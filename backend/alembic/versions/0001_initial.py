"""Initial schema — all tables for AI Interviewer.

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # resumes
    op.create_table(
        "resumes",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("parsed_profile", JSONB, nullable=True),
        sa.Column("extraction_status", sa.String(20), server_default="pending"),
        sa.Column("extraction_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # job_descriptions
    op.create_table(
        "job_descriptions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("parsed_requirements", JSONB, nullable=True),
        sa.Column("extraction_status", sa.String(20), server_default="pending"),
        sa.Column("extraction_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # match_reports
    op.create_table(
        "match_reports",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("resume_id", UUID(as_uuid=False), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jd_id", UUID(as_uuid=False), sa.ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_score", sa.Float, nullable=True),
        sa.Column("required_skill_coverage", sa.Float, nullable=True),
        sa.Column("preferred_skill_coverage", sa.Float, nullable=True),
        sa.Column("semantic_score", sa.Float, nullable=True),
        sa.Column("skill_analysis", JSONB, nullable=True),
        sa.Column("strengths", JSONB, nullable=True),
        sa.Column("unverified_claims", JSONB, nullable=True),
        sa.Column("gaps", JSONB, nullable=True),
        sa.Column("suggested_topics", JSONB, nullable=True),
        sa.Column("interview_plan", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_match_reports_resume_jd", "match_reports", ["resume_id", "jd_id"])

    # interview_sessions
    op.create_table(
        "interview_sessions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("resume_id", UUID(as_uuid=False), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jd_id", UUID(as_uuid=False), sa.ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_report_id", UUID(as_uuid=False), sa.ForeignKey("match_reports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("graph_state", JSONB, nullable=True),
        sa.Column("current_question_index", sa.Integer, server_default="0"),
        sa.Column("total_questions", sa.Integer, server_default="0"),
        sa.Column("follow_ups_on_current", sa.Integer, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("candidate_name", sa.String(255), nullable=True),
    )
    op.create_index("ix_sessions_status", "interview_sessions", ["status"])

    # interview_questions
    op.create_table(
        "interview_questions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=False), sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("competency", sa.String(255), nullable=False),
        sa.Column("question_type", sa.String(50), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("jd_requirement", sa.Text, nullable=True),
        sa.Column("resume_claim", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("expected_criteria", JSONB, nullable=True),
        sa.Column("follow_up_suggestions", JSONB, nullable=True),
        sa.Column("time_allocation_minutes", sa.Integer, server_default="3"),
        sa.Column("requires_whiteboard", sa.Boolean, server_default="false"),
        sa.Column("is_follow_up", sa.Boolean, server_default="false"),
        sa.Column("parent_question_id", UUID(as_uuid=False), nullable=True),
    )
    op.create_index("ix_questions_session", "interview_questions", ["session_id"])

    # candidate_answers
    op.create_table(
        "candidate_answers",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=False), sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", UUID(as_uuid=False), sa.ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_text", sa.Text, nullable=True),
        sa.Column("skipped", sa.Boolean, server_default="false"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # answer_evaluations
    op.create_table(
        "answer_evaluations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("answer_id", UUID(as_uuid=False), sa.ForeignKey("candidate_answers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("criterion_scores", JSONB, nullable=False),
        sa.Column("overall_score", sa.Float, nullable=False),
        sa.Column("concepts_demonstrated", JSONB, nullable=True),
        sa.Column("missing_concepts", JSONB, nullable=True),
        sa.Column("technical_inaccuracies", JSONB, nullable=True),
        sa.Column("evidence_from_answer", sa.Text, nullable=True),
        sa.Column("evaluator_feedback", sa.Text, nullable=True),
        sa.Column("evaluator_confidence", sa.String(20), nullable=True),
        sa.Column("evaluator_uncertainty", sa.Text, nullable=True),
        sa.Column("recommended_next_action", sa.String(50), nullable=True),
        sa.Column("follow_up_reason", sa.Text, nullable=True),
        sa.Column("contradicts_resume", sa.Boolean, server_default="false"),
        sa.Column("contradiction_detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # final_reports
    op.create_table(
        "final_reports",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=False), sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("overall_score", sa.Float, nullable=True),
        sa.Column("overall_summary", sa.Text, nullable=True),
        sa.Column("competency_scores", JSONB, nullable=True),
        sa.Column("technical_strengths", JSONB, nullable=True),
        sa.Column("knowledge_gaps", JSONB, nullable=True),
        sa.Column("verified_claims", JSONB, nullable=True),
        sa.Column("unverified_claims", JSONB, nullable=True),
        sa.Column("recommended_study_areas", JSONB, nullable=True),
        sa.Column("full_report", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("final_reports")
    op.drop_table("answer_evaluations")
    op.drop_table("candidate_answers")
    op.drop_index("ix_questions_session", "interview_questions")
    op.drop_table("interview_questions")
    op.drop_index("ix_sessions_status", "interview_sessions")
    op.drop_table("interview_sessions")
    op.drop_index("ix_match_reports_resume_jd", "match_reports")
    op.drop_table("match_reports")
    op.drop_table("job_descriptions")
    op.drop_table("resumes")
