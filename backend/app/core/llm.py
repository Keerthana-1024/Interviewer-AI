"""LLM client factory — supports Ollama, OpenAI, Anthropic, Google, and Mock providers."""
from __future__ import annotations

import json
import logging
from typing import Any, Type, TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

settings = get_settings()


def get_llm() -> BaseChatModel:
    """Return a configured LangChain chat model based on LLM_PROVIDER env var."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.LLM_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            # format="json" is set per-call when needed, not globally
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            google_api_key=settings.LLM_API_KEY,
        )

    elif provider == "mock":
        return _MockLLM()

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Use ollama|openai|anthropic|google|mock")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def call_llm_structured(
    prompt: str,
    output_schema: Type[T],
    system_prompt: str = "",
) -> T:
    """
    Call the LLM and parse the response into the given Pydantic schema.
    Retries up to 3 times on failure. Never silently returns empty data.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm()
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    logger.info(f"Calling LLM ({settings.LLM_PROVIDER}/{settings.LLM_MODEL}) with schema={output_schema.__name__}")

    try:
        response = await llm.ainvoke(messages)
        raw_text = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        raise

    # Parse JSON from response
    try:
        # Try to find JSON block if model adds extra text
        text = raw_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        return output_schema.model_validate(data)

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM response as {output_schema.__name__}: {e}\nRaw: {raw_text[:500]}")
        raise ValueError(
            f"LLM returned invalid JSON for schema {output_schema.__name__}. "
            f"Raw response (first 500 chars): {raw_text[:500]}"
        ) from e


class _MockLLM(BaseChatModel):
    """
    Mock LLM for testing without API keys.
    Returns deterministic structured JSON responses.
    CLEARLY LABELED: not a real LLM — do NOT use in production.
    """
    @property
    def _llm_type(self) -> str:
        return "mock"

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> Any:  # type: ignore[override]
        from langchain_core.outputs import ChatGeneration, ChatResult
        from langchain_core.messages import AIMessage

        # Build a deterministic response that satisfies most schemas
        mock_response = json.dumps({
            "mock": True,
            "note": "[MOCK LLM] Set LLM_PROVIDER=ollama to use the real Ollama model.",
            "skills": [
                {"name": "Python", "category": "programming", "evidence": "Mock evidence", "source_section": "Skills", "confidence": "high", "ambiguity": None},
                {"name": "FastAPI", "category": "framework", "evidence": "Mock evidence", "source_section": "Experience", "confidence": "high", "ambiguity": None}
            ],
            "experience": [{"title": "Software Engineer", "company": "Mock Corp", "duration": "2 years", "duration_months": 24, "responsibilities": ["Built APIs"], "technologies_used": ["Python"], "achievements": [], "evidence": "Mock"}],
            "projects": [{"name": "Mock Project", "description": "A test project", "technologies": ["Python"], "role": "individual", "impact": None, "evidence": "Mock"}],
            "education": [{"degree": "B.S. Computer Science", "field": "CS", "institution": "Mock University", "year": "2023", "gpa": None, "relevant_coursework": []}],
            "certifications": [],
            "summary": "[MOCK] A software engineer with Python and FastAPI experience. This is mock data.",
            # JD fields
            "role_title": "Software Engineer", "seniority": "mid", "domain": "backend engineering",
            "required_skills": [{"name": "Python", "category": "programming", "importance": "mandatory", "evidence": "Mock", "years_expected": 2}],
            "responsibilities": ["Build APIs"], "experience_years_min": 2, "experience_years_max": 5,
            "technical_competencies": ["Python", "API Design"], "behavioral_competencies": ["Communication"],
            "nice_to_have": [], "domain_knowledge_required": [],
            # Evaluation fields
            "scores": {"technical_correctness": 3, "depth_of_understanding": 3, "reasoning_and_problem_solving": 3, "relevance_to_question": 3, "specificity_and_examples": 2},
            "overall_score": 2.8, "concepts_demonstrated": ["Basic Python"], "missing_concepts": [],
            "technical_inaccuracies": [], "evidence_from_answer": "Mock evidence",
            "evaluator_feedback": "[MOCK] Good answer. Set LLM_PROVIDER=ollama for real evaluation.",
            "evaluator_confidence": "low", "evaluator_uncertainty": "Mock response",
            "recommended_next_action": "move_on", "follow_up_reason": None,
            "contradicts_resume": False, "contradiction_detail": None,
            # Plan fields
            "plan_summary": "[MOCK] Interview plan", "total_estimated_minutes": 30,
            "questions": [
                {"id": "q1", "text": "[MOCK] Tell me about your Python experience.", "type": "technical", "competency": "Python", "jd_requirement": None, "resume_claim": None, "reason": "Mock", "difficulty": "medium", "expected_answer_criteria": ["Knows Python"], "follow_up_suggestions": [], "time_allocation_minutes": 3, "requires_whiteboard": False},
                {"id": "q2", "text": "[MOCK] Describe a challenging project you worked on.", "type": "behavioral", "competency": "Problem Solving", "jd_requirement": None, "resume_claim": None, "reason": "Mock", "difficulty": "medium", "expected_answer_criteria": ["Clear example"], "follow_up_suggestions": [], "time_allocation_minutes": 4, "requires_whiteboard": False}
            ],
            # Adaptive decision
            "action": "ask_next_question", "reason": "[MOCK] Moving to next question.", "follow_up_text": None,
        })
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=mock_response))])

    async def _agenerate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> Any:  # type: ignore[override]
        return self._generate(messages, stop=stop, **kwargs)
