"""
Interview session management API.
Handles creation, question delivery, answer submission, pause/resume, end, and report.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.graph.graph import resume_graph_with_answer, run_graph_until_suspend
from app.models.models import (
    AnswerEvaluation, CandidateAnswer, FinalReport,
    InterviewQuestion, InterviewSession,
    JobDescription, MatchReport as MatchReportModel, Resume,
)
from app.schemas.schemas import (
    AnswerResponse, CreateInterviewRequest, FinalReportResponse,
    QuestionResponse, SessionStateResponse, SubmitAnswerRequest,
)
from app.services.interview.planner import generate_interview_plan
from app.services.interview.tts import text_to_speech

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interviews", tags=["Interviews"])
settings = get_settings()


@router.post("", response_model=SessionStateResponse, status_code=status.HTTP_201_CREATED)
async def create_interview(request: CreateInterviewRequest, db: Session = Depends(get_db)):
    """
    Create a new interview session.
    Generates interview plan, initializes LangGraph state, persists to DB.
    """
    # Validate resume
    resume = db.query(Resume).filter(Resume.id == request.resume_id).first()
    if not resume or resume.extraction_status != "success":
        raise HTTPException(status_code=404, detail="Resume not found or not parsed")

    # Validate JD
    jd = db.query(JobDescription).filter(JobDescription.id == request.jd_id).first()
    if not jd or jd.extraction_status != "success":
        raise HTTPException(status_code=404, detail="Job description not found or not analyzed")

    # Get or create match report
    match = None
    if request.match_report_id:
        match = db.query(MatchReportModel).filter(MatchReportModel.id == request.match_report_id).first()

    if not match:
        match = db.query(MatchReportModel).filter(
            MatchReportModel.resume_id == request.resume_id,
            MatchReportModel.jd_id == request.jd_id,
        ).first()

    match_dict = {}
    if match:
        match_dict = {
            "overall_score": match.overall_score,
            "required_skills": match.skill_analysis.get("required", []) if match.skill_analysis else [],
            "unverified_claims": match.unverified_claims or [],
            "gaps": match.gaps or [],
            "suggested_topics": match.suggested_topics or [],
        }

    # Generate interview plan
    try:
        plan = await generate_interview_plan(
            parsed_resume=resume.parsed_profile or {},
            parsed_jd=jd.parsed_requirements or {},
            match_report=match_dict,
            mode=request.mode.value,
            difficulty=request.difficulty.value,
            duration_minutes=request.duration_minutes,
            max_questions=request.max_questions,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Interview plan generation failed: {str(e)[:200]}")

    # Create session
    session = InterviewSession(
        resume_id=request.resume_id,
        jd_id=request.jd_id,
        match_report_id=match.id if match else None,
        candidate_name=request.candidate_name,
        config={
            "mode": request.mode.value,
            "difficulty": request.difficulty.value,
            "duration_minutes": request.duration_minutes,
            "max_questions": request.max_questions,
        },
        status="active",
        total_questions=len(plan.questions),
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()  # get session.id

    # Persist questions
    questions_db_ids = {}
    for idx, q in enumerate(plan.questions):
        iq = InterviewQuestion(
            session_id=session.id,
            question_text=q.text,
            competency=q.competency,
            question_type=q.type,
            difficulty=q.difficulty,
            order_index=idx,
            jd_requirement=q.jd_requirement,
            resume_claim=q.resume_claim,
            reason=q.reason,
            expected_criteria=q.expected_answer_criteria,
            follow_up_suggestions=q.follow_up_suggestions,
            time_allocation_minutes=q.time_allocation_minutes,
            requires_whiteboard=q.requires_whiteboard,
            is_follow_up=False,
        )
        db.add(iq)
        db.flush()
        questions_db_ids[q.id] = iq.id

    # Build initial LangGraph state
    initial_state = {
        "session_id": session.id,
        "resume_id": request.resume_id,
        "jd_id": request.jd_id,
        "mode": request.mode.value,
        "difficulty": request.difficulty.value,
        "duration_minutes": request.duration_minutes,
        "max_questions": request.max_questions,
        "max_follow_ups_per_topic": settings.DEFAULT_MAX_FOLLOW_UPS_PER_TOPIC,
        "candidate_name": request.candidate_name,
        "resume_summary": resume.parsed_profile.get("summary", "") if resume.parsed_profile else "",
        "jd_role_title": jd.parsed_requirements.get("role_title", "") if jd.parsed_requirements else "",
        "planned_questions": [q.model_dump() for q in plan.questions],
        "questions_asked": [],
        "questions_db_ids": questions_db_ids,
        "current_question_index": 0,
        "current_question": None,
        "current_question_db_id": None,
        "follow_ups_on_current_topic": 0,
        "evaluations": [],
        "competency_coverage": {},
        "unverified_claims": match_dict.get("unverified_claims", []),
        "last_action": None,
        "last_action_reason": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "estimated_end_at": None,
        "status": "active",
        "awaiting_answer": False,
        "current_answer": None,
        "current_answer_skipped": False,
        "error_message": None,
    }

    # Run graph until first question is presented
    updated_state = await run_graph_until_suspend(initial_state)
    session.graph_state = updated_state
    db.commit()
    db.refresh(session)

    return SessionStateResponse(
        id=session.id,
        status=session.status,
        config=session.config,
        current_question_index=session.current_question_index,
        total_questions=session.total_questions,
        started_at=session.started_at,
        completed_at=session.completed_at,
        candidate_name=session.candidate_name,
        created_at=session.created_at,
    )


@router.get("/{session_id}", response_model=SessionStateResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Retrieve interview session state."""
    session = _get_session_or_404(session_id, db)
    return _session_to_response(session)


@router.get("/{session_id}/question", response_model=QuestionResponse)
async def get_current_question(session_id: str, db: Session = Depends(get_db)):
    """
    Get the current question for the interview.
    Also triggers Deepgram TTS synthesis (audio returned separately via /question/audio).
    """
    session = _get_session_or_404(session_id, db)
    graph_state = session.graph_state or {}
    current_q = graph_state.get("current_question")

    if not current_q:
        raise HTTPException(status_code=404, detail="No active question. Interview may be complete.")

    asked = len(graph_state.get("questions_asked", []))
    total = session.total_questions

    return QuestionResponse(
        id=current_q.get("id", ""),
        question_text=current_q.get("text", ""),
        competency=current_q.get("competency", ""),
        question_type=current_q.get("type", "technical"),
        difficulty=current_q.get("difficulty", "medium"),
        order_index=asked,
        requires_whiteboard=current_q.get("requires_whiteboard", False),
        time_allocation_minutes=current_q.get("time_allocation_minutes", 3),
        is_follow_up=current_q.get("is_follow_up", False),
        session_progress={
            "current": asked,
            "total": total,
            "percent": round((asked / total * 100) if total > 0 else 0),
            "status": graph_state.get("status", "active"),
        },
    )


@router.get("/{session_id}/question/audio")
async def get_question_audio(session_id: str, db: Session = Depends(get_db)):
    """
    Return Deepgram TTS audio for the current question.
    Returns MP3 bytes. Returns 204 if TTS is not configured.
    """
    session = _get_session_or_404(session_id, db)
    graph_state = session.graph_state or {}
    current_q = graph_state.get("current_question")

    if not current_q:
        return Response(status_code=204)

    question_text = current_q.get("text", "")
    audio_bytes = await text_to_speech(question_text)

    if not audio_bytes:
        return Response(status_code=204)  # TTS unavailable — frontend uses text

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=question.mp3"},
    )


@router.post("/{session_id}/answers", response_model=AnswerResponse)
async def submit_answer(
    session_id: str,
    request: SubmitAnswerRequest,
    db: Session = Depends(get_db),
):
    """
    Submit a candidate answer. Triggers evaluation and adaptive question selection.
    """
    session = _get_session_or_404(session_id, db)

    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Interview is already completed.")
    if session.status == "paused":
        raise HTTPException(status_code=400, detail="Resume the interview first.")

    graph_state = session.graph_state or {}
    current_q = graph_state.get("current_question")

    if not current_q:
        raise HTTPException(status_code=400, detail="No active question to answer.")

    # Get DB question ID
    q_db_id = graph_state.get("questions_db_ids", {}).get(current_q.get("id", ""))
    if not q_db_id:
        # Follow-up question — create DB record on the fly
        iq = InterviewQuestion(
            session_id=session_id,
            question_text=current_q.get("text", ""),
            competency=current_q.get("competency", ""),
            question_type=current_q.get("type", "technical"),
            difficulty=current_q.get("difficulty", "medium"),
            order_index=session.current_question_index + 1,
            is_follow_up=True,
            expected_criteria=[],
        )
        db.add(iq)
        db.flush()
        q_db_id = iq.id

    # Persist answer
    answer = CandidateAnswer(
        session_id=session_id,
        question_id=q_db_id,
        answer_text=request.answer_text,
        skipped=request.skipped,
    )
    db.add(answer)
    db.flush()

    # Resume graph with answer
    updated_state = await resume_graph_with_answer(
        state=graph_state,
        answer_text=request.answer_text or "",
        skipped=request.skipped,
    )

    # Persist evaluation if available
    evaluations = updated_state.get("evaluations", [])
    latest_eval = evaluations[-1] if evaluations else None
    eval_data = None

    if latest_eval and not latest_eval.get("skipped"):
        eval_record = AnswerEvaluation(
            answer_id=answer.id,
            criterion_scores=latest_eval.get("criterion_scores", {}),
            overall_score=latest_eval.get("overall_score", 0.0),
            concepts_demonstrated=latest_eval.get("concepts_demonstrated", []),
            missing_concepts=latest_eval.get("missing_concepts", []),
            evaluator_feedback=latest_eval.get("evaluator_feedback", ""),
            recommended_next_action=latest_eval.get("recommended_next_action", ""),
            contradicts_resume=latest_eval.get("contradicts_resume", False),
        )
        db.add(eval_record)
        eval_data = {
            "overall_score": latest_eval.get("overall_score"),
            "feedback": latest_eval.get("evaluator_feedback"),
            "concepts_demonstrated": latest_eval.get("concepts_demonstrated", []),
            "missing_concepts": latest_eval.get("missing_concepts", []),
        }

    # Update session
    new_status = updated_state.get("status", "active")
    session.graph_state = updated_state
    session.status = new_status
    session.current_question_index = len(updated_state.get("questions_asked", []))

    if new_status == "completed":
        session.completed_at = datetime.now(timezone.utc)
        # Save final report if generated
        final_report_data = updated_state.get("final_report")
        if final_report_data:
            existing_report = db.query(FinalReport).filter(FinalReport.session_id == session_id).first()
            if not existing_report:
                final_report = FinalReport(
                    session_id=session_id,
                    overall_score=final_report_data.get("overall_score"),
                    overall_summary=final_report_data.get("overall_summary", ""),
                    competency_scores=final_report_data.get("competency_scores"),
                    technical_strengths=final_report_data.get("technical_strengths"),
                    knowledge_gaps=final_report_data.get("knowledge_gaps"),
                    full_report=final_report_data,
                )
                db.add(final_report)

    db.commit()

    next_action = updated_state.get("last_action", "ask_next_question")
    return AnswerResponse(
        answer_id=answer.id,
        question_id=q_db_id,
        evaluation=eval_data,
        next_action=next_action,
        message="Answer recorded." if new_status != "completed" else "Interview complete. Report is ready.",
    )


@router.post("/{session_id}/pause")
def pause_interview(session_id: str, db: Session = Depends(get_db)):
    """Pause an active interview session."""
    session = _get_session_or_404(session_id, db)
    if session.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot pause session in status: {session.status}")
    session.status = "paused"
    session.paused_at = datetime.now(timezone.utc)
    # Persist status to graph state too
    if session.graph_state:
        session.graph_state = {**session.graph_state, "status": "paused"}
    db.commit()
    return {"message": "Interview paused.", "session_id": session_id}


@router.post("/{session_id}/resume")
def resume_interview(session_id: str, db: Session = Depends(get_db)):
    """Resume a paused interview session."""
    session = _get_session_or_404(session_id, db)
    if session.status != "paused":
        raise HTTPException(status_code=400, detail=f"Cannot resume session in status: {session.status}")
    session.status = "active"
    session.paused_at = None
    if session.graph_state:
        session.graph_state = {**session.graph_state, "status": "active"}
    db.commit()
    return {"message": "Interview resumed.", "session_id": session_id}


@router.post("/{session_id}/end")
async def end_interview(session_id: str, db: Session = Depends(get_db)):
    """End an interview early. Generates a partial report."""
    session = _get_session_or_404(session_id, db)
    if session.status in {"completed", "abandoned"}:
        raise HTTPException(status_code=400, detail="Interview is already ended.")

    graph_state = session.graph_state or {}
    # Run report generation
    from app.graph.nodes import node_generate_report
    report_state = await node_generate_report({**graph_state, "status": "completed"})

    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    session.graph_state = {**graph_state, **report_state}

    final_report_data = report_state.get("final_report") or graph_state.get("final_report")
    if final_report_data:
        existing = db.query(FinalReport).filter(FinalReport.session_id == session_id).first()
        if not existing:
            fr = FinalReport(
                session_id=session_id,
                overall_score=final_report_data.get("overall_score"),
                full_report=final_report_data,
                technical_strengths=final_report_data.get("technical_strengths"),
                knowledge_gaps=final_report_data.get("knowledge_gaps"),
                competency_scores=final_report_data.get("competency_scores"),
            )
            db.add(fr)

    db.commit()
    return {"message": "Interview ended. Report is ready.", "session_id": session_id}


@router.get("/{session_id}/report", response_model=FinalReportResponse)
def get_report(session_id: str, db: Session = Depends(get_db)):
    """Retrieve the final interview report."""
    session = _get_session_or_404(session_id, db)
    report = db.query(FinalReport).filter(FinalReport.session_id == session_id).first()
    if not report:
        if session.status != "completed":
            raise HTTPException(status_code=400, detail="Interview is not yet complete.")
        raise HTTPException(status_code=404, detail="Report not found. Try ending the interview first.")

    return FinalReportResponse(
        id=report.id,
        session_id=report.session_id,
        overall_score=report.overall_score,
        overall_summary=report.overall_summary,
        competency_scores=report.competency_scores,
        technical_strengths=report.technical_strengths,
        knowledge_gaps=report.knowledge_gaps,
        verified_claims=report.verified_claims,
        unverified_claims=report.unverified_claims,
        recommended_study_areas=report.recommended_study_areas,
        full_report=report.full_report,
        created_at=report.created_at,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete an interview session and all associated data."""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()


@router.get("", response_model=list[SessionStateResponse])
def list_sessions(db: Session = Depends(get_db)):
    """List all interview sessions (most recent first)."""
    sessions = (
        db.query(InterviewSession)
        .order_by(InterviewSession.created_at.desc())
        .limit(20)
        .all()
    )
    return [_session_to_response(s) for s in sessions]


def _get_session_or_404(session_id: str, db: Session) -> InterviewSession:
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    return session


def _session_to_response(session: InterviewSession) -> SessionStateResponse:
    return SessionStateResponse(
        id=session.id,
        status=session.status,
        config=session.config,
        current_question_index=session.current_question_index,
        total_questions=session.total_questions,
        started_at=session.started_at,
        completed_at=session.completed_at,
        candidate_name=session.candidate_name,
        created_at=session.created_at,
    )
