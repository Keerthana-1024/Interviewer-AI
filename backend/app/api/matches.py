"""Resume–JD matching API."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import JobDescription, MatchReport as MatchReportModel, Resume
from app.schemas.schemas import CreateMatchRequest, MatchReportResponse
from app.services.matching.match_engine import MatchEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/matches", tags=["Matching"])
engine = MatchEngine()


@router.post("", response_model=MatchReportResponse, status_code=status.HTTP_201_CREATED)
def create_match(request: CreateMatchRequest, db: Session = Depends(get_db)):
    """
    Run hybrid matching between a resume and job description.
    Returns alignment score, skill coverage, strengths, gaps, and suggested topics.
    """
    # Fetch resume
    resume = db.query(Resume).filter(Resume.id == request.resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.extraction_status != "success" or not resume.parsed_profile:
        raise HTTPException(
            status_code=422,
            detail="Resume has not been successfully parsed. Upload and parse it first.",
        )

    # Fetch JD
    jd = db.query(JobDescription).filter(JobDescription.id == request.jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="Job description not found")
    if jd.extraction_status != "success" or not jd.parsed_requirements:
        raise HTTPException(
            status_code=422,
            detail="Job description has not been successfully analyzed. Analyze it first.",
        )

    # Check for existing match (idempotent)
    existing = db.query(MatchReportModel).filter(
        MatchReportModel.resume_id == request.resume_id,
        MatchReportModel.jd_id == request.jd_id,
    ).first()
    if existing:
        return _to_response(existing)

    # Run hybrid matching
    # Build section map from raw_text for semantic matching
    from app.services.document_processing.extractor import _detect_sections
    resume_sections = _detect_sections(resume.raw_text)

    try:
        match_result = engine.compute_match(
            parsed_resume=resume.parsed_profile,
            parsed_jd=jd.parsed_requirements,
            resume_sections=resume_sections,
        )
    except Exception as e:
        logger.error(f"Match engine error: {e}")
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)[:200]}")

    report_dict = match_result.to_dict()

    # Persist
    match = MatchReportModel(
        resume_id=request.resume_id,
        jd_id=request.jd_id,
        overall_score=match_result.overall_score,
        required_skill_coverage=match_result.required_skill_coverage,
        preferred_skill_coverage=match_result.preferred_skill_coverage,
        semantic_score=match_result.semantic_relevance_score,
        skill_analysis={
            "required": report_dict["required_skills"],
            "preferred": report_dict["preferred_skills"],
        },
        strengths=match_result.strengths,
        unverified_claims=match_result.unverified_claims,
        gaps=match_result.gaps,
        suggested_topics=match_result.suggested_topics,
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    return _to_response(match)


@router.get("/{match_id}", response_model=MatchReportResponse)
def get_match(match_id: str, db: Session = Depends(get_db)):
    """Retrieve a previously computed match report."""
    match = db.query(MatchReportModel).filter(MatchReportModel.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match report not found")
    return _to_response(match)


def _to_response(match: MatchReportModel) -> MatchReportResponse:
    return MatchReportResponse(
        id=match.id,
        resume_id=match.resume_id,
        jd_id=match.jd_id,
        overall_score=match.overall_score,
        required_skill_coverage=match.required_skill_coverage,
        preferred_skill_coverage=match.preferred_skill_coverage,
        skill_analysis=match.skill_analysis,
        strengths=match.strengths,
        gaps=match.gaps,
        suggested_topics=match.suggested_topics,
        interview_plan=match.interview_plan,
        created_at=match.created_at,
    )
