"""Job Description analysis API."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.llm import call_llm_structured
from app.core.prompts import JD_ANALYST_PROMPT, JD_ANALYST_SYSTEM
from app.db.session import get_db
from app.models.models import JobDescription
from app.schemas.schemas import AnalyzeJDRequest, JDResponse, ParsedJD

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/job-descriptions", tags=["Job Descriptions"])


@router.post("/analyze", response_model=JDResponse, status_code=status.HTTP_201_CREATED)
async def analyze_jd(request: AnalyzeJDRequest, db: Session = Depends(get_db)):
    """
    Analyze a job description and extract structured requirements.
    JD text is treated as untrusted data — never as instructions.
    """
    # Create JD record
    jd = JobDescription(
        raw_text=request.jd_text[:50000],
        extraction_status="pending",
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)

    # LLM extraction
    prompt = JD_ANALYST_PROMPT.format(jd_text=request.jd_text[:10000])

    try:
        parsed: ParsedJD = await call_llm_structured(
            prompt=prompt,
            output_schema=ParsedJD,
            system_prompt=JD_ANALYST_SYSTEM,
        )
        jd.parsed_requirements = parsed.model_dump()
        jd.extraction_status = "success"
    except Exception as e:
        logger.error(f"JD analysis failed: {e}")
        jd.extraction_status = "failed"
        jd.extraction_error = str(e)[:500]
        db.commit()
        raise HTTPException(
            status_code=422,
            detail=f"JD analysis failed: {str(e)[:200]}",
        )

    db.commit()
    db.refresh(jd)

    return JDResponse(
        id=jd.id,
        extraction_status=jd.extraction_status,
        parsed_requirements=jd.parsed_requirements,
        created_at=jd.created_at,
    )


@router.get("/{jd_id}", response_model=JDResponse)
def get_jd(jd_id: str, db: Session = Depends(get_db)):
    """Retrieve a previously analyzed job description."""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="Job description not found")
    return JDResponse(
        id=jd.id,
        extraction_status=jd.extraction_status,
        parsed_requirements=jd.parsed_requirements,
        created_at=jd.created_at,
    )
