"""
Unit and integration tests for openats/extract.py and CLI PDF/DOCX extraction.
Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openats.extract import (
    extract_text,
    ExtractionError,
    MAX_FILE_SIZE_BYTES,
    _extract_docx_stdlib,
)
from openats.cli import main as cli_main

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURES_DIR = os.path.join(REPO_ROOT, "tests", "fixtures")


class TestDocumentExtraction(unittest.TestCase):
    """Tests for PDF, DOCX, TXT, and MD extraction and validation rules."""

    def setUp(self):
        self.pdf_fixture = os.path.join(FIXTURES_DIR, "resume.pdf")
        self.scanned_pdf_fixture = os.path.join(FIXTURES_DIR, "scanned_empty.pdf")
        self.docx_fixture = os.path.join(FIXTURES_DIR, "resume.docx")
        self.sample_jd = os.path.join(REPO_ROOT, "sample_data", "sample_job_desc.txt")

    def test_pdf_extraction_finds_email_and_skills(self):
        """PDF text extraction finds candidate email, headings, and technical skills."""
        try:
            import pypdf
        except ImportError:
            try:
                import pdfplumber
            except ImportError:
                self.skipTest("Optional PDF library (pypdf/pdfplumber) not installed.")
        text = extract_text(self.pdf_fixture)
        self.assertIn("alex.rivera@example.com", text)
        self.assertIn("Python", text)
        self.assertIn("FastAPI", text)
        self.assertIn("PostgreSQL", text)
        self.assertIn("Kubernetes", text)

    def test_docx_extraction_finds_headings_and_table_rows(self):
        """DOCX extraction finds section headings and joins table cells with ' | '."""
        text = extract_text(self.docx_fixture)
        self.assertIn("PROFESSIONAL SUMMARY", text)
        self.assertIn("TECHNICAL SKILLS", text)
        self.assertIn("WORK EXPERIENCE", text)
        self.assertIn("EDUCATION", text)
        self.assertIn("Certification | AWS Certified Solutions Architect", text)

    def test_docx_stdlib_fallback_zero_dependencies(self):
        """Verify stdlib DOCX parser works directly on raw bytes without python-docx."""
        with open(self.docx_fixture, "rb") as f:
            raw_bytes = f.read()
        text = _extract_docx_stdlib(raw_bytes)
        self.assertIn("alex.rivera@example.com", text)
        self.assertIn("WORK EXPERIENCE", text)
        self.assertIn("Certification | AWS Certified Solutions Architect", text)

    def test_scanned_or_empty_pdf_raises_clear_error(self):
        """Scanned/image-only PDFs (< 20 words) raise the exact required OCR message."""
        with self.assertRaises(ExtractionError) as ctx:
            extract_text(self.scanned_pdf_fixture)
        self.assertEqual(
            str(ctx.exception),
            "No readable text found. This PDF looks scanned; use OCR or paste the text."
        )

    def test_unsupported_extension_raises_clear_error(self):
        """Unsupported file extensions raise a clear error listing supported formats."""
        with self.assertRaises(ExtractionError) as ctx:
            extract_text(b"MZ_fake_binary_content", filename="bad.exe")
        msg = str(ctx.exception)
        self.assertIn("Unsupported file format '.exe'", msg)
        for ext in (".txt", ".md", ".pdf", ".docx"):
            self.assertIn(ext, msg)

    def test_file_size_limit_15mb_enforced(self):
        """Files larger than 15 MB are rejected with a clear size limit error."""
        oversized_bytes = b"a" * (MAX_FILE_SIZE_BYTES + 1024)
        with self.assertRaises(ExtractionError) as ctx:
            extract_text(oversized_bytes, filename="huge_resume.txt")
        self.assertIn("15 MB", str(ctx.exception))

    def test_missing_pdf_adapters_raises_install_command_error(self):
        """When no PDF library is installed, raise an error naming pip install \"openats[pdf]\"."""
        with open(self.pdf_fixture, "rb") as f:
            pdf_bytes = f.read()

        with patch.dict(sys.modules, {"pypdf": None, "pdfplumber": None, "PyPDF2": None}):
            with self.assertRaises(ExtractionError) as ctx:
                extract_text(pdf_bytes, filename="resume.pdf")
            self.assertIn('pip install "openats[pdf]"', str(ctx.exception))

    def test_cli_accepts_pdf_and_docx_and_rejects_bad_ext(self):
        """CLI returns 0 on valid PDF/DOCX inputs and exits non-zero on unsupported files."""
        import io, json
        from contextlib import redirect_stdout, redirect_stderr

        buf_pdf = io.StringIO()
        with redirect_stdout(buf_pdf):
            code_pdf = cli_main(["--resume", self.pdf_fixture, "--jd", self.sample_jd, "--json"])
        self.assertEqual(code_pdf, 0)
        pdf_json = json.loads(buf_pdf.getvalue())
        self.assertEqual(pdf_json["final_score"], 76.3)

        buf_docx = io.StringIO()
        with redirect_stdout(buf_docx):
            code_docx = cli_main(["--resume", self.docx_fixture, "--jd", self.sample_jd, "--json"])
        self.assertEqual(code_docx, 0)
        docx_json = json.loads(buf_docx.getvalue())
        self.assertEqual(docx_json["final_score"], 76.3)

        bad_path = os.path.join(FIXTURES_DIR, "bad.exe")
        try:
            with open(bad_path, "wb") as f:
                f.write(b"fake binary")
            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                code_bad = cli_main(["--resume", bad_path, "--jd", self.sample_jd])
            self.assertNotEqual(code_bad, 0)
            self.assertIn("Unsupported file format", err_buf.getvalue())
        finally:
            if os.path.exists(bad_path):
                os.remove(bad_path)


if __name__ == "__main__":
    unittest.main()
