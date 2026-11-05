"""
Unit tests verifying fixes for:
- Alias matching (e.g. AWS, k8s <-> kubernetes)
- Nonsense phrase suppression (stack engineer, aws docker kubernetes)
- Coverage deduplication (longest match, no double counting)
- Real occurrence counts in JD (not fake 1x)
- Empty taxonomy coverage handling (N/A sentinel / None)
- PII protection (removal of raw email and phone by default)
"""

import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openats.engine import (
    analyze_ats_match,
    extract_keywords_with_frequencies,
    get_all_skill_forms,
)

class TestKeywordMatchingFixes(unittest.TestCase):

    def setUp(self):
        sample_data_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data")
        with open(os.path.join(sample_data_dir, "sample_resume.txt")) as f:
            self.sample_resume = f.read()
        with open(os.path.join(sample_data_dir, "sample_job_desc.txt")) as f:
            self.sample_jd = f.read()

    def test_aws_alias_matching(self):
        # "aws" in resume + "AWS" in JD: "aws" must be in matched_keywords, never in missing_keywords
        resume = "Senior Cloud Engineer with AWS and Python experience."
        jd = "Looking for Senior Cloud Engineer skilled in AWS and Python."
        result = analyze_ats_match(resume, jd)

        matched_names = [m["keyword"].lower() for m in result["matched_keywords"]]
        missing_names = [m["keyword"].lower() for m in result["missing_keywords"]]

        self.assertIn("aws", matched_names)
        self.assertNotIn("aws", missing_names)

        # Also verify against the real sample files
        sample_result = analyze_ats_match(self.sample_resume, self.sample_jd)
        sample_matched = [m["keyword"].lower() for m in sample_result["matched_keywords"]]
        sample_missing = [m["keyword"].lower() for m in sample_result["missing_keywords"]]

        self.assertIn("aws", sample_matched)
        self.assertNotIn("aws", sample_missing)

    def test_alias_round_trip(self):
        # Resume with "k8s" matches JD requiring "kubernetes", and vice versa
        resume_k8s = "DevOps Engineer with k8s and Docker deployment experience."
        jd_kubernetes = "Seeking DevOps Engineer with Kubernetes and Docker skills."
        result1 = analyze_ats_match(resume_k8s, jd_kubernetes)
        matched1 = [m["keyword"].lower() for m in result1["matched_keywords"]]
        self.assertTrue("kubernetes" in matched1 or "k8s" in matched1)

        resume_kubernetes = "DevOps Engineer with Kubernetes and Docker deployment experience."
        jd_k8s = "Seeking DevOps Engineer with k8s and Docker skills."
        result2 = analyze_ats_match(resume_kubernetes, jd_k8s)
        matched2 = [m["keyword"].lower() for m in result2["matched_keywords"]]
        self.assertTrue("kubernetes" in matched2 or "k8s" in matched2)

    def test_nonsense_phrases_suppression(self):
        # 'stack engineer' and 'aws docker kubernetes' must NOT appear in keywords for the sample JD
        sample_result = analyze_ats_match(self.sample_resume, self.sample_jd)
        all_keywords = (
            [m["keyword"].lower() for m in sample_result["matched_keywords"]] +
            [m["keyword"].lower() for m in sample_result["missing_keywords"]]
        )

        self.assertNotIn("stack engineer", all_keywords)
        self.assertNotIn("aws docker kubernetes", all_keywords)
        self.assertNotIn("aws docker", all_keywords)
        self.assertNotIn("docker kubernetes", all_keywords)

    def test_no_double_counting_longest_match(self):
        # 'distributed systems' matched must not also produce 'distributed' as a separate matched keyword
        sample_result = analyze_ats_match(self.sample_resume, self.sample_jd)
        matched_names = [m["keyword"].lower() for m in sample_result["matched_keywords"]]

        self.assertIn("distributed systems", matched_names)
        self.assertNotIn("distributed", matched_names)
        self.assertNotIn("systems", matched_names)

    def test_jd_count_equals_real_occurrence_count(self):
        # jd_count must equal real occurrences in JD text, not fake 1x
        sample_result = analyze_ats_match(self.sample_resume, self.sample_jd)
        for m in sample_result["missing_keywords"]:
            kw = m["keyword"]
            count = m["jd_count"]
            # Verify that count is a positive integer reflecting occurrences
            self.assertIsInstance(count, int)
            self.assertGreater(count, 0)
            # For "cloud infrastructure", it appears twice in the sample JD
            if kw == "cloud infrastructure":
                self.assertEqual(count, 2)
            if kw == "infrastructure":
                self.assertEqual(count, 2)

    def test_empty_taxonomy_coverage_returns_none_sentinel(self):
        # Empty taxonomy coverage returns None sentinel / skill_match_available = False
        resume = "Experienced team coordinator and office administrator."
        jd_no_skills = "We are seeking a reliable office worker for general filing and answering phones."
        result = analyze_ats_match(resume, jd_no_skills)

        sub = result["sub_scores"]
        self.assertFalse(sub["skill_match_available"])
        self.assertIsNone(sub["skill_match"])
        # Final score should still be a valid number between 0 and 100
        self.assertGreaterEqual(result["final_score"], 0.0)
        self.assertLessEqual(result["final_score"], 100.0)

    def test_pii_removal_by_default(self):
        # Structure audit by default omits raw email and phone values
        sample_result = analyze_ats_match(self.sample_resume, self.sample_jd, include_contact=False)
        audit = sample_result["structure_audit"]
        self.assertTrue(audit["has_email"])
        self.assertTrue(audit["has_phone"])
        self.assertNotIn("email", audit)
        self.assertNotIn("phone", audit)

        # Opt-in with include_contact=True includes them
        opt_in_result = analyze_ats_match(self.sample_resume, self.sample_jd, include_contact=True)
        opt_audit = opt_in_result["structure_audit"]
        self.assertIn("email", opt_audit)
        self.assertIn("phone", opt_audit)
        self.assertEqual(opt_audit["email"], "alex.rivera@example.com")


if __name__ == "__main__":
    unittest.main()
