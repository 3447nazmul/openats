import os
import sys
import unittest
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openats.star_enhancer import (
    analyze_bullet_point,
    generate_heuristic_rewrites,
    batch_analyze_bullets,
)

class TestSTARBulletEnhancer(unittest.TestCase):
    """Section 4: Algorithmic STAR Bullet Point Enhancer Tests."""

    def test_empty_bullet_handling(self):
        res = analyze_bullet_point("")
        self.assertEqual(res["score"], 0)
        self.assertFalse(res["has_action_verb"])
        self.assertFalse(res["has_metric"])
        self.assertEqual(len(res["suggested_rewrites"]), 0)

    def test_single_word_bullet(self):
        res = analyze_bullet_point("Engineered")
        self.assertEqual(res["score"], 0)
        self.assertIn("too short", res["feedback"][0].lower())

    def test_weak_opener_detection(self):
        bullet = "Responsible for building the user interface in React."
        res = analyze_bullet_point(bullet)
        self.assertEqual(res["weak_opener_detected"], "responsible for")
        self.assertFalse(res["has_metric"])
        self.assertEqual(len(res["suggested_rewrites"]), 2)
        # Rewrite should not start with 'responsible for'
        for rw in res["suggested_rewrites"]:
            self.assertFalse(rw.lower().startswith("responsible for"))

    def test_high_impact_bullet(self):
        bullet = "Architected and deployed microservices backend using FastAPI, reducing p99 latency by 45% for 10M+ users."
        res = analyze_bullet_point(bullet)
        self.assertTrue(res["has_action_verb"])
        self.assertTrue(res["has_metric"])
        self.assertGreaterEqual(res["score"], 90)
        self.assertEqual(res["action_verb"], "architected")

    def test_quantifiable_metrics_detection(self):
        test_cases = [
            ("Improved speed by 35%", True),
            ("Cut operational cost by $50,000 annually", True),
            ("Served 5M+ daily requests with 99.9% uptime", True),
            ("Reduced build times from 45 minutes to 8 minutes", True),
            ("Achieved 3x throughput increase across 12 nodes", True),
            ("Worked on some basic tasks without numbers", False),
        ]
        for bullet, expected in test_cases:
            res = analyze_bullet_point(bullet)
            self.assertEqual(
                res["has_metric"], expected,
                f"Failed for bullet: '{bullet}', got has_metric={res['has_metric']}",
            )

    def test_automated_heuristic_rewrites_count(self):
        bullet = "Worked on database maintenance and query tuning."
        rewrites = generate_heuristic_rewrites(bullet, has_verb=False, has_metric=False)
        self.assertEqual(len(rewrites), 2)
        for rw in rewrites:
            self.assertTrue(len(rw) > len(bullet))

    def test_batch_analyze_bullets(self):
        bullets = [
            "Architected scalable Kafka streaming pipeline handling 500K msgs/sec.",
            "Responsible for writing unit tests.",
            "Reduced cloud infrastructure costs by $120K through AWS reservation planning.",
            "Assisted in sprint retrospectives.",
        ]
        batch = batch_analyze_bullets(bullets)
        self.assertEqual(batch["total_bullets"], 4)
        self.assertGreaterEqual(batch["bullets_with_action_verbs"], 2)
        self.assertGreaterEqual(batch["bullets_with_metrics"], 2)
        self.assertGreater(batch["average_score"], 0)
        self.assertEqual(len(batch["analyses"]), 4)


class TestWeakOpenerGrammaticalRewrites(unittest.TestCase):
    """Exhaustive tests for weak opener rewrite grammar and metric placeholder handling."""

    def setUp(self):
        # 10 diverse weak opener cases covering all patterns
        self.test_cases = [
            # 1. worked on + gerund (prompt required example)
            (
                "Worked on building the front-end user dashboard in React",
                "the front-end user dashboard in React",
                "Built the front-end user dashboard in React"
            ),
            # 2. responsible for + gerund (prompt required example)
            (
                "Responsible for managing social media accounts and helping with campaigns",
                "social media accounts and helping with campaigns",
                "Managed social media accounts and helping with campaigns"
            ),
            # 3. helped with + gerund (prompt required example)
            (
                "Helped with resolving tickets",
                "tickets",
                "Resolved tickets with the support team"
            ),
            # 4. assisted in + gerund
            (
                "Assisted in developing automated test suites with PyTest",
                "automated test suites with PyTest",
                "Developed automated test suites with PyTest"
            ),
            # 5. tasked with + gerund
            (
                "Tasked with creating RESTful APIs using FastAPI",
                "RESTful APIs using FastAPI",
                "Created RESTful APIs using FastAPI"
            ),
            # 6. handled + gerund
            (
                "Handled deploying microservices to AWS EKS",
                "microservices to AWS EKS",
                "Deployed microservices to AWS EKS"
            ),
            # 7. duties included + gerund
            (
                "Duties included maintaining PostgreSQL databases",
                "PostgreSQL databases",
                "Maintained PostgreSQL databases"
            ),
            # 8. involved in + gerund
            (
                "Involved in designing system architecture for high concurrency",
                "system architecture for high concurrency",
                "Designed system architecture for high concurrency"
            ),
            # 9. participated in + gerund
            (
                "Participated in optimizing Redis caching layer",
                "Redis caching layer",
                "Optimized Redis caching layer"
            ),
            # 10. was part of + gerund
            (
                "Was part of migrating legacy monolithic services to Docker",
                "legacy monolithic services to Docker",
                "Migrated legacy monolithic services to Docker"
            ),
        ]

    def test_grammatical_outputs_no_verb_plus_ing(self):
        """Assert no rewrite produces an ungrammatical 'Verb + -ing' structure."""
        verb_plus_ing_pattern = re.compile(
            r"\b(engineered|spearheaded|directed|orchestrated|delivered|built|led|developed|"
            r"managed|resolved|created|deployed|maintained|designed|optimized|migrated)\s+[a-z]+ing\b",
            re.IGNORECASE,
        )
        for bullet, object_part, expected_lead in self.test_cases:
            res = analyze_bullet_point(bullet)
            self.assertGreaterEqual(len(res["suggested_rewrites"]), 1)
            for rw in res["suggested_rewrites"]:
                match = verb_plus_ing_pattern.search(rw)
                self.assertIsNone(
                    match,
                    f"Found ungrammatical 'Verb + -ing' in rewrite '{rw}' for original bullet: '{bullet}'"
                )

    def test_original_object_preserved(self):
        """Assert that the core object of the bullet is preserved in the rewrite."""
        for bullet, object_part, expected_lead in self.test_cases:
            res = analyze_bullet_point(bullet)
            rw = res["suggested_rewrites"][0]
            self.assertIn(
                object_part,
                rw,
                f"Object '{object_part}' was dropped or mangled in rewrite: '{rw}'"
            )

    def test_prompt_mandated_examples(self):
        """Verify the exact required examples from the specification."""
        # 1. "worked on building X" -> starts with "Built X"
        b1 = "Worked on building the front-end user dashboard in React"
        r1 = analyze_bullet_point(b1)["suggested_rewrites"][0]
        self.assertTrue(r1.startswith("Built the front-end user dashboard in React"))

        # 2. "responsible for managing X" -> starts with "Managed X"
        b2 = "Responsible for managing social media accounts and helping with campaigns"
        r2 = analyze_bullet_point(b2)["suggested_rewrites"][0]
        self.assertTrue(r2.startswith("Managed social media accounts"))

        # 3. "helped with resolving tickets" -> starts with "Resolved tickets with the support team"
        b3 = "Helped with resolving tickets"
        r3 = analyze_bullet_point(b3)["suggested_rewrites"][0]
        self.assertTrue(r3.startswith("Resolved tickets with the support team"))

    def test_no_invented_metrics_and_placeholder_present(self):
        """Assert no [X]% or fake numbers are invented, and [ADD YOUR REAL RESULT: ...] is present."""
        for bullet, object_part, expected_lead in self.test_cases:
            res = analyze_bullet_point(bullet)
            for rw in res["suggested_rewrites"]:
                # Must not contain old invented metric templates
                self.assertNotIn("[X]%", rw)
                self.assertNotIn("[X]", rw)
                self.assertNotIn("improvement in efficiency", rw)
                self.assertNotIn("increase in throughput", rw)
                # Must contain the distinct user placeholder
                self.assertIn("[ADD YOUR REAL RESULT:", rw)
                self.assertIn("__%", rw)

    def test_feedback_text_contains_warning(self):
        """Assert feedback text instructs user: 'Replace the bracket with a real number from your experience. Do not guess.'"""
        for bullet, object_part, expected_lead in self.test_cases:
            res = analyze_bullet_point(bullet)
            self.assertIn(
                "Replace the bracket with a real number from your experience. Do not guess.",
                res["feedback"]
            )

    def test_scoring_ceiling_without_metrics(self):
        """Assert a bullet NEVER scores above 70 without a real quantifiable metric (40/30/30 rule)."""
        bullets_without_metrics = [b for b, _, _ in self.test_cases] + [
            "Architected microservices with FastAPI",  # Strong verb, no metric -> 70
            "Spearheaded database indexing across PostgreSQL clusters",  # Strong verb, no metric -> 70
            "Plain bullet without action verb or metric",  # 40
        ]
        for b in bullets_without_metrics:
            res = analyze_bullet_point(b)
            self.assertLessEqual(
                res["score"],
                70,
                f"Bullet without metrics scored {res['score']} (>70): '{b}'"
            )

    def test_real_metrics_preserved_unchanged(self):
        """Assert bullets that already have real numbers retain them completely unchanged with no placeholder."""
        bullet_with_metrics = "Reduced API latency by 42% through Redis caching, serving 12M users."
        res = analyze_bullet_point(bullet_with_metrics)
        self.assertEqual(len(res["suggested_rewrites"]), 1)
        rw = res["suggested_rewrites"][0]
        self.assertIn("42%", rw)
        self.assertIn("12M", rw)
        self.assertNotIn("[ADD YOUR REAL RESULT:", rw)
        self.assertGreaterEqual(res["score"], 90)


if __name__ == "__main__":
    unittest.main()
