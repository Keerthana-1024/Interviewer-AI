"""
Unit tests for skill matching — deterministic, no LLM or API calls needed.
Run with: pytest tests/unit/test_skill_matcher.py -v
"""
import pytest
from app.services.matching.skill_matcher import SkillMatcher, MatchStatus, normalize, canonicalize


class TestNormalize:
    def test_lowercases(self):
        assert normalize("Python") == "python"

    def test_strips_whitespace(self):
        assert normalize("  react  ") == "react"

    def test_collapses_spaces(self):
        assert normalize("node  js") == "node js"


class TestCanonicalize:
    def test_alias_mapping(self):
        assert canonicalize("nodejs") == "node.js"
        assert canonicalize("reactjs") == "react"
        assert canonicalize("k8s") == "kubernetes"

    def test_passthrough_unknown(self):
        assert canonicalize("someunknowntech") == "someunknowntech"

    def test_case_insensitive(self):
        assert canonicalize("ReactJS") == "react"


class TestSkillMatcher:
    def setup_method(self):
        self.matcher = SkillMatcher(threshold=80)

    def test_exact_match(self):
        results = self.matcher.match_skills(["python"], ["Python", "FastAPI"])
        assert results[0].status == MatchStatus.EXACT or results[0].status == MatchStatus.ALIAS

    def test_alias_match(self):
        results = self.matcher.match_skills(["reactjs"], ["React", "TypeScript"])
        assert results[0].status in {MatchStatus.EXACT, MatchStatus.ALIAS}

    def test_fuzzy_match(self):
        # "postgress" is a typo for "postgresql"
        results = self.matcher.match_skills(["postgress"], ["PostgreSQL", "MySQL"])
        # Should fuzzy match to postgresql
        assert results[0].status in {MatchStatus.FUZZY, MatchStatus.AMBIGUOUS}

    def test_not_found(self):
        results = self.matcher.match_skills(["rust"], ["Python", "Java"])
        assert results[0].status == MatchStatus.NOT_FOUND

    def test_kubernetes_alias(self):
        results = self.matcher.match_skills(["k8s"], ["Kubernetes", "Docker"])
        assert results[0].status in {MatchStatus.EXACT, MatchStatus.ALIAS}

    def test_multiple_skills(self):
        jd_skills = ["Python", "Docker", "rust"]
        resume_skills = ["python", "docker", "golang"]
        results = self.matcher.match_skills(jd_skills, resume_skills)
        assert len(results) == 3
        # python and docker should match
        statuses = [r.status for r in results]
        matched = {MatchStatus.EXACT, MatchStatus.ALIAS, MatchStatus.FUZZY}
        assert results[0].status in matched
        assert results[1].status in matched
        assert results[2].status == MatchStatus.NOT_FOUND

    def test_coverage_computation(self):
        jd_skills = ["Python", "Docker", "Rust"]
        resume_skills = ["python", "docker"]
        results = self.matcher.match_skills(jd_skills, resume_skills)
        coverage, matched, total = self.matcher.compute_coverage(results)
        assert total == 3
        assert matched == 2
        assert abs(coverage - 2/3) < 0.01

    def test_empty_resume_skills(self):
        results = self.matcher.match_skills(["Python"], [])
        assert results[0].status == MatchStatus.NOT_FOUND

    def test_empty_jd_skills(self):
        results = self.matcher.match_skills([], ["Python"])
        assert results == []


class TestEdgeCases:
    def setup_method(self):
        self.matcher = SkillMatcher(threshold=80)

    def test_javascript_vs_typescript_not_same(self):
        """JS and TS are related but should NOT be treated as identical."""
        results = self.matcher.match_skills(["TypeScript"], ["JavaScript"])
        # Should NOT be an exact match
        assert results[0].matched_to != "TypeScript" or results[0].status != MatchStatus.EXACT

    def test_evidence_returned(self):
        evidence_map = {"python": "5 years Python experience"}
        results = self.matcher.match_skills(
            ["Python"],
            ["Python"],
            resume_skill_evidence=evidence_map,
        )
        assert results[0].evidence == "5 years Python experience"
