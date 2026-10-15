"""
Interview planner: generates a structured interview plan from match analysis.
Uses Ollama LLM with structured Pydantic output.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.core.llm import call_llm_structured
from app.core.prompts import PLANNER_PROMPT, PLANNER_SYSTEM
from app.schemas.schemas import InterviewPlan

logger = logging.getLogger(__name__)


async def generate_interview_plan(
    parsed_resume: Dict[str, Any],
    parsed_jd: Dict[str, Any],
    match_report: Dict[str, Any],
    mode: str = "mixed",
    difficulty: str = "medium",
    duration_minutes: int = 30,
    max_questions: int = 12,
) -> InterviewPlan:
    """
    Generate a personalized interview plan grounded in resume and JD evidence.
    Never invents resume details.
    """
    candidate_summary = parsed_resume.get("summary", "No summary available")
    jd_analysis = json.dumps({
        "role": parsed_jd.get("role_title"),
        "domain": parsed_jd.get("domain"),
        "seniority": parsed_jd.get("seniority"),
        "technical_competencies": parsed_jd.get("technical_competencies", []),
        "required_skills": [s["name"] for s in parsed_jd.get("required_skills", [])[:10]],
    }, indent=2)

    prompt = PLANNER_PROMPT.format(
        candidate_summary=candidate_summary,
        jd_analysis=jd_analysis,
        alignment_score=match_report.get("overall_score", 0),
        matched_skills=json.dumps(
            [s["jd_skill"] for s in match_report.get("required_skills", []) if s.get("status") in ["exact", "alias", "fuzzy"]]
        ),
        unverified_claims=json.dumps(match_report.get("unverified_claims", [])),
        skill_gaps=json.dumps(match_report.get("gaps", [])),
        suggested_topics=json.dumps(match_report.get("suggested_topics", [])),
        duration_minutes=duration_minutes,
        mode=mode,
        difficulty=difficulty,
        max_questions=max_questions,
    )

    try:
        plan = await call_llm_structured(
            prompt=prompt,
            output_schema=InterviewPlan,
            system_prompt=PLANNER_SYSTEM,
        )
        logger.info(f"Generated interview plan with {len(plan.questions)} questions")
        return plan
    except Exception as e:
        logger.error(f"Interview plan generation failed: {e}")
        raise RuntimeError(f"Failed to generate interview plan: {e}") from e
