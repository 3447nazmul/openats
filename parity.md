# OpenATS Cross-Platform Score Parity Verification Report

## Executive Summary
Prior to this release, the OpenATS Python engine (`openats/engine.py`) and the browser client-side web app (`index.html` / `openats/templates/index.html`) produced divergent scores on identical inputs due to separate taxonomies, hardcoded JS skill lists, and differing preprocessing rules:
- **Historical Divergence (Sample Data):**
  - **Python Engine:** 75.9% (Keyword: 73.5%, Skills: 75.0%, Structure: 95.0%, STAR Impact: 50.0%)
  - **Browser JS:** 85.0% (Keyword: 85.0%, Skills: 83.0%, Structure: 90.0%, STAR Impact: 77.0%)
  - **Discrepancy:** ~9.1% total match drift!

Following the architecture alignment:
- The Python taxonomy (`openats/taxonomy.py`) is the **single source of truth** (1,344+ skills, 143 aliases, standardized sections, action verbs, and tech symbol preservation).
- `scripts/build_web_data.py` exports this taxonomy to `openats/templates/skills.json` and embeds it directly into `index.html` and `openats/templates/index.html`.
- The JavaScript engine (`scripts/parity_engine.js`) mirrors every algorithmic step of the Python engine:
  - Tech symbol protection (`C++`, `C#`, `.NET`, `Node.js`, `CI/CD`)
  - Bidirectional alias resolution (`aws` <-> `amazon web services`, `k8s` <-> `kubernetes`, etc.)
  - N-gram deduplication and longest-match filtering
  - Granular structure compliance scoring (base 20 + contact + sections + bullets + word count)
  - STAR impact metrics detection using standard action verbs and metric regex patterns
  - Multi-factor scoring weights: 40% keyword, 30% skills, 20% structure, 10% STAR impact.

---

## 🎯 Verified Score Parity Matrix
Tested on canonical input pair (`sample_data/sample_resume.txt` vs `sample_data/sample_job_desc.txt`):

| Scoring Factor | Weight | Python Engine | Browser JS App | Discrepancy (Δ) | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Keyword Overlap** | 40% | **72.3%** | **72.3%** | **0.0%** | ✅ Exact Parity |
| **Skills Coverage** | 30% | **78.1%** | **78.1%** | **0.0%** | ✅ Exact Parity |
| **Structure Compliance** | 20% | **95.0%** | **95.0%** | **0.0%** | ✅ Exact Parity |
| **STAR Metric Impact** | 10% | **50.0%** | **50.0%** | **0.0%** | ✅ Exact Parity |
| **Overall ATS Match** | **100%** | **76.3%** | **76.3%** | **0.0%** | **✅ 100% Exact Match** |

*Score Tier:* **Strong Match** (76.3%) across both platforms.  
*Matched Keywords Count:* **27** vs **27** (Exact match)  
*Missing Keywords Count:* **8** vs **8** (Exact match)

---

## 🛠️ Regeneration & Verification Workflow

### 1. Rebuild Web Taxonomy & Sync HTML
Whenever skills, aliases, or action verbs are updated in `openats/taxonomy.py`:
```bash
python3 scripts/build_web_data.py
```
This updates:
1. `openats/templates/skills.json` (standalone JSON format)
2. `index.html` (embedded 100% client-side web application)
3. `openats/templates/index.html` (server template, kept identical)

### 2. Verify Cross-Platform Parity
To assert that Python and JavaScript engines produce equal results:
```bash
node scripts/parity_check.js
```

### 3. Run Comprehensive QC Suite
Run the full automated QC test runner (including parity, server, and engine tests):
```bash
python3 run_qc_suite.py
```
