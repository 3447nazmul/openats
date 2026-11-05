"""
Unit and integration tests for openats/format_audit.py and format simulation checks.
Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""

import os
import sys
import unittest
import io
import json
from contextlib import redirect_stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openats.format_audit import (
    audit_pdf_format,
    audit_docx_format,
    audit_text_format,
    audit_resume_format,
    DISCLAIMER,
)
from openats.cli import main as cli_main

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURES_DIR = os.path.join(REPO_ROOT, "tests", "fixtures")


class TestFormatAuditSimulation(unittest.TestCase):
    """Tests for layout simulation, multi-column, table, and text false-alarm avoidance."""


    def _check_pdf_installed(self):
        try:
            import pypdf
        except ImportError:
            try:
                import pdfplumber
            except ImportError:
                self.skipTest("Optional PDF library (pypdf/pdfplumber) not installed.")

    def setUp(self):
        self.multi_col_pdf = os.path.join(FIXTURES_DIR, "multi_column.pdf")
        self.clean_pdf = os.path.join(FIXTURES_DIR, "resume.pdf")
        self.docx_table = os.path.join(FIXTURES_DIR, "resume.docx")
        self.scanned_pdf = os.path.join(FIXTURES_DIR, "scanned_empty.pdf")
        self.sample_jd = os.path.join(REPO_ROOT, "sample_data", "sample_job_desc.txt")

    def test_multi_column_pdf_triggers_columns_finding(self):
        """Multi-column PDF layout triggers a high-severity multi_column finding."""
        self._check_pdf_installed()
        findings = audit_pdf_format(self.multi_col_pdf)
        col_findings = [f for f in findings if f["type"] == "multi_column"]
        self.assertGreaterEqual(len(col_findings), 1)
        self.assertEqual(col_findings[0]["severity"], "high")
        self.assertIn("single-column", col_findings[0]["fix"].lower())

    def test_table_docx_triggers_table_finding(self):
        """Word document with tables triggers a high-severity table_detected finding."""
        findings = audit_docx_format(self.docx_table)
        tbl_findings = [f for f in findings if f["type"] == "table_detected"]
        self.assertGreaterEqual(len(tbl_findings), 1)
        self.assertEqual(tbl_findings[0]["severity"], "high")
        self.assertIn("bullet points", tbl_findings[0]["fix"].lower())

    def test_built_database_tables_produces_no_table_finding(self):
        """CRITICAL REGRESSION TEST: The sentence 'Built database tables for reporting.' produces NO table finding."""
        sample_text = (
            "EXPERIENCE\n"
            "Senior Backend Engineer at TechCorp\n"
            "• Built database tables for reporting and high-volume data analytics.\n"
            "• Handled HTTP headers in custom API authentication middleware.\n"
            "• Created footer navigation components in React.\n"
            "EDUCATION\n"
            "B.S. in Computer Science"
        )
        findings = audit_text_format(sample_text)
        table_findings = [f for f in findings if f["type"] == "table_detected"]
        self.assertEqual(
            len(table_findings),
            0,
            f"False positive table finding triggered for normal text: {table_findings}"
        )

    def test_clean_single_column_pdf_triggers_zero_high_severity_findings(self):
        """Clean single-column resume PDF produces zero high-severity layout findings."""
        self._check_pdf_installed()
        findings = audit_pdf_format(self.clean_pdf)
        high_severity = [f for f in findings if f["severity"] == "high"]
        self.assertEqual(
            len(high_severity),
            0,
            f"Clean single-column PDF triggered high-severity warnings: {high_severity}"
        )

    def test_scanned_empty_pdf_triggers_scanned_finding(self):
        """Scanned or low-word PDF triggers a scanned_image finding."""
        self._check_pdf_installed()
        findings = audit_pdf_format(self.scanned_pdf)
        scanned_findings = [f for f in findings if f["type"] == "scanned_image"]
        self.assertGreaterEqual(len(scanned_findings), 1)
        self.assertEqual(scanned_findings[0]["severity"], "high")

    def test_disclaimer_present_in_audit_resume_format(self):
        """Verify the exact honest disclaimer is included in the format audit result."""
        res = audit_resume_format(self.clean_pdf)
        self.assertIn("disclaimer", res)
        self.assertEqual(res["disclaimer"], DISCLAIMER)
        self.assertIn("simulates common ATS parsing risks", res["disclaimer"])

    def test_cli_prints_format_warnings_for_pdf(self):
        """CLI automatically runs format audit and prints 'Format & Parsing Simulation Warnings' for PDF input."""
        self._check_pdf_installed()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["--resume", self.multi_col_pdf, "--jd", self.sample_jd])
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("Format & Parsing Simulation Warnings", output)
        self.assertIn("[HIGH]", output)
        self.assertIn("Multi-column layout detected", output)
        self.assertIn("simulates common ATS parsing risks", output)

    def test_cli_format_check_flag_for_text(self):
        """CLI --format-check flag enables format audit on plain text input."""
        sample_resume_txt = os.path.join(REPO_ROOT, "sample_data", "sample_resume.txt")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["--resume", sample_resume_txt, "--jd", self.sample_jd, "--format-check"])
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("Format & Parsing Simulation Warnings", output)
        self.assertIn("Clean layout!", output)


if __name__ == "__main__":
    unittest.main()
