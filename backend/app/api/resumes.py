"""Resume upload and parsing API."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.llm import call_llm_structured
from app.core.prompts import RESUME_ANALYST_PROMPT, RESUME_ANALYST_SYSTEM
from app.db.session import get_db
from app.models.models import Resume
from app.schemas.schemas import ParsedResume, ResumeResponse
from app.services.document_processing.extractor import DocumentProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resumes", tags=["Resumes"])
settings = get_settings()
processor = DocumentProcessor(max_bytes=settings.max_file_bytes)


@router.post("", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF or DOCX resume.
    Extracts text and runs structured LLM analysis.
    File content is treated as untrusted data — never executed.
    """
    # Validate MIME type (defense in depth)
    if file.content_type not in {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    } and not (file.filename or "").lower().endswith((".pdf", ".docx")):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are accepted.",
        )

    file_bytes = await file.read()

    # Extract text
    try:
        extraction = processor.extract(file_bytes, file.filename or "resume")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not extraction.success:
        raise HTTPException(
            status_code=422,
            detail=f"Document extraction failed: {extraction.error}",
        )

    # Create DB record
    resume = Resume(
        filename=file.filename or "resume",
        file_type=extraction.file_type,
        raw_text=extraction.text,
        extraction_status="pending",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    # Run LLM analysis
    prompt = RESUME_ANALYST_PROMPT.format(resume_text=extraction.text[:15000])  # cap for token safety

    try:
        parsed: ParsedResume = await call_llm_structured(
            prompt=prompt,
            output_schema=ParsedResume,
            system_prompt=RESUME_ANALYST_SYSTEM,
        )
        resume.parsed_profile = parsed.model_dump()
        resume.extraction_status = "success"
    except Exception as e:
        logger.error(f"Resume LLM analysis failed: {e}")
        resume.extraction_status = "failed"
        resume.extraction_error = str(e)[:500]

    db.commit()
    db.refresh(resume)

    return ResumeResponse(
        id=resume.id,
        filename=resume.filename,
        extraction_status=resume.extraction_status,
        parsed_profile=resume.parsed_profile,
        created_at=resume.created_at,
    )


@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume(resume_id: str, db: Session = Depends(get_db)):
    """Retrieve a previously uploaded resume."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return ResumeResponse(
        id=resume.id,
        filename=resume.filename,
        extraction_status=resume.extraction_status,
        parsed_profile=resume.parsed_profile,
        created_at=resume.created_at,
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: str, db: Session = Depends(get_db)):
    """Delete a resume and its parsed data."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    db.delete(resume)
    db.commit()
