"""
LangGraph interview state definition.
All fields are typed. State is serializable to JSON for DB persistence.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class EvaluationRecord(TypedDict):
    question_id: str
    question_text: str
    competency: str
    answer_text: Optional[str]
    skipped: bool
    overall_score: float
    criterion_scores: Dict[str, int]
    concepts_demonstrated: List[str]
    missing_concepts: List[str]
    evaluator_feedback: str
    recommended_next_action: str
    contradicts_resume: bool


class InterviewState(TypedDict):
    """Typed LangGraph state. Persisted to DB as JSONB after each node."""

    # ─── Session identifiers ─────────────────────────────────────────────────
    session_id: str
    resume_id: str
    jd_id: str

    # ─── Configuration ────────────────────────────────────────────────────────
    mode: str                   # technical|behavioral|mixed|project-focused
    difficulty: str             # easy|medium|hard
    duration_minutes: int
    max_questions: int
    max_follow_ups_per_topic: int

    # ─── Candidate info ───────────────────────────────────────────────────────
    candidate_name: Optional[str]
    resume_summary: str
    jd_role_title: str

    # ─── Interview plan ───────────────────────────────────────────────────────
    planned_questions: List[Dict[str, Any]]  # list of PlannedQuestion dicts
    questions_asked: List[str]               # question IDs asked so far
    questions_db_ids: Dict[str, str]         # plan_id → db question UUID

    # ─── Current question ─────────────────────────────────────────────────────
    current_question_index: int
    current_question: Optional[Dict[str, Any]]
    current_question_db_id: Optional[str]
    follow_ups_on_current_topic: int

    # ─── Evaluations ──────────────────────────────────────────────────────────
    evaluations: List[EvaluationRecord]
    competency_coverage: Dict[str, List[float]]  # competency → [scores]
    unverified_claims: List[str]

    # ─── Adaptive state ───────────────────────────────────────────────────────
    last_action: Optional[str]   # follow_up|ask_next|end
    last_action_reason: Optional[str]

    # ─── Timing ───────────────────────────────────────────────────────────────
    started_at: Optional[str]    # ISO datetime string
    estimated_end_at: Optional[str]

    # ─── Control ──────────────────────────────────────────────────────────────
    status: str                  # pending|active|paused|completed|abandoned
    awaiting_answer: bool        # True = graph suspended, waiting for user input
    current_answer: Optional[str]
    current_answer_skipped: bool
    error_message: Optional[str]
