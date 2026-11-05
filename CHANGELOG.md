# Changelog

All notable changes to OpenATS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-05

### Added
- **Multi-Factor Weighted ATS Scoring Engine**: Computes compatibility (0–100%) across Keyword Overlap (40%), Skill Taxonomy Coverage (30%), Section & Heading Compliance (20%), and STAR Quantifiable Impact (10%).
- **Curated Skill Taxonomy**: Built-in dictionary containing 1,344 technical and professional skills across 8 domains, with 143 bidirectional alias mappings and tech symbol preservation (`C++`, `C#`, `.NET`, `Node.js`, `CI/CD`).
- **STAR Framework Bullet Point Enhancer**: Offline algorithmic enhancer auditing experience bullets for action verbs, quantifiable metrics, and grammatical gerund restructuring with transparent user placeholders (`[ADD YOUR REAL RESULT: e.g. reduced time by __%]`).
- **Zero-Dependency Document Text Extraction**: Native stdlib extraction for `.txt`, `.md`, and `.docx` (via OpenXML ZIP parsing), with optional adapter support for `.pdf` via `pypdf`, `pdfplumber`, or `PyPDF2`.
- **Parsing & Format Simulation Audit**: Layout risk scanner detecting multi-column layouts, table structures, and margin text in PDF and Word documents.
- **Client-Side Web Dashboard**: Interactive single-page dashboard with zero server upload, self-contained CSS, light/dark theme support, scan history (`localStorage`), and multi-job comparison (up to 3 jobs).
- **Terminal CLI & REST Server**: Python CLI with `--resume`, `--jd`, `--json`, `--bullet`, and `--format-check` options, paired with a lightweight `ThreadingHTTPServer` on localhost.

### Known Limitations
- **Language Scope**: Curated taxonomy and heuristics are currently English-only.
- **OCR**: Scanned or image-only documents require prior OCR text extraction before scanning.
- **Scoring Purpose**: Scores are heuristic readiness estimates to aid job seekers and do not replicate proprietary black-box algorithms of individual enterprise ATS vendors (Workday, Taleo, Greenhouse, Lever).
