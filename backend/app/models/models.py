"""SQLAlchemy ORM models for the AI Interviewer."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


def _uuid():
    return str(uuid.uuid4())


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)  # pdf | docx
    raw_text = Column(Text, nullable=False)
    parsed_profile = Column(JSONB, nullable=True)   # structured extraction result
    extraction_status = Column(String(20), default="pending")  # pending|success|failed
    extraction_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("InterviewSession", back_populates="resume")


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    raw_text = Column(Text, nullable=False)
    parsed_requirements = Column(JSONB, nullable=True)
    extraction_status = Column(String(20), default="pending")
    extraction_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("InterviewSession", back_populates="job_description")


class MatchReport(Base):
    __tablename__ = "match_reports"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    resume_id = Column(UUID(as_uuid=False), ForeignKey("resumes.id"), nullable=False)
    jd_id = Column(UUID(as_uuid=False), ForeignKey("job_descriptions.id"), nullable=False)

    overall_score = Column(Float, nullable=True)
    required_skill_coverage = Column(Float, nullable=True)  # 0-1
    preferred_skill_coverage = Column(Float, nullable=True)
    semantic_score = Column(Float, nullable=True)

    skill_analysis = Column(JSONB, nullable=True)     # matched/partial/missing skills
    strengths = Column(JSONB, nullable=True)          # list of strength strings
    unverified_claims = Column(JSONB, nullable=True)
    gaps = Column(JSONB, nullable=True)
    suggested_topics = Column(JSONB, nullable=True)
    interview_plan = Column(JSONB, nullable=True)     # generated plan

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("InterviewSession", back_populates="match_report")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    resume_id = Column(UUID(as_uuid=False), ForeignKey("resumes.id"), nullable=False)
    jd_id = Column(UUID(as_uuid=False), ForeignKey("job_descriptions.id"), nullable=False)
    match_report_id = Column(UUID(as_uuid=False), ForeignKey("match_reports.id"), nullable=True)

    # Configuration
    config = Column(JSONB, nullable=True)  # duration, mode, difficulty, max_questions

    # State
    status = Column(String(20), default="pending")  # pending|active|paused|completed|abandoned
    graph_state = Column(JSONB, nullable=True)       # persisted LangGraph state
    current_question_index = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    follow_ups_on_current = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Candidate info (optional)
    candidate_name = Column(String(255), nullable=True)

    resume = relationship("Resume", back_populates="sessions")
    job_description = relationship("JobDescription", back_populates="sessions")
    match_report = relationship("MatchReport", back_populates="sessions")
    questions = relationship("InterviewQuestion", back_populates="session", order_by="InterviewQuestion.order_index")
    answers = relationship("CandidateAnswer", back_populates="session")
    report = relationship("FinalReport", back_populates="session", uselist=False)


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("interview_sessions.id"), nullable=False)

    question_text = Column(Text, nullable=False)
    competency = Column(String(255), nullable=False)
    question_type = Column(String(50), nullable=False)  # technical|behavioral|project|scenario|system_design
    difficulty = Column(String(20), nullable=False)      # easy|medium|hard
    order_index = Column(Integer, nullable=False)
    jd_requirement = Column(Text, nullable=True)
    resume_claim = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    expected_criteria = Column(JSONB, nullable=True)
    follow_up_suggestions = Column(JSONB, nullable=True)
    time_allocation_minutes = Column(Integer, default=3)
    requires_whiteboard = Column(Boolean, default=False)
    is_follow_up = Column(Boolean, default=False)
    parent_question_id = Column(UUID(as_uuid=False), ForeignKey("interview_questions.id"), nullable=True)

    session = relationship("InterviewSession", back_populates="questions")
    answers = relationship("CandidateAnswer", back_populates="question")


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("interview_sessions.id"), nullable=False)
    question_id = Column(UUID(as_uuid=False), ForeignKey("interview_questions.id"), nullable=False)

    answer_text = Column(Text, nullable=True)
    skipped = Column(Boolean, default=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="answers")
    question = relationship("InterviewQuestion", back_populates="answers")
    evaluation = relationship("AnswerEvaluation", back_populates="answer", uselist=False)


class AnswerEvaluation(Base):
    __tablename__ = "answer_evaluations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    answer_id = Column(UUID(as_uuid=False), ForeignKey("candidate_answers.id"), nullable=False, unique=True)

    criterion_scores = Column(JSONB, nullable=False)  # {technical_correctness: 3, ...}
    overall_score = Column(Float, nullable=False)
    concepts_demonstrated = Column(JSONB, nullable=True)
    missing_concepts = Column(JSONB, nullable=True)
    technical_inaccuracies = Column(JSONB, nullable=True)
    evidence_from_answer = Column(Text, nullable=True)
    evaluator_feedback = Column(Text, nullable=True)
    evaluator_confidence = Column(String(20), nullable=True)
    evaluator_uncertainty = Column(Text, nullable=True)
    recommended_next_action = Column(String(50), nullable=True)
    follow_up_reason = Column(Text, nullable=True)
    contradicts_resume = Column(Boolean, default=False)
    contradiction_detail = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    answer = relationship("CandidateAnswer", back_populates="evaluation")


class FinalReport(Base):
    __tablename__ = "final_reports"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("interview_sessions.id"), nullable=False, unique=True)

    overall_score = Column(Float, nullable=True)
    overall_summary = Column(Text, nullable=True)
    competency_scores = Column(JSONB, nullable=True)
    technical_strengths = Column(JSONB, nullable=True)
    knowledge_gaps = Column(JSONB, nullable=True)
    verified_claims = Column(JSONB, nullable=True)
    unverified_claims = Column(JSONB, nullable=True)
    recommended_study_areas = Column(JSONB, nullable=True)
    full_report = Column(JSONB, nullable=True)  # complete raw report JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InterviewSession", back_populates="report")
