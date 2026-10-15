"""
LangGraph interview nodes.
Each node has explicit inputs (InterviewState) and outputs (state updates).
No side effects outside of what's documented.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.llm import call_llm_structured
from app.core.prompts import (
    ADAPTIVE_DECISION_PROMPT, ADAPTIVE_DECISION_SYSTEM,
    EVALUATOR_PROMPT, EVALUATOR_SYSTEM,
)
from app.graph.state import EvaluationRecord, InterviewState
from app.schemas.schemas import AdaptiveDecision, AnswerEvaluationResult

logger = logging.getLogger(__name__)


async def node_load_plan(state: InterviewState) -> Dict[str, Any]:
    """
    Node: Initialize interview state from plan.
    Validates that planned_questions exist.
    """
    if not state.get("planned_questions"):
        return {
            "status": "abandoned",
            "error_message": "No interview plan found. Cannot start interview.",
        }

    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "status": "active",
        "current_question_index": 0,
        "follow_ups_on_current_topic": 0,
        "evaluations": [],
        "competency_coverage": {},
        "questions_asked": [],
        "started_at": now_iso,
        "awaiting_answer": False,
        "error_message": None,
    }


async def node_select_question(state: InterviewState) -> Dict[str, Any]:
    """
    Node: Select the next question using the adaptive rule-based policy.
    Records the reason for each selection decision.
    """
    planned = state.get("planned_questions", [])
    asked_ids = set(state.get("questions_asked", []))
    current_idx = state.get("current_question_index", 0)
    follow_ups_used = state.get("follow_ups_on_current_topic", 0)
    max_follow_ups = state.get("max_follow_ups_per_topic", 2)
    max_q = state.get("max_questions", 12)

    # Check termination conditions
    if len(asked_ids) >= max_q:
        return {"status": "completed", "current_question": None, "awaiting_answer": False}

    if len(asked_ids) >= len(planned):
        return {"status": "completed", "current_question": None, "awaiting_answer": False}

    # Check if we need a follow-up on current topic
    last_eval = state.get("evaluations", [])[-1] if state.get("evaluations") else None
    current_q = state.get("current_question")

    if (
        last_eval
        and last_eval.get("recommended_next_action") == "follow_up"
        and follow_ups_used < max_follow_ups
        and current_q
    ):
        # Follow-up will be injected by decide node; skip normal selection
        return {}  # No change — decide node handles this

    # Find next unasked planned question
    next_q = None
    for q in planned:
        if q["id"] not in asked_ids:
            next_q = q
            break

    if next_q is None:
        return {"status": "completed", "current_question": None, "awaiting_answer": False}

    return {
        "current_question": next_q,
        "current_question_db_id": state.get("questions_db_ids", {}).get(next_q["id"]),
        "follow_ups_on_current_topic": 0,
        "last_action": "ask_next_question",
        "last_action_reason": "Next highest-priority uncovered competency",
    }


async def node_present_question(state: InterviewState) -> Dict[str, Any]:
    """
    Node: Mark that we are waiting for the candidate's answer.
    Graph suspends here until answer is submitted via API.
    """
    current_q = state.get("current_question")
    if not current_q:
        return {"status": "completed", "awaiting_answer": False}

    q_id = current_q.get("id")
    asked_ids = list(state.get("questions_asked", []))
    if q_id and q_id not in asked_ids:
        asked_ids.append(q_id)

    return {
        "awaiting_answer": True,
        "current_answer": None,
        "current_answer_skipped": False,
        "questions_asked": asked_ids,
    }


async def node_evaluate_answer(state: InterviewState) -> Dict[str, Any]:
    """
    Node: Evaluate the candidate's answer using LLM structured rubric.
    Returns updated evaluations list and competency coverage map.
    """
    current_q = state.get("current_question", {})
    answer_text = state.get("current_answer")
    skipped = state.get("current_answer_skipped", False)

    if skipped or not answer_text or not answer_text.strip():
        # Record skip — no LLM call needed
        eval_record = EvaluationRecord(
            question_id=current_q.get("id", ""),
            question_text=current_q.get("text", ""),
            competency=current_q.get("competency", ""),
            answer_text=None,
            skipped=True,
            overall_score=0.0,
            criterion_scores={},
            concepts_demonstrated=[],
            missing_concepts=current_q.get("expected_answer_criteria", []),
            evaluator_feedback="Question was skipped.",
            recommended_next_action="move_on",
            contradicts_resume=False,
        )
        evaluations = list(state.get("evaluations", [])) + [eval_record]
        return {
            "evaluations": evaluations,
            "awaiting_answer": False,
            "error_message": None,
        }

    # Build prompt
    prompt = EVALUATOR_PROMPT.format(
        question_text=current_q.get("text", ""),
        competency=current_q.get("competency", ""),
        difficulty=current_q.get("difficulty", "medium"),
        expected_criteria=json.dumps(current_q.get("expected_answer_criteria", [])),
        resume_context=state.get("resume_summary", ""),
        answer_text=answer_text,
    )

    try:
        result: AnswerEvaluationResult = await call_llm_structured(
            prompt=prompt,
            output_schema=AnswerEvaluationResult,
            system_prompt=EVALUATOR_SYSTEM,
        )

        eval_record = EvaluationRecord(
            question_id=current_q.get("id", ""),
            question_text=current_q.get("text", ""),
            competency=current_q.get("competency", ""),
            answer_text=answer_text,
            skipped=False,
            overall_score=result.overall_score,
            criterion_scores=result.scores,
            concepts_demonstrated=result.concepts_demonstrated,
            missing_concepts=result.missing_concepts,
            evaluator_feedback=result.evaluator_feedback,
            recommended_next_action=result.recommended_next_action,
            contradicts_resume=result.contradicts_resume,
        )

        # Update competency coverage
        competency = current_q.get("competency", "general")
        coverage = dict(state.get("competency_coverage", {}))
        coverage.setdefault(competency, []).append(result.overall_score)

    except Exception as e:
        logger.error(f"Answer evaluation failed: {e}")
        eval_record = EvaluationRecord(
            question_id=current_q.get("id", ""),
            question_text=current_q.get("text", ""),
            competency=current_q.get("competency", ""),
            answer_text=answer_text,
            skipped=False,
            overall_score=0.0,
            criterion_scores={},
            concepts_demonstrated=[],
            missing_concepts=[],
            evaluator_feedback=f"Evaluation failed due to LLM error: {str(e)[:200]}",
            recommended_next_action="move_on",
            contradicts_resume=False,
        )
        coverage = dict(state.get("competency_coverage", {}))

    evaluations = list(state.get("evaluations", [])) + [eval_record]
    return {
        "evaluations": evaluations,
        "competency_coverage": coverage,
        "awaiting_answer": False,
        "error_message": None,
    }


async def node_decide_next(state: InterviewState) -> Dict[str, Any]:
    """
    Node: Adaptive decision — follow-up, next question, or end interview.
    Rule-based with LLM to generate follow-up text if needed.
    Decision reason is always logged.
    """
    evaluations = state.get("evaluations", [])
    if not evaluations:
        return {"last_action": "ask_next_question", "last_action_reason": "No evaluations yet"}

    last_eval = evaluations[-1]
    score = last_eval.get("overall_score", 0.0)
    next_action_hint = last_eval.get("recommended_next_action", "move_on")
    follow_ups_used = state.get("follow_ups_on_current_topic", 0)
    max_follow_ups = state.get("max_follow_ups_per_topic", 2)
    asked_count = len(state.get("questions_asked", []))
    max_q = state.get("max_questions", 12)
    planned = state.get("planned_questions", [])

    # Terminal check
    if asked_count >= max_q or asked_count >= len(planned):
        return {"last_action": "end_interview", "last_action_reason": "Question budget exhausted"}

    # Rule-based adaptive policy
    should_follow_up = (
        next_action_hint in {"follow_up", "clarify", "verify_claim"}
        and follow_ups_used < max_follow_ups
        and score > 0.0  # Don't follow up on blank/skipped answers
    )

    if should_follow_up:
        # Generate follow-up question via LLM
        current_q = state.get("current_question", {})
        topics_covered = [e["competency"] for e in evaluations]
        topics_remaining = [
            q["competency"] for q in planned
            if q["id"] not in state.get("questions_asked", [])
        ]

        prompt = ADAPTIVE_DECISION_PROMPT.format(
            current_question=current_q.get("text", ""),
            score=round(score, 2),
            recommended_action=next_action_hint,
            follow_ups_used=follow_ups_used,
            max_follow_ups=max_follow_ups,
            questions_remaining=max_q - asked_count,
            time_remaining="unknown",  # Could compute from started_at
            topics_covered=", ".join(set(topics_covered)),
            topics_remaining=", ".join(set(topics_remaining[:5])),
        )

        try:
            decision: AdaptiveDecision = await call_llm_structured(
                prompt=prompt,
                output_schema=AdaptiveDecision,
                system_prompt="Decide the next interview action. Return JSON only.",
            )

            if decision.action == "ask_follow_up" and decision.follow_up_text:
                # Create follow-up question object
                current_q_copy = dict(current_q)
                follow_up_id = f"followup_{current_q.get('id', 'q')}_{follow_ups_used + 1}"
                follow_up_q = {
                    "id": follow_up_id,
                    "text": decision.follow_up_text,
                    "type": current_q_copy.get("type", "technical"),
                    "competency": current_q_copy.get("competency", ""),
                    "difficulty": current_q_copy.get("difficulty", "medium"),
                    "expected_answer_criteria": [],
                    "follow_up_suggestions": [],
                    "time_allocation_minutes": 2,
                    "requires_whiteboard": False,
                    "is_follow_up": True,
                    "reason": decision.reason,
                }
                return {
                    "current_question": follow_up_q,
                    "follow_ups_on_current_topic": follow_ups_used + 1,
                    "last_action": "follow_up",
                    "last_action_reason": decision.reason,
                }

        except Exception as e:
            logger.warning(f"Adaptive decision LLM call failed: {e}. Falling through to next question.")

    return {
        "last_action": "ask_next_question",
        "last_action_reason": f"Moving to next topic (score={score:.1f}, action={next_action_hint})",
    }


async def node_generate_report(state: InterviewState) -> Dict[str, Any]:
    """
    Node: Aggregate all evaluations into a final report structure.
    This node runs when status transitions to 'completed'.
    """
    evaluations = state.get("evaluations", [])
    competency_coverage = state.get("competency_coverage", {})

    # Aggregate competency scores
    competency_scores: Dict[str, Any] = {}
    for comp, scores in competency_coverage.items():
        if scores:
            avg = sum(scores) / len(scores)
            competency_scores[comp] = {
                "average_score": round(avg, 2),
                "num_questions": len(scores),
                "max_score": max(scores),
                "min_score": min(scores),
            }

    # Overall score
    all_scores = [e["overall_score"] for e in evaluations if not e.get("skipped")]
    overall = sum(all_scores) / len(all_scores) if all_scores else 0.0

    # Strengths and gaps
    strengths = []
    gaps = []
    for eval_rec in evaluations:
        for concept in eval_rec.get("concepts_demonstrated", []):
            if concept not in strengths:
                strengths.append(concept)
        for concept in eval_rec.get("missing_concepts", []):
            if concept not in gaps:
                gaps.append(concept)

    report_data = {
        "overall_score": round(overall, 2),
        "competency_scores": competency_scores,
        "technical_strengths": strengths[:8],
        "knowledge_gaps": gaps[:8],
        "questions_asked": len(state.get("questions_asked", [])),
        "questions_skipped": sum(1 for e in evaluations if e.get("skipped")),
        "evaluations": evaluations,
        "disclaimer": (
            "This is an AI-generated practice interview report. "
            "It is not a validated assessment of professional competence "
            "and should not be used as a hiring decision tool."
        ),
    }

    return {
        "status": "completed",
        "final_report": report_data,
    }
