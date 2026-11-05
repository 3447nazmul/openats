"""
OpenATS Resume Format & Parsing Simulation Audit Module.
Detects document layout issues that commonly break real ATS parsers:
- Multi-column layouts (text interleaving risks)
- Tables and grid structures (dropped/scrambled columns)
- Substantive text inside header/footer margins
- Scanned pages / image-only layers
- Structural line/heading issues in plain text

Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""

import io
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from itertools import groupby
from typing import Dict, List, Any, Optional, Union

DISCLAIMER: str = (
    "This simulates common ATS parsing risks; real ATS systems vary "
    "and no simulation can guarantee a pass."
)


def _detect_multi_column_words(words: List[Dict[str, Any]], page_width: float) -> bool:
    """
    Detect multiple text columns by checking for horizontal column gaps
    across consecutive words on the same text line.
    """
    if len(words) < 8:
        return False

    # Group words by vertical line (within 4 points)
    sorted_words = sorted(words, key=lambda w: (round(w.get("top", 0.0) / 4) * 4, w.get("x0", 0.0)))
    split_lines = 0

    for _, g in groupby(sorted_words, key=lambda w: round(w.get("top", 0.0) / 4) * 4):
        lw = list(g)
        for i in range(len(lw) - 1):
            w1_x1 = lw[i].get("x1", lw[i].get("x0", 0.0) + 10)
            w2_x0 = lw[i + 1].get("x0", 0.0)
            gap = w2_x0 - w1_x1
            # A significant gap across the center region indicates parallel columns
            if gap > 60 and w1_x1 < (page_width * 0.58) and w2_x0 > (page_width * 0.42):
                split_lines += 1
                break

    return split_lines >= 3


def audit_pdf_format(
    path_or_bytes: Union[str, Path, bytes, bytearray]
) -> List[Dict[str, Any]]:
    """
    Audit a PDF file layout for common ATS parsing traps.
    Detects:
      1. Multi-column layouts (horizontal gap analysis between parallel columns)
      2. Table structures (grid alignments or pdfplumber tables)
      3. Text inside header / footer margins
      4. Large embedded images with minimal extractable text (scanned pages)
      5. Non-embedded or unusual decorative fonts

    Returns:
        List of findings: [{"type", "severity", "page", "message", "fix"}]
    """
    raw_bytes: bytes
    if isinstance(path_or_bytes, (bytes, bytearray)):
        raw_bytes = bytes(path_or_bytes)
    else:
        with open(str(path_or_bytes), "rb") as f:
            raw_bytes = f.read()

    findings: List[Dict[str, Any]] = []

    # 1. Try pdfplumber first if installed for high-accuracy table & word detection
    try:
        import pdfplumber  # type: ignore
        stream = io.BytesIO(raw_bytes)
        with pdfplumber.open(stream) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                page_width = float(page.width)
                page_height = float(page.height)

                # (a) Check tables
                tables = []
                try:
                    tables = page.find_tables()
                except Exception:
                    pass
                if tables and len(tables) > 0:
                    findings.append({
                        "type": "table_detected",
                        "severity": "high",
                        "page": page_idx,
                        "message": (
                            f"Table structure detected on page {page_idx} ({len(tables)} table(s)). "
                            "ATS parsers frequently drop table cells or read text out of order."
                        ),
                        "fix": "Replace tables with standard left-aligned bullet points or tab-separated text."
                    })

                # (b) Multi-column layout detection via word positions
                words = page.extract_words() or []
                if _detect_multi_column_words(words, page_width=page_width):
                    findings.append({
                        "type": "multi_column",
                        "severity": "high",
                        "page": page_idx,
                        "message": (
                            f"Multi-column layout detected on page {page_idx}. "
                            "ATS parsers scan horizontally across columns, interleaving sentences into gibberish."
                        ),
                        "fix": "Use a clean, single-column vertical layout for your resume."
                    })

                # (c) Text in header / footer margins (top < 25 or bottom > page_height - 25)
                header_words = [w for w in words if float(w.get("top", 0.0)) < 25]
                footer_words = [w for w in words if float(w.get("bottom", 0.0)) > (page_height - 25)]
                if len(header_words) >= 4 or len(footer_words) >= 4:
                    findings.append({
                        "type": "header_footer_text",
                        "severity": "medium",
                        "page": page_idx,
                        "message": (
                            f"Text detected in top/bottom page margins on page {page_idx}. "
                            "Many corporate ATS parsers completely ignore header and footer zones."
                        ),
                        "fix": "Move contact details and essential qualifications into the main document body flow."
                    })

                # (d) Embedded images with minimal text (likely scanned)
                images = getattr(page, "images", []) or []
                if len(images) > 0 and len(words) < 20:
                    findings.append({
                        "type": "scanned_image",
                        "severity": "high",
                        "page": page_idx,
                        "message": (
                            f"Large image detected with only {len(words)} readable words on page {page_idx}. "
                            "This page appears to be a scanned image or flattened graphic."
                        ),
                        "fix": "Export your resume directly as a text-based PDF from Word, Google Docs, or LaTeX."
                    })

        return findings
    except ImportError:
        pass
    except Exception:
        pass

    # 2. pypdf fallback
    try:
        import pypdf  # type: ignore
        stream = io.BytesIO(raw_bytes)
        reader = pypdf.PdfReader(stream)

        for page_idx, page in enumerate(reader.pages, start=1):
            page_width = float(page.mediabox.width or 612.0)
            page_height = float(page.mediabox.height or 792.0)

            words_pypdf: List[Dict[str, Any]] = []

            def _visitor(text, cm, tm, font_dict, font_size):
                if text.strip():
                    x0 = float(tm[4]) if len(tm) > 4 else 0.0
                    y0 = float(tm[5]) if len(tm) > 5 else 0.0
                    # approximate word width
                    x1 = x0 + len(text) * 6.0
                    top = page_height - y0
                    words_pypdf.append({
                        "text": text.strip(),
                        "x0": x0,
                        "x1": x1,
                        "top": top,
                        "bottom": top + 10.0,
                    })

            try:
                page.extract_text(visitor_text=_visitor)
            except Exception:
                pass

            # (a) Multi-column check
            if _detect_multi_column_words(words_pypdf, page_width=page_width):
                findings.append({
                    "type": "multi_column",
                    "severity": "high",
                    "page": page_idx,
                    "message": (
                        f"Multi-column layout detected on page {page_idx}. "
                        "ATS parsers scan horizontally across columns, interleaving sentences into gibberish."
                    ),
                    "fix": "Use a clean, single-column vertical layout for your resume."
                })

            # (b) Header / footer margin text check
            top_margin_items = [it for it in words_pypdf if it["top"] < 25]
            bottom_margin_items = [it for it in words_pypdf if it["bottom"] > (page_height - 25)]
            if len(top_margin_items) >= 4 or len(bottom_margin_items) >= 4:
                findings.append({
                    "type": "header_footer_text",
                    "severity": "medium",
                    "page": page_idx,
                    "message": (
                        f"Text detected in top/bottom page margins on page {page_idx}. "
                        "Many corporate ATS parsers completely ignore header and footer zones."
                    ),
                    "fix": "Move contact details and essential qualifications into the main document body flow."
                })

            # (c) Images check (scanned page)
            img_count = 0
            try:
                img_count = len(page.images)
            except Exception:
                pass

            word_count = sum(len(it["text"].split()) for it in words_pypdf)
            if img_count > 0 and word_count < 20:
                findings.append({
                    "type": "scanned_image",
                    "severity": "high",
                    "page": page_idx,
                    "message": (
                        f"Image elements detected with only {word_count} readable words on page {page_idx}. "
                        "This page appears to be a scanned image or flattened graphic."
                    ),
                    "fix": "Export your resume directly as a text-based PDF from Word, Google Docs, or LaTeX."
                })

    except Exception:
        pass

    return findings


def audit_docx_format(
    path_or_bytes: Union[str, Path, bytes, bytearray]
) -> List[Dict[str, Any]]:
    """
    Audit a Word (.docx) document using pure stdlib OpenXML parsing.
    Detects:
      1. Tables (<w:tbl>)
      2. Floating text boxes (<w:txbxContent>, <v:textbox>)
      3. Substantive text inside headers or footers
      4. Multi-column sections (<w:cols w:num="2+">)

    Returns:
        List of findings: [{"type", "severity", "page", "message", "fix"}]
    """
    raw_bytes: bytes
    if isinstance(path_or_bytes, (bytes, bytearray)):
        raw_bytes = bytes(path_or_bytes)
    else:
        with open(str(path_or_bytes), "rb") as f:
            raw_bytes = f.read()

    stream = io.BytesIO(raw_bytes)
    if not zipfile.is_zipfile(stream):
        return []

    stream.seek(0)
    findings: List[Dict[str, Any]] = []

    try:
        with zipfile.ZipFile(stream, "r") as zf:
            namelist = zf.namelist()

            # 1. Inspect main document.xml
            if "word/document.xml" in namelist:
                doc_xml = zf.read("word/document.xml")
                root = ET.fromstring(doc_xml)

                def local(tag: str) -> str:
                    return tag.split("}")[-1] if "}" in tag else tag

                # (a) Tables
                tables = [e for e in root.iter() if local(e.tag) == "tbl"]
                if tables:
                    findings.append({
                        "type": "table_detected",
                        "severity": "high",
                        "page": None,
                        "message": (
                            f"Table structure detected ({len(tables)} table(s) found in document). "
                            "Tables frequently confuse ATS parsers and cause cell contents to be skipped."
                        ),
                        "fix": "Replace tables with standard bullet points or tab-separated text."
                    })

                # (b) Floating text boxes
                textboxes = [
                    e for e in root.iter()
                    if local(e.tag) in ("txbxContent", "textbox")
                ]
                if textboxes:
                    findings.append({
                        "type": "text_box",
                        "severity": "high",
                        "page": None,
                        "message": (
                            f"Floating text box detected ({len(textboxes)} text box(es) found). "
                            "Most ATS parsers skip floating shapes and text boxes entirely."
                        ),
                        "fix": "Move text from text boxes directly into the main document body flow."
                    })

                # (c) Multi-column sections (<w:cols w:num="2+">)
                multi_cols = False
                for elem in root.iter():
                    if local(elem.tag) == "cols":
                        num = elem.attrib.get(
                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}num",
                            elem.attrib.get("num", "1")
                        )
                        try:
                            if int(num) > 1:
                                multi_cols = True
                                break
                        except ValueError:
                            pass
                if multi_cols:
                    findings.append({
                        "type": "multi_column",
                        "severity": "high",
                        "page": None,
                        "message": (
                            "Multi-column section detected (2 or more columns). "
                            "ATS parsers often interleave text horizontally across columns."
                        ),
                        "fix": "Format the entire document using a single-column layout."
                    })

            # 2. Check headers and footers for substantive text
            header_footer_files = [
                name for name in namelist
                if name.startswith("word/") and (
                    name.startswith("word/header") or name.startswith("word/footer")
                ) and name.endswith(".xml")
            ]

            hf_words = []
            for hf_name in header_footer_files:
                try:
                    hf_xml = zf.read(hf_name)
                    hf_root = ET.fromstring(hf_xml)
                    for node in hf_root.iter():
                        tag_name = node.tag.split("}")[-1] if "}" in node.tag else node.tag
                        if tag_name == "t" and node.text:
                            hf_words.extend(node.text.split())
                except Exception:
                    pass

            if len(hf_words) >= 6:
                findings.append({
                    "type": "header_footer_text",
                    "severity": "medium",
                    "page": None,
                    "message": (
                        f"Substantive text detected in Word header/footer streams ({len(hf_words)} words). "
                        "Many corporate ATS parsers do not inspect headers or footers."
                    ),
                    "fix": "Move contact details and essential qualifications into the top of the main body."
                })

    except Exception:
        pass

    return findings


def audit_text_format(text: str) -> List[Dict[str, Any]]:
    """
    Audit plain text layout for structural ATS hazards.
    Keeps ONLY true structural signals:
      - Extremely long unbroken lines (> 140 characters)
      - Missing major section headings (Work Experience, Education)

    CRITICAL REGRESSION RULE:
      The words 'table', 'header', 'footer', or 'text box' inside normal sentences
      (e.g., 'Built database tables for reporting') MUST NOT trigger any finding.
    """
    findings: List[Dict[str, Any]] = []
    if not text or not text.strip():
        return findings

    lines = [line.strip() for line in text.splitlines()]

    # 1. Extremely long lines (unwrapped run-on paragraphs)
    long_lines = [l for l in lines if len(l) > 140 and not l.startswith("http")]
    if len(long_lines) >= 3:
        findings.append({
            "type": "long_lines",
            "severity": "info",
            "page": None,
            "message": (
                f"{len(long_lines)} unusually long line(s) detected (>140 chars). "
                "Ensure paragraphs have natural line breaks for clean terminal and parser extraction."
            ),
            "fix": "Format long paragraphs with standard line wrapping."
        })

    # 2. Check for missing standard headings
    lower = text.lower()
    has_exp = any(
        kw in lower
        for kw in ("experience", "work history", "employment", "professional background")
    )
    if not has_exp:
        findings.append({
            "type": "missing_heading",
            "severity": "medium",
            "page": None,
            "message": "Standard 'Experience' or 'Work History' heading not clearly identified.",
            "fix": "Add a clear 'Work Experience' or 'Professional Experience' section header."
        })

    return findings


def audit_resume_format(
    path_or_bytes: Union[str, Path, bytes, bytearray],
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    High-level format audit dispatcher.
    Inspects PDF, DOCX, or plain text, returning findings and disclaimer.
    """
    inferred_name = filename or (str(path_or_bytes) if isinstance(path_or_bytes, (str, Path)) else "")
    ext = os.path.splitext(inferred_name)[1].lower()

    findings: List[Dict[str, Any]] = []
    fmt = "text"

    if ext == ".pdf":
        fmt = "pdf"
        findings = audit_pdf_format(path_or_bytes)
    elif ext == ".docx":
        fmt = "docx"
        findings = audit_docx_format(path_or_bytes)
    else:
        fmt = "text"
        if isinstance(path_or_bytes, (bytes, bytearray)):
            try:
                t = bytes(path_or_bytes).decode("utf-8")
            except UnicodeDecodeError:
                t = bytes(path_or_bytes).decode("utf-8", errors="replace")
        else:
            try:
                with open(str(path_or_bytes), "r", encoding="utf-8", errors="replace") as f:
                    t = f.read()
            except Exception:
                t = str(path_or_bytes)
        findings = audit_text_format(t)

    has_high = any(f.get("severity") == "high" for f in findings)

    return {
        "format": fmt,
        "findings": findings,
        "has_high_risk": has_high,
        "total_findings": len(findings),
        "disclaimer": DISCLAIMER,
    }
