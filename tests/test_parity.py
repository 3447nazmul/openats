"""
Unit and integration tests for cross-platform score parity (Python vs Browser JS).
Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""

import os
import sys
import json
import shutil
import subprocess
import unittest

from openats.engine import analyze_ats_match

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class TestCrossPlatformScoreParity(unittest.TestCase):
    def setUp(self):
        self.resume_path = os.path.join(REPO_ROOT, "sample_data", "sample_resume.txt")
        self.jd_path = os.path.join(REPO_ROOT, "sample_data", "sample_job_desc.txt")
        with open(self.resume_path, "r", encoding="utf-8") as f:
            self.resume_text = f.read()
        with open(self.jd_path, "r", encoding="utf-8") as f:
            self.jd_text = f.read()

    def test_python_sample_data_scores(self):
        """Verify Python engine produces exact expected scores on canonical sample data."""
        res = analyze_ats_match(self.resume_text, self.jd_text)
        self.assertEqual(res["final_score"], 76.3)
        self.assertEqual(res["score_tier"], "Strong Match")

        sub = res["sub_scores"]
        self.assertEqual(sub["keyword_match"], 72.3)
        self.assertEqual(sub["skill_match"], 78.1)
        self.assertEqual(sub["structure_compliance"], 95)
        self.assertEqual(sub["measurable_impact"], 50.0)

    def test_node_parity_runner_script(self):
        """Execute node scripts/parity_check.js to ensure exact JS-Python parity."""
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js is not installed in the environment.")

        parity_script = os.path.join(REPO_ROOT, "scripts", "parity_check.js")
        self.assertTrue(os.path.exists(parity_script), "scripts/parity_check.js missing")

        env = os.environ.copy()
        env["PYTHON"] = sys.executable
        proc = subprocess.run(
            [node_bin, parity_script],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"parity_check.js failed with code {proc.returncode}:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    def test_web_data_json_export(self):
        """Verify openats/templates/skills.json exists, is valid JSON, and contains key exports."""
        json_path = os.path.join(REPO_ROOT, "openats", "templates", "skills.json")
        self.assertTrue(os.path.exists(json_path), "skills.json missing from templates")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("SKILL_TAXONOMY", data)
        self.assertIn("ALL_SKILLS", data)
        self.assertIn("SKILL_ALIASES", data)
        self.assertIn("ACTION_VERBS", data)
        self.assertIn("STANDARD_SECTIONS", data)
        self.assertIn("TECH_SYMBOL_MAP", data)
        self.assertGreater(len(data["ALL_SKILLS"]), 1000)

    def test_templates_index_html_in_sync(self):
        """Verify openats/templates/index.html is identical to root index.html."""
        root_html = os.path.join(REPO_ROOT, "index.html")
        tmpl_html = os.path.join(REPO_ROOT, "openats", "templates", "index.html")
        self.assertTrue(os.path.exists(root_html), "root index.html missing")
        self.assertTrue(os.path.exists(tmpl_html), "openats/templates/index.html missing")

        with open(root_html, "rb") as f1, open(tmpl_html, "rb") as f2:
            self.assertEqual(f1.read(), f2.read(), "index.html and templates/index.html must be identical")

    def test_tailoring_workspace_elements_and_safety_contract(self):
        """Verify P2-2 Tailoring workspace elements, scratchpad warning, and export contracts exist in index.html."""
        root_html_path = os.path.join(REPO_ROOT, "index.html")
        with open(root_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Workspace and Editor
        self.assertIn('id="tailorModal"', html, "tailorModal missing")
        self.assertIn('id="btnReScore"', html, "btnReScore button missing")
        self.assertIn('id="btnRestoreOriginal"', html, "btnRestoreOriginal missing")
        self.assertIn('id="tailorResumeText"', html, "tailorResumeText editor missing")

        # Before/After diff card
        self.assertIn('id="diffCard"', html, "diffCard container missing")
        self.assertIn('id="diffScoreTrail"', html, "diffScoreTrail element missing")
        self.assertIn('id="diffNewList"', html, "diffNewList element missing")

        # Scratchpad and ethical warning
        self.assertIn('id="tailorScratchText"', html, "tailorScratchText textarea missing")
        self.assertIn(
            "Add a keyword to your resume only if you genuinely have that skill. Misrepresenting skills can cost you the job.",
            html,
            "Mandatory scratchpad ethical warning missing"
        )

        # Honest disclaimer and export actions
        self.assertIn(
            "Scores are readiness estimates, not a vendor ATS result.",
            html,
            "Mandatory ATS disclaimer missing"
        )
        self.assertIn('id="btnDownloadTxt"', html, "btnDownloadTxt export button missing")
        self.assertIn('id="btnDownloadMd"', html, "btnDownloadMd export button missing")


if __name__ == "__main__":
    unittest.main()
