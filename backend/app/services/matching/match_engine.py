"""
Hybrid matching engine: combines fuzzy skill matching + semantic similarity
into an interpretable alignment score with configurable weights.

Weights (configurable in settings):
  - Required skill coverage:  45%
  - Evidence strength:         25%
  - Semantic relevance:        20%
  - Experience alignment:      10%
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.matching.skill_matcher import (
    MatchStatus, SkillMatchResult, SkillMatcher,
)
from app.services.matching.semantic_matcher import semantic_skill_score

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class MatchReport:
    """Full result of the hybrid matching analysis."""
    overall_score: float = 0.0             # 0-100
    required_skill_coverage: float = 0.0  # 0-1
    preferred_skill_coverage: float = 0.0
    evidence_strength_score: float = 0.0
    semantic_relevance_score: float = 0.0
    experience_alignment_score: float = 0.0

    required_skill_results: List[SkillMatchResult] = field(default_factory=list)
    preferred_skill_results: List[SkillMatchResult] = field(default_factory=list)

    strengths: List[str] = field(default_factory=list)
    unverified_claims: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    suggested_topics: List[str] = field(default_factory=list)

    # Semantic evidence for each JD requirement
    semantic_evidence: Dict[str, List[str]] = field(default_factory=dict)

    # Weight breakdown (for explainability)
    weight_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        def skill_result_dict(r: SkillMatchResult) -> dict:
            return {
                "jd_skill": r.jd_skill,
                "status": r.status.value,
                "matched_to": r.matched_to,
                "evidence": r.evidence,
                "confidence": round(r.confidence, 3),
                "fuzzy_score": r.fuzzy_score,
                "notes": r.notes,
            }

        return {
            "overall_score": round(self.overall_score, 1),
            "required_skill_coverage": round(self.required_skill_coverage, 3),
            "preferred_skill_coverage": round(self.preferred_skill_coverage, 3),
            "evidence_strength_score": round(self.evidence_strength_score, 3),
            "semantic_relevance_score": round(self.semantic_relevance_score, 3),
            "experience_alignment_score": round(self.experience_alignment_score, 3),
            "required_skills": [skill_result_dict(r) for r in self.required_skill_results],
            "preferred_skills": [skill_result_dict(r) for r in self.preferred_skill_results],
            "strengths": self.strengths,
            "unverified_claims": self.unverified_claims,
            "gaps": self.gaps,
            "suggested_topics": self.suggested_topics,
            "weight_breakdown": self.weight_breakdown,
            "disclaimer": (
                "Scores reflect textual overlap and semantic similarity between the resume and JD. "
                "They are NOT validated predictors of job performance or hiring probability."
            ),
        }


class MatchEngine:
    """
    Orchestrates hybrid resume–JD matching.
    Never invents or fabricates evidence.
    """

    def __init__(self):
        self.skill_matcher = SkillMatcher()

    def compute_match(
        self,
        parsed_resume: Dict[str, Any],
        parsed_jd: Dict[str, Any],
        resume_sections: Dict[str, str],
    ) -> MatchReport:
        """
        Run full hybrid matching pipeline.
        Returns MatchReport with all component scores and evidence.
        """
        report = MatchReport()

        # ─── Extract resume skills + evidence ────────────────────────────────
        resume_skills = [s["name"] for s in parsed_resume.get("skills", [])]
        resume_evidence_map = {
            s["name"].lower(): s.get("evidence", "")
            for s in parsed_resume.get("skills", [])
        }

        # ─── Extract JD skill lists ───────────────────────────────────────────
        required_skills = [
            s["name"] for s in parsed_jd.get("required_skills", [])
            if s.get("importance") == "mandatory"
        ]
        preferred_skills = [
            s["name"] for s in parsed_jd.get("required_skills", [])
            if s.get("importance") == "preferred"
        ]

        # ─── 1. Fuzzy skill matching ──────────────────────────────────────────
        report.required_skill_results = self.skill_matcher.match_skills(
            required_skills, resume_skills, resume_evidence_map
        )
        report.preferred_skill_results = self.skill_matcher.match_skills(
            preferred_skills, resume_skills, resume_evidence_map
        )

        req_coverage, req_matched, req_total = self.skill_matcher.compute_coverage(
            report.required_skill_results
        )
        pref_coverage, _, _ = self.skill_matcher.compute_coverage(
            report.preferred_skill_results
        )
        report.required_skill_coverage = req_coverage
        report.preferred_skill_coverage = pref_coverage

        # ─── 2. Evidence strength score ───────────────────────────────────────
        # Average confidence of matched skills (only matched ones count)
        matched_results = [
            r for r in report.required_skill_results
            if r.status not in {MatchStatus.NOT_FOUND, MatchStatus.AMBIGUOUS}
        ]
        if matched_results:
            avg_confidence = sum(r.confidence for r in matched_results) / len(matched_results)
            report.evidence_strength_score = avg_confidence
        else:
            report.evidence_strength_score = 0.0

        # ─── 3. Semantic relevance score ──────────────────────────────────────
        jd_competencies = parsed_jd.get("technical_competencies", [])
        semantic_scores = []
        for competency in jd_competencies[:10]:  # cap for performance
            score, evidence_passages = semantic_skill_score(competency, resume_sections)
            semantic_scores.append(score)
            if evidence_passages:
                report.semantic_evidence[competency] = evidence_passages

        report.semantic_relevance_score = (
            sum(semantic_scores) / len(semantic_scores) if semantic_scores else 0.0
        )

        # ─── 4. Experience alignment ──────────────────────────────────────────
        exp_years_min = parsed_jd.get("experience_years_min") or 0
        candidate_months = sum(
            e.get("duration_months") or 0
            for e in parsed_resume.get("experience", [])
        )
        candidate_years = candidate_months / 12 if candidate_months > 0 else 0

        if exp_years_min <= 0:
            report.experience_alignment_score = 0.8  # unspecified → neutral
        elif candidate_years >= exp_years_min:
            report.experience_alignment_score = min(1.0, candidate_years / max(exp_years_min, 1))
        else:
            report.experience_alignment_score = candidate_years / exp_years_min

        # ─── 5. Weighted overall score ────────────────────────────────────────
        w_req = settings.WEIGHT_REQUIRED_SKILL_COVERAGE
        w_ev = settings.WEIGHT_EVIDENCE_STRENGTH
        w_sem = settings.WEIGHT_SEMANTIC_RELEVANCE
        w_exp = settings.WEIGHT_EXPERIENCE_ALIGNMENT

        raw = (
            report.required_skill_coverage * w_req
            + report.evidence_strength_score * w_ev
            + report.semantic_relevance_score * w_sem
            + report.experience_alignment_score * w_exp
        )
        report.overall_score = round(raw * 100, 1)  # 0-100

        report.weight_breakdown = {
            "required_skill_coverage": f"{w_req*100:.0f}% (score: {report.required_skill_coverage:.2f})",
            "evidence_strength": f"{w_ev*100:.0f}% (score: {report.evidence_strength_score:.2f})",
            "semantic_relevance": f"{w_sem*100:.0f}% (score: {report.semantic_relevance_score:.2f})",
            "experience_alignment": f"{w_exp*100:.0f}% (score: {report.experience_alignment_score:.2f})",
        }

        # ─── 6. Narrative analysis ────────────────────────────────────────────
        report.strengths = self._compute_strengths(report, parsed_resume)
        report.gaps = self._compute_gaps(report, required_skills)
        report.unverified_claims = self._compute_unverified(parsed_resume, parsed_jd)
        report.suggested_topics = self._suggest_topics(report, parsed_jd)

        return report

    def _compute_strengths(self, report: MatchReport, parsed_resume: dict) -> List[str]:
        strengths = []
        for r in report.required_skill_results:
            if r.status in {MatchStatus.EXACT, MatchStatus.ALIAS}:
                strengths.append(f"Strong match: '{r.jd_skill}' found in resume (exact/alias match)")
        for proj in parsed_resume.get("projects", []):
            if proj.get("impact"):
                strengths.append(f"Demonstrated project impact: {proj['impact'][:100]}")
        return strengths[:8]

    def _compute_gaps(self, report: MatchReport, required_skills: List[str]) -> List[str]:
        gaps = []
        for r in report.required_skill_results:
            if r.status == MatchStatus.NOT_FOUND:
                gaps.append(f"Required skill not found in resume: '{r.jd_skill}'")
            elif r.status == MatchStatus.AMBIGUOUS:
                gaps.append(f"Ambiguous match for required skill: '{r.jd_skill}' (verify in interview)")
        return gaps

    def _compute_unverified(self, parsed_resume: dict, parsed_jd: dict) -> List[str]:
        """Skills claimed on resume but not directly evidenced."""
        unverified = []
        for skill in parsed_resume.get("skills", []):
            if skill.get("confidence") == "low":
                unverified.append(
                    f"Low-confidence claim: '{skill['name']}' — {skill.get('ambiguity', 'needs verification')}"
                )
        return unverified[:6]

    def _suggest_topics(self, report: MatchReport, parsed_jd: dict) -> List[str]:
        topics = []
        # Prioritize: missing required skills → ambiguous → low evidence strengths
        for r in report.required_skill_results:
            if r.status in {MatchStatus.NOT_FOUND, MatchStatus.AMBIGUOUS}:
                topics.append(f"Verify: {r.jd_skill}")
        for comp in parsed_jd.get("technical_competencies", []):
            topics.append(f"Probe: {comp}")
        for comp in parsed_jd.get("behavioral_competencies", []):
            topics.append(f"Behavioral: {comp}")
        return topics[:10]
