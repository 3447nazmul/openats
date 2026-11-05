import os
import sys
import unittest
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openats.engine import (
    clean_and_tokenize,
    audit_resume_structure,
    analyze_ats_match,
)

class TestResumeStructureAudit(unittest.TestCase):
    """Section 5: Resume Structure & Section Compliance Audit Tests."""

    def test_contact_info_detection(self):
        resume = """
        Alex Rivera
        Email: alex@example.com | Phone: (555) 234-5678
        LinkedIn: linkedin.com/in/alexrivera | GitHub: github.com/alexrivera
        WORK EXPERIENCE
        • Engineered distributed pipeline.
        EDUCATION
        B.S. in CS
        SKILLS
        Python, Go
        """
        audit = audit_resume_structure(resume)
        self.assertTrue(audit["has_email"])
        self.assertTrue(audit["has_phone"])
        self.assertTrue(audit["has_links"])
        self.assertEqual(audit["email"], "alex@example.com")
        self.assertIn("Work Experience", audit["detected_sections"])
        self.assertIn("Education", audit["detected_sections"])
        self.assertIn("Skills", audit["detected_sections"])

    def test_missing_sections_and_red_flags(self):
        incomplete_resume = "Just some text without contact info or sections."
        audit = audit_resume_structure(incomplete_resume)
        self.assertFalse(audit["has_email"])
        self.assertFalse(audit["has_phone"])
        self.assertIn("Work Experience", audit["missing_sections"])
        self.assertGreater(len(audit["red_flags"]), 0)

    def test_empty_resume_audit(self):
        audit = audit_resume_structure("")
        self.assertEqual(audit["structure_score"], 0)
        self.assertEqual(len(audit["detected_sections"]), 0)
        self.assertIn("Resume text is empty.", audit["red_flags"])


class TestMultiFactorWeightedScoring(unittest.TestCase):
    """Section 6: Multi-Factor Weighted Scoring Model (0–100%) Tests."""

    def setUp(self):
        self.sample_resume = """
        Alex Rivera
        Email: alex.rivera@example.com | Phone: (555) 234-5678
        LinkedIn: linkedin.com/in/alexrivera | GitHub: github.com/alexrivera

        PROFESSIONAL SUMMARY
        Senior Software Engineer with 6+ years experience in Python, FastAPI, Docker, and AWS.

        TECHNICAL SKILLS
        • Languages: Python, Go, TypeScript, SQL
        • Frameworks: FastAPI, Django, React, Next.js
        • Databases: PostgreSQL, Redis, MongoDB
        • DevOps: Docker, Kubernetes, AWS, Terraform, CI/CD

        WORK EXPERIENCE
        Senior Backend Engineer | CloudTech | 2021 – Present
        • Architected and deployed microservices backend using FastAPI and PostgreSQL, serving 10M+ MAU.
        • Reduced p99 API latency by 45% via Redis caching layer and query indexing.
        • Spearheaded Kubernetes containerization on AWS EKS, improving deployment frequency by 60%.
        • Automated CI/CD pipelines with GitHub Actions, slashing release cycle time from 40m to 6m.

        EDUCATION
        B.S. in Computer Science | University of Technology | 2015 – 2019
        """

        self.matching_jd = """
        Senior Full Stack Engineer
        Looking for a Senior Software Engineer with strong Python and FastAPI experience.
        Required Skills:
        • Python, FastAPI, PostgreSQL, Redis
        • Docker, Kubernetes (K8s), AWS
        • Microservices architecture and CI/CD pipelines
        • Bachelor's degree in Computer Science
        """

        self.unrelated_jd = """
        Executive Pastry Chef
        Responsibilities:
        • Oversee daily bakery operations, viennoiserie, sourdough bread production.
        • Manage pastry inventory, flour sourcing, chocolate tempering, food safety standards.
        • Lead team of 8 pastry cooks. 5+ years French culinary bakery experience required.
        """

    def test_mathematical_formula_consistency(self):
        result = analyze_ats_match(self.sample_resume, self.matching_jd)
        final_score = result["final_score"]
        sub = result["sub_scores"]

        # Final_Score = (0.40 * Keyword_Match) + (0.30 * Skill_Taxonomy_Coverage)
        #             + (0.20 * Section_Structure_Score) + (0.10 * STAR_Metric_Density)
        expected = round(
            (0.40 * sub["keyword_match"]) +
            (0.30 * sub["skill_match"]) +
            (0.20 * sub["structure_compliance"]) +
            (0.10 * sub["measurable_impact"]),
            1,
        )
        self.assertAlmostEqual(final_score, expected, places=1)

    def test_scoring_bounds_always_0_to_100(self):
        result = analyze_ats_match(self.sample_resume, self.matching_jd)
        self.assertGreaterEqual(result["final_score"], 0.0)
        self.assertLessEqual(result["final_score"], 100.0)

        for name, sub in result["sub_scores"].items():
            self.assertGreaterEqual(sub, 0.0, f"Sub-score {name} < 0")
            self.assertLessEqual(sub, 100.0, f"Sub-score {name} > 100")

    def test_high_match_scores_higher_than_unrelated(self):
        matching_res = analyze_ats_match(self.sample_resume, self.matching_jd)
        unrelated_res = analyze_ats_match(self.sample_resume, self.unrelated_jd)

        self.assertGreater(matching_res["final_score"], 65.0)
        self.assertLess(unrelated_res["final_score"], 50.0)
        self.assertGreater(matching_res["final_score"], unrelated_res["final_score"] + 30.0)

    def test_empty_input_exceptions(self):
        with self.assertRaises(ValueError):
            analyze_ats_match("", self.matching_jd)

        with self.assertRaises(ValueError):
            analyze_ats_match(self.sample_resume, "")

        with self.assertRaises(ValueError):
            analyze_ats_match("   \n\t   ", "   ")

    def test_score_tier_labels(self):
        valid_tiers = [
            "Excellent Match",
            "Strong Match",
            "Moderate Match",
            "Needs Improvement",
            "Low Match (Major Gaps)",
        ]
        result = analyze_ats_match(self.sample_resume, self.matching_jd)
        self.assertIn(result["score_tier"], valid_tiers)

    def test_skill_breakdown_by_domain_structure(self):
        result = analyze_ats_match(self.sample_resume, self.matching_jd)
        breakdown = result["skill_breakdown"]
        self.assertIsInstance(breakdown, dict)

        for domain, data in breakdown.items():
            self.assertIn("matched", data)
            self.assertIn("missing", data)
            self.assertIsInstance(data["matched"], list)
            self.assertIsInstance(data["missing"], list)

    def test_recommendations_populated(self):
        result = analyze_ats_match(self.sample_resume, self.matching_jd)
        recs = result["recommendations"]
        self.assertGreater(len(recs), 0)
        self.assertIsInstance(recs, list)
        self.assertTrue(any("🌟" in r or "✅" in r or "•" in r for r in recs))




if __name__ == "__main__":
    unittest.main()
