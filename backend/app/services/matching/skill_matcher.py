"""
Skill matching: exact, fuzzy (RapidFuzz), and alias-aware matching.
Does NOT use semantic similarity — that's handled by semantic_matcher.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process as rfprocess

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Skill Alias Dictionary ───────────────────────────────────────────────────
# Maps canonical name → set of known aliases/variants.
# Prevents treating JS and TypeScript as identical (they're related but different).

SKILL_ALIASES: Dict[str, List[str]] = {
    "python": ["py", "python3", "python 3"],
    "javascript": ["js", "javascript es6", "es6", "es2015"],
    "typescript": ["ts", "typescript 5"],
    "react": ["reactjs", "react.js", "react js"],
    "vue": ["vuejs", "vue.js", "vue js", "vue 3"],
    "angular": ["angularjs", "angular.js", "angular 2", "angular 14"],
    "node.js": ["nodejs", "node js", "node"],
    "fastapi": ["fast api", "fast-api"],
    "postgresql": ["postgres", "pg", "psql", "postgresql 15"],
    "mysql": ["my sql", "mysql 8"],
    "mongodb": ["mongo", "mongo db"],
    "redis": ["redis cache"],
    "docker": ["docker container", "docker containers"],
    "kubernetes": ["k8s", "k 8s", "kube"],
    "aws": ["amazon web services", "amazon aws"],
    "gcp": ["google cloud", "google cloud platform", "google gcp"],
    "azure": ["microsoft azure", "ms azure"],
    "machine learning": ["ml", "machine learning ml"],
    "deep learning": ["dl", "deep learning dl"],
    "natural language processing": ["nlp", "natural language processing nlp"],
    "computer vision": ["cv", "computer vision cv"],
    "tensorflow": ["tf", "tensorflow 2"],
    "pytorch": ["torch", "py torch"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "pandas": ["pd", "pandas dataframe"],
    "numpy": ["np", "numpy array"],
    "langchain": ["lang chain"],
    "langgraph": ["lang graph"],
    "git": ["github", "gitlab", "version control"],
    "ci/cd": ["cicd", "ci cd", "continuous integration", "continuous deployment"],
    "rest api": ["rest", "restful", "restful api", "rest apis"],
    "graphql": ["graph ql"],
    "sql": ["structured query language"],
    "java": ["java 17", "java 11", "java 8"],
    "spring": ["spring boot", "spring framework"],
    "c++": ["cpp", "c plus plus"],
    "c#": ["csharp", "c sharp", ".net"],
}

# Build reverse alias map: alias → canonical
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for canonical, aliases in SKILL_ALIASES.items():
    _ALIAS_TO_CANONICAL[canonical] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical


class MatchStatus(str, Enum):
    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"   # set by semantic_matcher
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


@dataclass
class SkillMatchResult:
    jd_skill: str
    status: MatchStatus
    matched_to: Optional[str] = None          # what resume skill it matched
    evidence: Optional[str] = None            # resume excerpt
    confidence: float = 0.0                   # 0-1
    fuzzy_score: Optional[int] = None         # rapidfuzz score
    notes: Optional[str] = None


def normalize(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return " ".join(text.lower().strip().split())


def canonicalize(skill: str) -> str:
    """Map skill to its canonical name via alias dict."""
    norm = normalize(skill)
    return _ALIAS_TO_CANONICAL.get(norm, norm)


class SkillMatcher:
    """
    Performs exact + alias + fuzzy skill matching.
    Thresholds are configurable via settings.
    """

    def __init__(self, threshold: int = None):
        self.threshold = threshold or settings.FUZZY_MATCH_THRESHOLD

    def match_skills(
        self,
        jd_skills: List[str],
        resume_skills: List[str],
        resume_skill_evidence: Optional[Dict[str, str]] = None,
    ) -> List[SkillMatchResult]:
        """
        Match each JD skill against resume skills.
        Returns one SkillMatchResult per JD skill.
        """
        # Build canonical resume skill set
        canonical_resume = {canonicalize(s): s for s in resume_skills}
        resume_evidence = resume_skill_evidence or {}

        results: List[SkillMatchResult] = []

        for jd_skill in jd_skills:
            result = self._match_one(jd_skill, canonical_resume, resume_evidence)
            results.append(result)

        return results

    def _match_one(
        self,
        jd_skill: str,
        canonical_resume: Dict[str, str],  # canonical → original resume skill
        resume_evidence: Dict[str, str],
    ) -> SkillMatchResult:
        jd_norm = normalize(jd_skill)
        jd_canonical = canonicalize(jd_skill)

        # 1. Exact canonical match
        if jd_canonical in canonical_resume:
            original = canonical_resume[jd_canonical]
            return SkillMatchResult(
                jd_skill=jd_skill,
                status=MatchStatus.EXACT if jd_norm == jd_canonical else MatchStatus.ALIAS,
                matched_to=original,
                evidence=resume_evidence.get(original.lower()),
                confidence=1.0,
            )

        # 2. Fuzzy match against canonical resume skills
        if canonical_resume:
            best_match, score, _ = rfprocess.extractOne(
                jd_canonical,
                list(canonical_resume.keys()),
                scorer=fuzz.token_set_ratio,
            ) or (None, 0, None)

            if best_match and score >= self.threshold:
                original = canonical_resume[best_match]
                return SkillMatchResult(
                    jd_skill=jd_skill,
                    status=MatchStatus.FUZZY,
                    matched_to=original,
                    evidence=resume_evidence.get(original.lower()),
                    confidence=score / 100,
                    fuzzy_score=score,
                    notes=f"Fuzzy match (score={score}): '{jd_skill}' → '{original}'",
                )

            # Ambiguous if close but not over threshold
            if best_match and score >= self.threshold - 15:
                return SkillMatchResult(
                    jd_skill=jd_skill,
                    status=MatchStatus.AMBIGUOUS,
                    matched_to=best_match,
                    confidence=score / 100,
                    fuzzy_score=score,
                    notes=f"Low-confidence fuzzy match (score={score}): verify manually",
                )

        return SkillMatchResult(jd_skill=jd_skill, status=MatchStatus.NOT_FOUND, confidence=0.0)

    def compute_coverage(
        self, results: List[SkillMatchResult], mandatory_only: bool = False
    ) -> Tuple[float, int, int]:
        """
        Returns (coverage_ratio, matched_count, total_count).
        A match is counted if status is EXACT, ALIAS, FUZZY, or SEMANTIC.
        """
        matched_statuses = {MatchStatus.EXACT, MatchStatus.ALIAS, MatchStatus.FUZZY, MatchStatus.SEMANTIC}
        matched = sum(1 for r in results if r.status in matched_statuses)
        total = len(results)
        ratio = matched / total if total > 0 else 0.0
        return ratio, matched, total
