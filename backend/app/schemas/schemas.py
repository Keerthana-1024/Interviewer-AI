"""Pydantic schemas for API request/response and LLM structured output validation."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ─── Enums ────────────────────────────────────────────────────────────────────

class InterviewMode(str, Enum):
    technical = "technical"
    behavioral = "behavioral"
    mixed = "mixed"
    project_focused = "project-focused"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class SessionStatus(str, Enum):
    pending = "pending"
    active = "active"
    paused = "paused"
    completed = "completed"
    abandoned = "abandoned"


class NextAction(str, Enum):
    follow_up = "follow_up"
    clarify = "clarify"
    move_on = "move_on"
    verify_claim = "verify_claim"
    end_topic = "end_topic"


# ─── LLM Structured Outputs ───────────────────────────────────────────────────

class ExtractedSkill(BaseModel):
    name: str
    category: str
    evidence: str
    source_section: str
    confidence: str  # high|medium|low
    ambiguity: Optional[str] = None


class ExtractedExperience(BaseModel):
    title: str
    company: str
    duration: str
    duration_months: Optional[int] = None
    responsibilities: List[str] = []
    technologies_used: List[str] = []
    achievements: List[str] = []
    evidence: str


class ExtractedProject(BaseModel):
    name: str
    description: str
    technologies: List[str] = []
    role: Optional[str] = None
    impact: Optional[str] = None
    evidence: str


class ExtractedEducation(BaseModel):
    degree: str
    field: Optional[str] = None
    institution: str
    year: Optional[str] = None
    gpa: Optional[str] = None
    relevant_coursework: List[str] = []


class ExtractedCertification(BaseModel):
    name: str
    issuer: Optional[str] = None
    year: Optional[str] = None
    evidence: Optional[str] = None


class ParsedResume(BaseModel):
    """Structured LLM output from resume analysis."""
    skills: List[ExtractedSkill] = []
    experience: List[ExtractedExperience] = []
    projects: List[ExtractedProject] = []
    education: List[ExtractedEducation] = []
    certifications: List[ExtractedCertification] = []
    summary: str = ""


class JDSkillRequirement(BaseModel):
    name: str
    category: str
    importance: str  # mandatory|preferred
    evidence: str
    years_expected: Optional[int] = None


class ParsedJD(BaseModel):
    """Structured LLM output from JD analysis."""
    role_title: str
    seniority: str
    domain: str
    required_skills: List[JDSkillRequirement] = []
    responsibilities: List[str] = []
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    technical_competencies: List[str] = []
    behavioral_competencies: List[str] = []
    nice_to_have: List[str] = []
    domain_knowledge_required: List[str] = []


class AnswerEvaluationResult(BaseModel):
    """Structured LLM output from answer evaluation."""
    scores: Dict[str, int]  # criterion → 0-4
    overall_score: float = Field(..., ge=0, le=4)
    concepts_demonstrated: List[str] = []
    missing_concepts: List[str] = []
    technical_inaccuracies: List[str] = []
    evidence_from_answer: Optional[str] = None
    evaluator_feedback: str
    evaluator_confidence: str  # high|medium|low
    evaluator_uncertainty: Optional[str] = None
    recommended_next_action: str
    follow_up_reason: Optional[str] = None
    contradicts_resume: bool = False
    contradiction_detail: Optional[str] = None


class PlannedQuestion(BaseModel):
    """One question in the generated interview plan."""
    id: str
    text: str
    type: str
    competency: str
    jd_requirement: Optional[str] = None
    resume_claim: Optional[str] = None
    reason: str
    difficulty: str
    expected_answer_criteria: List[str] = []
    follow_up_suggestions: List[str] = []
    time_allocation_minutes: int = 3
    requires_whiteboard: bool = False


class InterviewPlan(BaseModel):
    """Structured LLM output from interview planning."""
    plan_summary: str
    total_estimated_minutes: int
    questions: List[PlannedQuestion]


class AdaptiveDecision(BaseModel):
    """Structured LLM output for adaptive next-action decision."""
    action: str  # ask_follow_up|ask_next_question|end_interview
    reason: str
    follow_up_text: Optional[str] = None


# ─── API Request Schemas ───────────────────────────────────────────────────────

class AnalyzeJDRequest(BaseModel):
    jd_text: str = Field(..., min_length=50, max_length=50000)


class CreateMatchRequest(BaseModel):
    resume_id: str
    jd_id: str


class CreateInterviewRequest(BaseModel):
    resume_id: str
    jd_id: str
    match_report_id: Optional[str] = None
    candidate_name: Optional[str] = None
    mode: InterviewMode = InterviewMode.mixed
    difficulty: Difficulty = Difficulty.medium
    duration_minutes: int = Field(default=30, ge=10, le=120)
    max_questions: int = Field(default=12, ge=3, le=30)


class SubmitAnswerRequest(BaseModel):
    answer_text: Optional[str] = Field(default=None, max_length=10000)
    skipped: bool = False

    @field_validator("answer_text")
    @classmethod
    def check_answer(cls, v: Optional[str], info: Any) -> Optional[str]:
        if v:
            return v.strip()
        return v


# ─── API Response Schemas ─────────────────────────────────────────────────────

class ResumeResponse(BaseModel):
    id: str
    filename: str
    extraction_status: str
    parsed_profile: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class JDResponse(BaseModel):
    id: str
    extraction_status: str
    parsed_requirements: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MatchReportResponse(BaseModel):
    id: str
    resume_id: str
    jd_id: str
    overall_score: Optional[float]
    required_skill_coverage: Optional[float]
    preferred_skill_coverage: Optional[float]
    skill_analysis: Optional[Dict[str, Any]]
    strengths: Optional[List[str]]
    gaps: Optional[List[str]]
    suggested_topics: Optional[List[str]]
    interview_plan: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    id: str
    question_text: str
    competency: str
    question_type: str
    difficulty: str
    order_index: int
    requires_whiteboard: bool
    time_allocation_minutes: int
    is_follow_up: bool
    session_progress: Dict[str, Any]  # {current: 3, total: 12, time_remaining: 20}


class SessionStateResponse(BaseModel):
    id: str
    status: str
    config: Optional[Dict[str, Any]]
    current_question_index: int
    total_questions: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    candidate_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AnswerResponse(BaseModel):
    answer_id: str
    question_id: str
    evaluation: Optional[Dict[str, Any]]
    next_action: str
    message: str


class FinalReportResponse(BaseModel):
    id: str
    session_id: str
    overall_score: Optional[float]
    overall_summary: Optional[str]
    competency_scores: Optional[Dict[str, Any]]
    technical_strengths: Optional[List[str]]
    knowledge_gaps: Optional[List[str]]
    verified_claims: Optional[List[str]]
    unverified_claims: Optional[List[str]]
    recommended_study_areas: Optional[List[Dict[str, str]]]
    full_report: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
