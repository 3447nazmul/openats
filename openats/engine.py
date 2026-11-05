"""
OpenATS — Core Semantic ATS Evaluation Engine.
Performs advanced text preprocessing, n-gram extraction, semantic skill matching,
multi-factor weighted scoring, section compliance audits, and STAR bullet scoring.

Scoring Formula:
  Final_Score = (0.40 * Keyword_Match) + (0.30 * Skill_Taxonomy_Coverage)
              + (0.20 * Section_Structure_Score) + (0.10 * STAR_Metric_Density)

Zero external pip dependencies — pure Python standard library.
Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""
import re
import math
from collections import Counter
from typing import Dict, List, Set, Any, Tuple, Optional

from .taxonomy import (
    SKILL_TAXONOMY, ALL_SKILLS, SKILL_ALIASES, ACTION_VERBS,
    STANDARD_SECTIONS, STOP_WORDS, BENGALI_STOP_WORDS
)
from .star_enhancer import analyze_bullet_point, batch_analyze_bullets


# ---------------------------------------------------------------------------
# Section 1: Advanced Text Preprocessing & Cleaning
# ---------------------------------------------------------------------------

# Mapping of tech symbols that must be preserved during normalization
TECH_SYMBOL_MAP = {
    "c++": "cpp_lang",
    "c#": "csharp_lang",
    ".net": "dotnet_framework",
    "node.js": "nodejs_runtime",
    "next.js": "nextjs_framework",
    "nuxt.js": "nuxtjs_framework",
    "vue.js": "vuejs_framework",
    "react.js": "reactjs_lib",
    "express.js": "expressjs_framework",
    "d3.js": "d3js_lib",
    "three.js": "threejs_lib",
    "alpine.js": "alpinejs_lib",
    "ember.js": "emberjs_framework",
    "solid.js": "solidjs_lib",
    "ci/cd": "cicd_practice",
    "tcp/ip": "tcpip_protocol",
    "rest api": "rest_api_design",
    "restful api": "restful_api_design",
    "a/b testing": "ab_testing",
}

# Reverse map to recover canonical names after tokenization
TECH_REVERSE_MAP = {v: k for k, v in TECH_SYMBOL_MAP.items()}


def _protect_tech_symbols(text: str) -> str:
    """
    Replaces special tech tokens with safe placeholders before general tokenization.
    Preserves symbols like C++, C#, .NET, CI/CD, TCP/IP, Node.js, etc.
    """
    result = text
    # Sort by length descending so longer matches are replaced first
    for symbol, placeholder in sorted(TECH_SYMBOL_MAP.items(), key=lambda x: -len(x[0])):
        # Case-insensitive replacement
        pattern = re.compile(re.escape(symbol), re.IGNORECASE)
        result = pattern.sub(placeholder, result)
    return result


def _restore_tech_symbols(token: str) -> str:
    """Restores a placeholder token back to its canonical tech name."""
    return TECH_REVERSE_MAP.get(token, token)


def clean_and_tokenize(text: str) -> List[str]:
    """
    Normalizes text and extracts word tokens.
    Preserves tech symbols (C++, .NET, CI/CD, etc.) via placeholder substitution.
    Unicode-aware — handles multi-lingual characters.
    """
    if not text or not text.strip():
        return []

    # Protect tech symbols first
    protected = _protect_tech_symbols(text.lower())

    # Tokenize: allow alphanumeric, underscores, hyphens, dots (for version numbers)
    raw_tokens = re.findall(r'(?:[^\W\d_]|[̀-᷿]|_)(?:[^\W\d_]|[̀-᷿]|\d|[\-_\.]){0,30}', protected)

    # Clean up trailing punctuation before restoring tech symbols
    tokens = []
    for token in raw_tokens:
        cleaned_tok = token.rstrip(".-")
        restored = _restore_tech_symbols(cleaned_tok)
        if restored and len(restored) >= 1:
            tokens.append(restored)

    return tokens



def normalize_skill(skill: str) -> str:
    """
    Normalizes a skill string by checking aliases and applying stemming.
    Returns the canonical form from the taxonomy if possible.
    """
    lower = skill.lower().strip()

    # Check aliases first to resolve to canonical taxonomy name
    if lower in SKILL_ALIASES:
        return SKILL_ALIASES[lower]

    # Direct match in taxonomy
    if lower in ALL_SKILLS:
        return lower

    return lower


# ---------------------------------------------------------------------------
# Section 2: N-Gram & Semantic Phrase Extraction
# ---------------------------------------------------------------------------

def extract_ngrams(tokens: List[str], n: int) -> List[str]:
    """Extracts n-grams (phrases of length n) from a token list."""
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def _levenshtein_distance(s1: str, s2: str) -> int:
    """
    Computes the Levenshtein edit distance between two strings.
    Used for fuzzy skill matching with tolerance of 1.
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))

    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _fuzzy_skill_match(token: str, skill_set: Dict[str, str], max_distance: int = 1) -> Optional[str]:
    """
    Attempts to fuzzy-match a token against the skill taxonomy.
    Returns the matched skill name if edit distance <= max_distance, else None.
    Only attempts fuzzy matching for tokens of length >= 4 to avoid false positives.
    """
    if len(token) < 4:
        return None

    for skill in skill_set:
        if abs(len(token) - len(skill)) > max_distance:
            continue
        if _levenshtein_distance(token, skill) <= max_distance:
            return skill

    return None



def get_all_skill_forms(term: str) -> Set[str]:
    """
    Returns all recognized variations of a skill or keyword:
    the original term, its canonical taxonomy form, and any aliases.
    e.g. 'aws' -> {'aws', 'amazon web services'}
         'k8s' -> {'k8s', 'kubernetes'}
         'postgres' -> {'postgres', 'postgresql'}
    """
    t_clean = term.lower().strip()
    forms = {t_clean}
    canonical = SKILL_ALIASES.get(t_clean, t_clean)
    forms.add(canonical.lower())
    for alias, target in SKILL_ALIASES.items():
        if target.lower() == canonical.lower():
            forms.add(alias.lower())
    if canonical.lower() in SKILL_ALIASES:
        forms.add(SKILL_ALIASES[canonical.lower()].lower())
    for f in list(forms):
        if "." in f:
            forms.add(f.replace(".", ""))
            forms.add(f.replace(".", " "))
    return forms


def is_skill_or_alias(token: str) -> bool:
    """Checks if a single token exists in skill taxonomy or aliases."""
    t = token.lower().strip()
    return t in ALL_SKILLS or t in SKILL_ALIASES


def is_skill_concatenation(phrase: str) -> bool:
    """
    Checks if an n-gram is merely an artificial concatenation of adjacent single skills
    (e.g., 'aws docker', 'docker kubernetes', 'aws docker kubernetes') where the phrase
    itself is not a recognized standalone skill.
    """
    p_lower = phrase.lower().strip()
    if p_lower in ALL_SKILLS:
        return False
    words = p_lower.split()
    if len(words) < 2:
        return False
    return all(is_skill_or_alias(w) for w in words)


def is_job_title_fragment(phrase: str, title_line: str) -> bool:
    """
    Checks if an n-gram is a fragment of the job title line (e.g. 'stack engineer', 'full stack')
    and not an actual technical skill in the taxonomy.
    """
    p_lower = phrase.lower().strip()
    if p_lower in ALL_SKILLS:
        return False
    if title_line and p_lower in title_line.lower():
        return True
    words = p_lower.split()
    role_words = {
        "engineer", "developer", "architect", "manager", "director", "consultant",
        "analyst", "specialist", "intern", "associate", "candidate", "role", "position"
    }
    if any(w in role_words for w in words):
        return True
    return False


def count_occurrences_in_text(term: str, text_lower: str) -> int:
    """Counts real occurrences of a keyword and its alias forms in text."""
    forms = get_all_skill_forms(term)
    cnt = 0
    for f in forms:
        try:
            cnt += len(re.findall(r"\b" + re.escape(f) + r"\b", text_lower))
        except re.error:
            cnt += text_lower.count(f)
    if cnt == 0:
        cnt = text_lower.count(term.lower())
    return max(1, cnt)


def extract_keywords_with_frequencies(text: str, top_k: int = 40) -> List[Tuple[str, float]]:
    """
    Extracts high-value keywords and key phrases (unigrams, bigrams, trigrams)
    from text with normalized TF and inverse heuristic importance weighting.
    Filters out nonsense concatenations and title fragments.
    """
    if not text or not text.strip():
        return []

    first_line = next((l.strip().lower() for l in text.splitlines() if l.strip()), "")

    tokens = clean_and_tokenize(text)
    is_bengali = bool(re.search(r'[ঀ-৿]', text))
    active_stop_words = STOP_WORDS | BENGALI_STOP_WORDS if is_bengali else STOP_WORDS
    meaningful_tokens = [t for t in tokens if t.lower() not in active_stop_words and len(t) > 1]

    if not meaningful_tokens:
        return []

    unigram_counts = Counter(meaningful_tokens)
    bigrams = extract_ngrams(meaningful_tokens, 2)
    trigrams = extract_ngrams(meaningful_tokens, 3)

    # Filter bigrams: keep those in taxonomy or appearing 2+ times, excluding concatenations and title fragments
    bigram_counts = Counter(bigrams)
    filtered_bigrams = {}
    for bg, count in bigram_counts.items():
        bg_lower = bg.lower().strip()
        if bg_lower in ALL_SKILLS:
            filtered_bigrams[bg] = count
        elif count >= 2:
            if not is_skill_concatenation(bg_lower) and not is_job_title_fragment(bg_lower, first_line):
                filtered_bigrams[bg] = count

    # Filter trigrams: keep those in taxonomy or appearing 2+ times, excluding concatenations and title fragments
    trigram_counts = Counter(trigrams)
    filtered_trigrams = {}
    for tg, count in trigram_counts.items():
        tg_lower = tg.lower().strip()
        if tg_lower in ALL_SKILLS:
            filtered_trigrams[tg] = count
        elif count >= 2:
            if not is_skill_concatenation(tg_lower) and not is_job_title_fragment(tg_lower, first_line):
                filtered_trigrams[tg] = count

    total_tokens = len(meaningful_tokens) or 1
    weighted_keywords = {}

    role_words = {"engineer", "developer", "architect", "manager", "director", "consultant", "analyst", "candidate"}
    for token, count in unigram_counts.items():
        t_lower = token.lower()
        if t_lower in role_words and t_lower not in ALL_SKILLS:
            continue
        tf = count / total_tokens
        skill_boost = 2.0 if t_lower in ALL_SKILLS else 1.0
        if t_lower in SKILL_ALIASES:
            skill_boost = 1.8
        weight = tf * skill_boost * (1 + math.log(1 + count))
        weighted_keywords[t_lower] = weight

    for bigram, count in filtered_bigrams.items():
        tf = count / max(total_tokens - 1, 1)
        skill_boost = 2.5 if bigram.lower() in ALL_SKILLS else 1.2
        weight = tf * skill_boost * (1 + math.log(1 + count))
        weighted_keywords[bigram.lower()] = weight * 1.3

    for trigram, count in filtered_trigrams.items():
        tf = count / max(total_tokens - 2, 1)
        skill_boost = 3.0 if trigram.lower() in ALL_SKILLS else 1.1
        weight = tf * skill_boost * (1 + math.log(1 + count))
        weighted_keywords[trigram.lower()] = weight * 1.5

    lower_text = text.lower()
    for skill in ALL_SKILLS:
        if len(skill) >= 2 and skill in lower_text:
            if skill not in weighted_keywords:
                try:
                    pattern = r"\b" + re.escape(skill) + r"\b"
                    matches = re.findall(pattern, lower_text)
                    if matches:
                        count = len(matches)
                        tf = count / total_tokens
                        weighted_keywords[skill] = tf * 2.0 * (1 + math.log(1 + count))
                except re.error:
                    pass

    sorted_keywords = sorted(weighted_keywords.items(), key=lambda x: -x[1])
    return sorted_keywords[:top_k]


# ---------------------------------------------------------------------------
# Section 3: Resume Structure & Section Compliance Audit
# ---------------------------------------------------------------------------

def audit_resume_structure(resume_text: str) -> Dict[str, Any]:
    """
    Comprehensive audit of resume formatting, sections, contact information,
    and bullet point analysis. Returns granular scoring out of 100.
    """
    if not resume_text or not resume_text.strip():
        return {
            "structure_score": 0,
            "has_email": False,
            "has_phone": False,
            "has_links": False,
            "email": None,
            "phone": None,
            "detected_sections": [],
            "missing_sections": [],
            "total_bullets": 0,
            "bullets_with_action_verbs": 0,
            "bullets_with_metrics": 0,
            "bullet_analyses": [],
            "red_flags": ["Resume text is empty."],
        }

    lower = resume_text.lower()

    # 1. Contact Information checks
    email_match = re.search(
        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', resume_text
    )
    phone_match = re.search(
        r'(?:'
        r'(?:\+?880\s*[-.]?\s*|0)1[3-9]\d{2}[\s.\-]*\d{6}\b'  # Bangladesh: +880 1XXX-XXXXXX or 01XXXXXXXXX
        r'|(?:\+?44\s*[-.]?\s*|0)(?:\d{2,4}[\s.\-]*\d{3,4}[\s.\-]*\d{3,4})\b'  # UK: +44 ...
        r'|(?:\+?91\s*[-.]?\s*)[6-9]\d{4}[\s.\-]*\d{5}\b'  # India: +91 ...
        r'|\+[1-9]\d{7,14}\b'  # Generic E.164 (+ followed by 8-15 digits)
        r'|(?:\+?1\s*[-.]?\s*)?(?:\(?\d{3}\)?[\s.\-]*)\d{3}[\s.\-]*\d{4}\b'  # North American: (555) 123-4567
        r')',
        resume_text
    )
    linkedin_match = re.search(
        r'linkedin\.com/in/[\w\-]+', resume_text, re.IGNORECASE
    )
    github_match = re.search(
        r'github\.com/[\w\-]+', resume_text, re.IGNORECASE
    )
    portfolio_match = re.search(
        r'(?:portfolio|website|blog)\s*[:\|]?\s*(?:https?://)?[\w.\-]+\.\w{2,}',
        resume_text, re.IGNORECASE
    )

    has_email = bool(email_match)
    has_phone = bool(phone_match)
    has_links = bool(linkedin_match or github_match or portfolio_match)

    # 2. Section Headings detection
    detected_sections = []
    missing_sections = []

    key_sections = {
        "Contact Info": [
            "email", "phone", "contact", "address"
        ],
        "Professional Summary": [
            "summary", "profile", "about me", "objective",
            "professional summary", "executive summary", "career summary",
            "professional profile"
        ],
        "Work Experience": [
            "experience", "employment", "work history", "work experience",
            "professional experience", "career history", "employment history",
            "relevant experience"
        ],
        "Education": [
            "education", "academic", "degree", "university", "college",
            "academic background", "educational background", "certifications",
            "certificates"
        ],
        "Skills": [
            "skills", "technical skills", "technologies", "competencies",
            "core competencies", "tools", "tools & technologies",
            "tech stack", "proficiencies"
        ],
        "Projects": [
            "projects", "personal projects", "portfolio", "key projects",
            "notable projects", "side projects", "open source"
        ],
    }

    for section_name, aliases in key_sections.items():
        found = False
        for alias in aliases:
            # Match section headings: at line start, possibly with # or caps
            pattern = r'(?:^|\n)\s*(?:#{1,4}\s*)?' + re.escape(alias) + r'\b'
            if re.search(pattern, lower):
                found = True
                break
        if found:
            detected_sections.append(section_name)
        else:
            missing_sections.append(section_name)

    # Special: detect Contact Info via presence of email/phone rather than heading
    if has_email or has_phone:
        if "Contact Info" not in detected_sections:
            detected_sections.append("Contact Info")
            if "Contact Info" in missing_sections:
                missing_sections.remove("Contact Info")

    # 3. Bullet points and impact metrics
    raw_lines = resume_text.splitlines()
    bullet_lines = []
    for line in raw_lines:
        stripped = line.strip()
        if stripped and (
            stripped.startswith(("•", "-", "*", "–", "▪", "●", "◦", "·"))
            or re.match(r'^\d+\.', stripped)
        ):
            bullet_lines.append(stripped)

    bullet_analyses = [analyze_bullet_point(b) for b in bullet_lines]
    bullets_with_action_verbs = sum(1 for b in bullet_analyses if b["has_action_verb"])
    bullets_with_metrics = sum(1 for b in bullet_analyses if b["has_metric"])
    total_bullets = len(bullet_lines)

    # 4. Calculate structure compliance score (0–100) with granular scoring
    structure_score = 20  # Base score for having any content

    # Contact information (max 25 points)
    if has_email:
        structure_score += 12
    if has_phone:
        structure_score += 8
    if has_links:
        structure_score += 5

    # Section coverage (max 25 points)
    num_sections = len(detected_sections)
    if num_sections >= 5:
        structure_score += 25
    elif num_sections >= 4:
        structure_score += 20
    elif num_sections == 3:
        structure_score += 15
    elif num_sections == 2:
        structure_score += 10
    elif num_sections == 1:
        structure_score += 5

    # Bullet point quality (max 20 points)
    if total_bullets >= 8:
        structure_score += 20
    elif total_bullets >= 5:
        structure_score += 15
    elif total_bullets >= 3:
        structure_score += 10
    elif total_bullets >= 1:
        structure_score += 5

    # Word count check (max 10 points) — ideal: 300-1000 words
    word_count = len(resume_text.split())
    if 300 <= word_count <= 1000:
        structure_score += 10
    elif 200 <= word_count < 300 or 1000 < word_count <= 1200:
        structure_score += 5

    structure_score = min(structure_score, 100)

    # 5. Red flags
    red_flags = []
    if not has_email:
        red_flags.append("Missing contact email address. Most ATS systems require email for communication.")
    if not has_phone:
        red_flags.append("Missing phone number. Include a professional phone number.")
    if "Work Experience" in missing_sections:
        red_flags.append("Standard 'Work Experience' section heading not clearly identified. Use 'Work Experience' or 'Professional Experience'.")
    if "Skills" in missing_sections:
        red_flags.append("Standard 'Skills' section heading not detected. Add a dedicated 'Technical Skills' or 'Skills' section.")
    if "Education" in missing_sections:
        red_flags.append("'Education' section not detected. Include your educational background.")
    if total_bullets < 3:
        red_flags.append("Very few bullet points detected. ATS and recruiters prefer concise, bulleted accomplishment lists (aim for 3-6 per role).")
    if word_count < 150:
        red_flags.append(f"Resume appears too short ({word_count} words). Aim for 300-800 words for a strong single-page resume.")
    if word_count > 1200:
        red_flags.append(f"Resume may be too long ({word_count} words). Consider trimming to 1-2 pages unless you have 10+ years of experience.")

    # Note: Structural layout checks (tables, textboxes, columns) are performed via openats.format_audit
    if re.search(r'(?:image|photo|picture|headshot)', lower):
        red_flags.append("Reference to photos/images detected. Most ATS systems cannot parse images — remove them.")

    return {
        "structure_score": structure_score,
        "has_email": has_email,
        "has_phone": has_phone,
        "has_links": has_links,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
        "detected_sections": detected_sections,
        "missing_sections": missing_sections,
        "total_bullets": total_bullets,
        "bullets_with_action_verbs": bullets_with_action_verbs,
        "bullets_with_metrics": bullets_with_metrics,
        "bullet_analyses": bullet_analyses[:20],  # Cap at 20 for response size
        "red_flags": red_flags,
        "word_count": word_count,
    }


# ---------------------------------------------------------------------------
# Section 4: Multi-Factor Weighted Scoring (0–100%)
# ---------------------------------------------------------------------------

def _detect_bengali_text(text: str) -> bool:
    """Detect if text is predominantly Bengali script."""
    if not text:
        return False
    bengali_chars = len(re.findall(r'[\u0980-\u09FF]', text))
    total_letters = len(re.findall(r'[^\W\d_]', text))
    return (bengali_chars >= 15) and (bengali_chars / max(total_letters, 1) > 0.25)


def _detect_keyword_stuffing(
    resume_text: str,
    matched_keywords: List[Dict[str, Any]],
    structure_audit: Dict[str, Any]
) -> bool:
    """
    Detects unnatural keyword stuffing or resumes lacking surrounding narrative context.
    Flags resumes where:
      1. Matched keywords appear with almost no surrounding experience text
         (very low word count, no bullets, no verbs, no metrics).
      2. The same keyword/phrase repeats unnaturally across the document.
      3. Matched keywords account for an abnormally high fraction of total words.
    """
    tokens = clean_and_tokenize(resume_text)
    total_tokens = len(tokens)
    if total_tokens == 0:
        return False

    total_bullets = structure_audit.get("total_bullets", 0)
    bullets_with_verbs = structure_audit.get("bullets_with_action_verbs", 0)
    bullets_with_metrics = structure_audit.get("bullets_with_metrics", 0)
    word_count = structure_audit.get("word_count", total_tokens)

    has_narrative = (total_bullets > 0 and bullets_with_verbs > 0)
    total_kw_hits = sum(m.get("resume_count", 1) for m in matched_keywords)

    # 1. Matched keywords with almost no surrounding experience text
    if matched_keywords:
        if total_bullets == 0 and bullets_with_verbs == 0 and bullets_with_metrics == 0:
            return True
        if not has_narrative and word_count < 150:
            return True

    # 2. Unnatural keyword repetition
    token_counts = Counter(t.lower() for t in tokens)
    for m in matched_keywords:
        kw = m.get("keyword", "").lower()
        cnt = token_counts.get(kw, 0)
        # In a short document (under 150 words), repeating the same keyword 6+ times
        if word_count < 150 and cnt >= 6:
            return True
        # In any document, if a single keyword makes up more than 20% of all tokens
        if total_tokens >= 20 and (cnt / total_tokens) > 0.20:
            return True

    # 3. Overall keyword concentration without narrative (>40% of document is matched keywords)
    if total_tokens >= 15 and not has_narrative and (total_kw_hits / total_tokens) > 0.40:
        return True

    return False


def analyze_ats_match(resume_text: str, job_description: str, include_contact: bool = False) -> Dict[str, Any]:
    """
    Main orchestration function: produces a complete ATS scorecard comparing
    Resume to Job Description using the multi-factor weighted scoring model.

    Formula:
      Final_Score = (0.40 * Keyword_Match) + (0.30 * Skill_Taxonomy_Coverage)
                  + (0.20 * Section_Structure_Score) + (0.10 * STAR_Metric_Density)

    Args:
        resume_text: Raw resume content.
        job_description: Target job description.
        include_contact: If True, include extracted email/phone strings in structure_audit;
                         if False (default), omit raw contact values to protect PII.
    """
    if not resume_text or not resume_text.strip():
        raise ValueError("Resume text must be provided and cannot be empty.")
    if not job_description or not job_description.strip():
        raise ValueError("Job description must be provided and cannot be empty.")

    resume_lower = resume_text.lower()
    jd_lower = job_description.lower()

    # 1. Keyword Extraction & Matching (40% weight)
    jd_keywords = extract_keywords_with_frequencies(job_description, top_k=40)

    matched_keywords = []
    missing_keywords = []

    for kw, weight in jd_keywords:
        # Search for original term, canonical form, and all aliases
        forms_to_check = get_all_skill_forms(kw)
        resume_count = 0
        for form in forms_to_check:
            try:
                pattern = r"\b" + re.escape(form) + r"\b"
                resume_count += len(re.findall(pattern, resume_lower))
            except re.error:
                resume_count += resume_lower.count(form)

        # Fuzzy match fallback if not found
        if resume_count == 0:
            for form in forms_to_check:
                fuzzy = _fuzzy_skill_match(form, ALL_SKILLS, max_distance=1)
                if fuzzy and fuzzy != form:
                    try:
                        pattern = r"\b" + re.escape(fuzzy) + r"\b"
                        resume_count += len(re.findall(pattern, resume_lower))
                    except re.error:
                        resume_count += resume_lower.count(fuzzy)
                if resume_count > 0:
                    break

        kw_cat = ALL_SKILLS.get(kw.lower(), ALL_SKILLS.get(SKILL_ALIASES.get(kw.lower(), ""), "General Keyword"))
        real_count = count_occurrences_in_text(kw, jd_lower)

        if resume_count > 0:
            matched_keywords.append({
                "keyword": kw,
                "jd_weight": round(weight, 4),
                "resume_count": resume_count,
                "category": kw_cat,
            })
        else:
            # Importance rating based on real JD occurrence frequency and domain weight:
            # - Critical: Repeated heavily in JD (count >= 3) OR recognized technical skill with count >= 2
            # - High: Appears 2 times in JD, OR recognized skill appearing at least once with weight >= 0.02
            # - Medium: Single occurrence general term or lower frequency mention
            if real_count >= 3 or (kw_cat != "General Keyword" and real_count >= 2):
                importance = "Critical"
            elif real_count >= 2 or (kw_cat != "General Keyword" and weight >= 0.02):
                importance = "High"
            else:
                importance = "Medium"

            missing_keywords.append({
                "keyword": kw,
                "jd_weight": round(weight, 4),
                "jd_count": real_count,
                "importance": importance,
                "category": kw_cat,
            })

    # Deduplicate matched keywords by coverage (prefer longest match)
    # If a longer phrase like "distributed systems" matches, component words like "distributed" or "systems"
    # should not also be counted as separate matched keywords.
    matched_phrases = [m["keyword"].lower() for m in matched_keywords if " " in m["keyword"]]
    deduped_matched = []
    for m in matched_keywords:
        kw_l = m["keyword"].lower()
        is_sub = False
        for p in matched_phrases:
            if kw_l != p and kw_l in p.split():
                is_sub = True
                break
        if not is_sub:
            deduped_matched.append(m)
    matched_keywords = deduped_matched

    # Keyword match score: weighted ratio of matched vs total
    total_jd_weight = sum(w for _, w in jd_keywords) if jd_keywords else 1.0
    matched_weight = sum(m["jd_weight"] for m in matched_keywords)
    keyword_score = round((matched_weight / total_jd_weight) * 100, 1)
    keyword_score = min(keyword_score, 100.0)

    # 2. Skill Taxonomy Analysis (30% weight)
    jd_skills = set()
    resume_skills = set()
    categorized_breakdown = {}

    for skill, category in ALL_SKILLS.items():
        try:
            if re.search(r"\b" + re.escape(skill) + r"\b", jd_lower):
                jd_skills.add(skill)
                if category not in categorized_breakdown:
                    categorized_breakdown[category] = {"matched": [], "missing": []}

                forms = get_all_skill_forms(skill)
                skill_found = any(re.search(r"\b" + re.escape(f) + r"\b", resume_lower) for f in forms)
                if not skill_found:
                    resume_tokens = set(clean_and_tokenize(resume_text))
                    skill_found = any(_levenshtein_distance(t, skill) <= 1 for t in resume_tokens)

                if skill_found:
                    resume_skills.add(skill)
                    categorized_breakdown[category]["matched"].append(skill)
                else:
                    categorized_breakdown[category]["missing"].append(skill)
        except re.error:
            continue

    if not jd_skills:
        skill_score = None
        skill_match_available = False
    else:
        skill_score = round((len(resume_skills) / len(jd_skills)) * 100, 1)
        skill_score = min(skill_score, 100.0)
        skill_match_available = True

    # 3. Structure & Formatting Audit (20% weight)
    structure_audit = audit_resume_structure(resume_text)
    if not include_contact:
        structure_audit.pop("email", None)
        structure_audit.pop("phone", None)

    # 4. STAR Impact Score (10% weight)
    total_b = structure_audit["total_bullets"]
    if total_b > 0:
        verb_ratio = structure_audit["bullets_with_action_verbs"] / total_b
        metric_ratio = structure_audit["bullets_with_metrics"] / total_b
        impact_score = round(((verb_ratio * 0.5) + (metric_ratio * 0.5)) * 100, 1)
    else:
        impact_score = 30.0
    impact_score = min(impact_score, 100.0)

    # Bengali Language Check (Item 2)
    is_bengali = _detect_bengali_text(resume_text) or _detect_bengali_text(job_description)
    language_warning = (
        "This resume appears to be in Bengali. The skill taxonomy is English-only, so this score is not reliable for Bengali text."
        if is_bengali else None
    )

    # Keyword Stuffing Detection (Item 1)
    stuffing_detected = _detect_keyword_stuffing(resume_text, matched_keywords, structure_audit)
    stuffing_warning = (
        "Keyword repetition detected - this looks like stuffing. Add real experience bullets using these skills."
        if stuffing_detected else None
    )

    if stuffing_detected:
        keyword_score = min(keyword_score, 30.0)
        if skill_score is not None:
            skill_score = min(skill_score, 30.0)

    # 5. Composite Final Score (Weighted Formula)
    if skill_score is not None:
        final_score = round(
            (0.40 * keyword_score) +
            (0.30 * skill_score) +
            (0.20 * structure_audit["structure_score"]) +
            (0.10 * impact_score),
            1
        )
    else:
        # Re-weight remaining factors proportionally across 0.70 total weight:
        # Keyword (40/70), Structure (20/70), Impact (10/70)
        reweighted = (
            (0.40 * keyword_score) +
            (0.20 * structure_audit["structure_score"]) +
            (0.10 * impact_score)
        ) / 0.70
        final_score = round(reweighted, 1)

    final_score = max(0.0, min(final_score, 100.0))

    if final_score >= 80:
        score_tier = "Excellent Match"
    elif final_score >= 65:
        score_tier = "Strong Match"
    elif final_score >= 50:
        score_tier = "Moderate Match"
    else:
        score_tier = "Needs Optimization"

    recommendations = _generate_recommendations(
        final_score=final_score,
        keyword_score=keyword_score,
        skill_score=skill_score,
        impact_score=impact_score,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        structure_audit=structure_audit,
        categorized_breakdown=categorized_breakdown,
        total_bullets=total_b,
    )

    if stuffing_warning:
        recommendations.insert(0, f"🚨 **{stuffing_warning}**")
    if language_warning:
        recommendations.insert(0, f"⚠️ **Notice:** {language_warning}")

    return {
        "final_score": final_score,
        "score_tier": score_tier,
        "is_bengali": is_bengali,
        "language_warning": language_warning,
        "stuffing_detected": stuffing_detected,
        "stuffing_warning": stuffing_warning,
        "sub_scores": {
            "keyword_match": keyword_score,
            "skill_match": skill_score,
            "skill_match_available": skill_match_available,
            "structure_compliance": structure_audit["structure_score"],
            "measurable_impact": impact_score,
        },
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "skill_breakdown": categorized_breakdown,
        "structure_audit": structure_audit,
        "recommendations": recommendations,
        "summary": {
            "total_jd_keywords": len(jd_keywords),
            "matched_count": len(matched_keywords),
            "missing_count": len(missing_keywords),
            "total_jd_skills": len(jd_skills),
            "matched_skills_count": len(resume_skills),
        },
    }


def _generate_recommendations(
    final_score: float,
    keyword_score: float,
    skill_score: Optional[float],
    impact_score: float,
    matched_keywords: List[Dict],
    missing_keywords: List[Dict],
    structure_audit: Dict[str, Any],
    categorized_breakdown: Dict[str, Dict],
    total_bullets: int,
) -> List[str]:
    """
    Generates a prioritized list of strategic recommendations based on
    all scoring factors. Returns actionable, specific advice.
    """
    recommendations = []

    # Overall tier message
    if final_score >= 80:
        recommendations.append(
            "🌟 **Excellent ATS readiness!** Your resume matches over 80% of key requirements "
            "and is primed to pass automated screenings. Fine-tune the few gaps below for a perfect score."
        )
    elif final_score >= 65:
        recommendations.append(
            "✅ **Strong foundation with room for optimization.** You're above the typical screening "
            "threshold, but incorporating the missing keywords below can push you into the top tier."
        )
    elif final_score >= 50:
        recommendations.append(
            "⚠️ **Moderate match — optimization needed.** Your resume covers some requirements but "
            "has significant gaps. Focus on the missing high-priority keywords and structural improvements."
        )
    else:
        recommendations.append(
            "🚨 **High risk of ATS filtering.** Significant gaps in required technical keywords and/or "
            "resume structure. Prioritize the critical missing skills and structural fixes below."
        )

    # Missing keywords recommendation
    if missing_keywords:
        critical = [m["keyword"] for m in missing_keywords if m.get("importance") == "Critical"][:5]
        high = [m["keyword"] for m in missing_keywords if m.get("importance") == "High"][:5]

        if critical:
            recommendations.append(
                f"• **Critical missing terms:** Add these high-frequency keywords where you have genuine "
                f"experience: **{', '.join(critical)}**."
            )
        if high:
            recommendations.append(
                f"• **High-priority gaps:** Incorporate these terms naturally into your experience "
                f"bullets: **{', '.join(high)}**."
            )

    # Keyword score specific advice
    if keyword_score < 50:
        recommendations.append(
            "• **Mirror the job description language.** Use the exact terms and phrases from the posting "
            "in your summary, skills section, and experience bullets."
        )

    # Skill domain gaps
    for domain, data in categorized_breakdown.items():
        missing = data.get("missing", [])
        if len(missing) >= 3:
            top_missing = missing[:4]
            recommendations.append(
                f"• **{domain} gap:** Consider adding: {', '.join(top_missing)}."
            )

    # Structure recommendations
    if structure_audit.get("red_flags"):
        for flag in structure_audit["red_flags"][:3]:
            recommendations.append(f"• **Formatting:** {flag}")

    # STAR bullet recommendations
    if total_bullets > 0:
        metric_ratio = structure_audit["bullets_with_metrics"] / total_bullets
        verb_ratio = structure_audit["bullets_with_action_verbs"] / total_bullets

        if metric_ratio < 0.4:
            recommendations.append(
                "• **Quantify your impact.** Add measurable results (%, $, user scale, latency reduction) "
                "to at least 40% of your experience bullets."
            )
        if verb_ratio < 0.5:
            recommendations.append(
                "• **Lead with action verbs.** Start each bullet with a strong past-tense verb like "
                "'Architected', 'Optimized', 'Spearheaded', 'Reduced', or 'Delivered'."
            )
    elif total_bullets == 0:
        recommendations.append(
            "• **Use bullet points.** Break your experience into concise, bulleted accomplishment "
            "statements. ATS and recruiters scan for these."
        )

    # Impact score advice
    if impact_score < 40:
        recommendations.append(
            "• **Strengthen your STAR bullets.** Each bullet should follow: Action Verb + What you did "
            "+ Measurable Result (e.g., 'Reduced API latency by 42% through Redis caching')."
        )

    return recommendations[:10]  # Cap at 10 most important
