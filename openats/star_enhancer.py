"""
OpenATS — STAR Framework Bullet Point Enhancer
Transforms weak, passive resume bullets into high-impact, ATS-optimized achievements.
Works 100% offline via algorithmic heuristics. Zero external API dependency.
Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""

import re
from typing import Dict, List, Any, Optional

from .taxonomy import ACTION_VERBS

# ---------------------------------------------------------------------------
# Constants & Scoring Weights (40/30/30 Structure)
# ---------------------------------------------------------------------------

# Maximum bullet length before truncation.
_MAX_BULLET_LENGTH: int = 500

# Maximum number of bullets processed in a batch.
_MAX_BATCH_SIZE: int = 20

# 40/30/30 Scoring breakdown:
# - 40 base score: awarded to any valid, non-empty bullet.
# - 30 action verb bonus: awarded when an approved past-tense action verb leads the bullet.
# - 30 quantifiable metric bonus: awarded when a verifiable metric (%, $, count, latency) exists.
# Hard Constraint: A bullet must NEVER score above 70 without a real quantifiable metric.
_BASE_SCORE: int = 40
_ACTION_VERB_BONUS: int = 30
_METRIC_BONUS: int = 30

# Distinct placeholders for user-supplied metrics (never invent fake numbers).
_PLACEHOLDER_A: str = " [ADD YOUR REAL RESULT: e.g. reduced time by __%]"
_PLACEHOLDER_B: str = " [ADD YOUR REAL RESULT: e.g. improved efficiency by __%]"


# ---------------------------------------------------------------------------
# WEAK_OPENERS — passive / vague phrases mapped to strong replacements
# ---------------------------------------------------------------------------

WEAK_OPENERS: Dict[str, List[str]] = {
    "responsible for": [
        "Spearheaded",
        "Directed",
        "Managed",
        "Led",
    ],
    "worked on": [
        "Engineered",
        "Developed",
        "Architected",
        "Built",
        "Designed and deployed",
    ],
    "helped with": [
        "Collaborated with cross-functional teams to deliver",
        "Co-engineered",
        "Facilitated",
        "Partnered on",
    ],
    "handled": [
        "Orchestrated",
        "Managed end-to-end",
        "Administered",
        "Oversaw",
    ],
    "assisted in": [
        "Partnered to implement",
        "Contributed to",
        "Accelerated delivery of",
    ],
    "duties included": [
        "Executed key initiatives including",
        "Delivered",
        "Drove outcomes including",
    ],
    "participated in": [
        "Drove participation in",
        "Active contributor to",
        "Championed involvement in",
    ],
    "involved in": [
        "Played a key role in",
        "Drove",
        "Instrumental in",
    ],
    "was part of": [
        "Contributed to",
        "Core member of the team that",
        "Delivered as part of",
    ],
    "tasked with": [
        "Entrusted with",
        "Led the initiative to",
        "Took ownership of",
    ],
    "did": [
        "Executed",
        "Delivered",
        "Accomplished",
    ],
    "managed": [
        "Directed",
        "Led",
        "Oversaw",
        "Orchestrated",
    ],
    "created": [
        "Designed and built",
        "Architected",
        "Pioneered",
    ],
    "used": [
        "Leveraged",
        "Utilized",
        "Applied",
        "Employed",
    ],
    "made": [
        "Developed",
        "Crafted",
        "Engineered",
        "Produced",
    ],
}

# Pre-compile a single regex that matches any weak opener at the start of a
# bullet (case-insensitive). Longer phrases are tried first.
_WEAK_OPENER_PATTERN: re.Pattern = re.compile(
    r"^(?:" +
    "|".join(
        re.escape(phrase)
        for phrase in sorted(WEAK_OPENERS.keys(), key=len, reverse=True)
    ) +
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# GERUND_TO_PAST — canonical mapping from -ing gerunds to past-tense verbs
# ---------------------------------------------------------------------------

GERUND_TO_PAST: Dict[str, str] = {
    "building": "Built",
    "managing": "Managed",
    "resolving": "Resolved",
    "developing": "Developed",
    "designing": "Designed",
    "creating": "Created",
    "engineering": "Engineered",
    "implementing": "Implemented",
    "maintaining": "Maintained",
    "leading": "Led",
    "driving": "Drove",
    "writing": "Wrote",
    "testing": "Tested",
    "deploying": "Deployed",
    "architecting": "Architected",
    "optimizing": "Optimized",
    "automating": "Automated",
    "analyzing": "Analyzed",
    "migrating": "Migrated",
    "executing": "Executed",
    "coordinating": "Coordinated",
    "collaborating": "Collaborated",
    "conducting": "Conducted",
    "configuring": "Configured",
    "delivering": "Delivered",
    "directing": "Directed",
    "establishing": "Established",
    "facilitating": "Facilitated",
    "formulating": "Formulated",
    "generating": "Generated",
    "improving": "Improved",
    "launching": "Launched",
    "monitoring": "Monitored",
    "negotiating": "Negotiated",
    "organizing": "Organized",
    "overseeing": "Oversaw",
    "performing": "Performed",
    "planning": "Planned",
    "producing": "Produced",
    "programming": "Programmed",
    "providing": "Provided",
    "researching": "Researched",
    "restructuring": "Restructured",
    "reviewing": "Reviewed",
    "scaling": "Scaled",
    "securing": "Secured",
    "spearheading": "Spearheaded",
    "standardizing": "Standardized",
    "streamlining": "Streamlined",
    "supervising": "Supervised",
    "supporting": "Supported",
    "tracking": "Tracked",
    "training": "Trained",
    "transforming": "Transformed",
    "upgrading": "Upgraded",
    "utilizing": "Utilized",
    "handling": "Handled",
    "assisting": "Assisted",
    "fixing": "Fixed",
    "refactoring": "Refactored",
    "integrating": "Integrated",
    "administering": "Administered",
    "evaluating": "Evaluated",
    "troubleshooting": "Troubleshot",
    "authoring": "Authored",
    "running": "Ran",
    "making": "Made",
    "setting": "Set",
    "cutting": "Cut",
    "growing": "Grew",
    "expanding": "Expanded",
    "reducing": "Reduced",
    "increasing": "Increased",
    "decreasing": "Decreased",
    "eliminating": "Eliminated",
    "saving": "Saved",
    "winning": "Won",
    "serving": "Served",
    "preparing": "Prepared",
    "publishing": "Published",
    "presenting": "Presented",
    "mentoring": "Mentored",
    "onboarding": "Onboarded",
    "recruiting": "Recruited",
    "hiring": "Hired",
    "budgeting": "Budgeted",
    "forecasting": "Forecasted",
    "auditing": "Audited",
    "compiling": "Compiled",
    "investigating": "Investigated",
    "partnering": "Partnered",
    "debugging": "Debugged",
    "coding": "Coded",
    "validating": "Validated",
    "verifying": "Verified",
    "profiling": "Profiled",
    "benchmarking": "Benchmarked",
    "containerizing": "Containerized",
    "orchestrating": "Orchestrated",
    "provisioning": "Provisioned",
    "documenting": "Documented",
    "gathering": "Gathered",
    "communicating": "Communicated",
    "moderating": "Moderated",
    "curating": "Curated",
    "scheduling": "Scheduled",
    "processing": "Processed",
    "querying": "Queried",
    "indexing": "Indexed",
    "caching": "Cached",
    "partitioning": "Partitioned",
    "sharding": "Sharded",
    "synthesizing": "Synthesized",
    "translating": "Translated",
    "converting": "Converted",
    "parsing": "Parsed",
    "scraping": "Scraped",
    "extracting": "Extracted",
    "cleaning": "Cleaned",
    "ingesting": "Ingested",
    "loading": "Loaded",
    "aggregating": "Aggregated",
    "visualizing": "Visualized",
    "modeling": "Modeled",
    "tuning": "Tuned",
    "shipping": "Shipped",
    "pushing": "Pushed",
    "releasing": "Released",
    "patching": "Patched",
    "solving": "Solved",
}


def _gerund_to_past(word: str) -> Optional[str]:
    """Convert an English gerund (-ing word) to its past-tense action form."""
    w = word.lower().strip()
    if w in GERUND_TO_PAST:
        return GERUND_TO_PAST[w]
    if not w.endswith("ing") or len(w) <= 4:
        return None
    base = w[:-3]
    if len(base) >= 3 and base[-1] == base[-2] and base[-1] in "bcdgklmnprstz":
        return (base + "ed").capitalize()
    if base.endswith(("at", "iz", "us", "clos", "mov", "liv", "sav")):
        return (base + "ed").capitalize()
    return (base + "ed").capitalize()


# ---------------------------------------------------------------------------
# METRIC_PATTERNS — compiled regexes for quantifiable achievements
# ---------------------------------------------------------------------------

METRIC_PATTERNS: List[re.Pattern] = [
    # Percentages — e.g. 45%, 12.5%
    re.compile(r"\d+(?:\.\d+)?%", re.IGNORECASE),

    # Dollar (or euro) amounts — $500, $1.2M, $50k, €100K
    re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d+)?[kKmMbBtT]?", re.IGNORECASE),

    # Latency / speed — 200ms, 3 seconds, 5 minutes
    re.compile(
        r"\d+(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?|sec|minutes?|min|hours?|hr)",
        re.IGNORECASE,
    ),

    # Relative gains — "reduced by 30", "increased by 50%"
    re.compile(
        r"(?:reduced?|increased?|improved?|decreased?|grew|boosted?|cut|saved?)"
        r"\s+(?:by\s+)?\d+(?:\.\d+)?%?",
        re.IGNORECASE,
    ),

    # Scale indicators — 10K users, 1M requests, 500+ customers
    re.compile(r"\d[\d,]*(?:\.\d+)?[kKmMbB]?\+?\s*(?:users?|requests?|customers?|clients?|transactions?|records?|entries|endpoints?|servers?|msgs?|messages?|qps|events?|req/s|rps|ops|jobs)", re.IGNORECASE),

    # From/to ranges — "from 10 to 100"
    re.compile(r"from\s+\d[\d,]*(?:\.\d+)?\s+to\s+\d[\d,]*(?:\.\d+)?", re.IGNORECASE),

    # Multipliers — 3x, 10x, 2.5x improvement
    re.compile(r"\d+(?:\.\d+)?x\b", re.IGNORECASE),

    # Revenue / cost keywords paired with numbers
    re.compile(r"(?:revenue|cost\s+savings?|ROI|profit|budget)\s*(?:of\s+)?\$?\d", re.IGNORECASE),

    # Time savings — "hours saved", "days reduced"
    re.compile(
        r"\d+(?:\.\d+)?\s*(?:hours?|days?|weeks?|months?)\s+(?:saved|reduced|eliminated|freed)",
        re.IGNORECASE,
    ),

    # Generic large numbers with commas — 1,000; 50,000
    re.compile(r"\b\d{1,3}(?:,\d{3})+\b"),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_bullet(text: str) -> str:
    """Strip whitespace, leading bullet markers, and enforce max length."""
    text = text.strip()
    # Remove common leading bullet markers: -, *, •, ▸, ▹, ▪, ●, ◦, ·, numbered lists
    text = re.sub(r"^(?:[-*•▸▹▪●◦·]\s+|\d+[.)]\s+)", "", text).strip()
    if len(text) > _MAX_BULLET_LENGTH:
        text = text[:_MAX_BULLET_LENGTH].rstrip() + "…"
    return text


def _detect_weak_opener(bullet_lower: str) -> Optional[str]:
    """Return the first weak opener found at the start of *bullet_lower*."""
    match = _WEAK_OPENER_PATTERN.search(bullet_lower)
    if match:
        return match.group(0).lower()
    return None


def _detect_action_verb(bullet: str) -> Optional[str]:
    """Return the first strong action verb found in *bullet*."""
    words = re.findall(r"[A-Za-z]+", bullet)
    first_words = [w.lower() for w in words[:5]]

    verbs_set: set = set()
    if isinstance(ACTION_VERBS, dict):
        for verb_list in ACTION_VERBS.values():
            for verb in verb_list:
                verbs_set.add(verb.lower())
    elif isinstance(ACTION_VERBS, (list, tuple, set, frozenset)):
        verbs_set = {v.lower() for v in ACTION_VERBS}
    else:
        try:
            verbs_set = {v.lower() for v in ACTION_VERBS}
        except TypeError:
            verbs_set = set()

    for word in first_words:
        if word in verbs_set:
            return word.lower()
    return None


def _detect_metrics(bullet: str) -> bool:
    """Return ``True`` if *bullet* contains at least one quantifiable metric."""
    for pattern in METRIC_PATTERNS:
        if pattern.search(bullet):
            return True
    return False


def _compute_score(has_action_verb: bool, has_metric: bool) -> int:
    """Compute a 0-100 quality score for a bullet.

    Scoring breakdown (40/30/30 structure):
        * 40 — base score (non-empty bullet)
        * +30 — strong action verb at opening
        * +30 — quantifiable metric present

    Constraint:
        A bullet must NEVER score above 70 without a real quantifiable metric.
        Maximum possible score without a metric is exactly 70 (40 base + 30 verb).
    """
    score = _BASE_SCORE
    if has_action_verb:
        score += _ACTION_VERB_BONUS
    if has_metric:
        score += _METRIC_BONUS
    else:
        # Hard ceiling: without a real metric, score cannot exceed 70
        score = min(score, 70)
    return score


def _build_feedback(
    has_action_verb: bool,
    has_metric: bool,
    weak_opener: Optional[str],
) -> List[str]:
    """Generate specific, actionable improvement tips."""
    tips: List[str] = []

    if weak_opener:
        replacements = WEAK_OPENERS.get(weak_opener, [])
        if replacements:
            alts = ", ".join(f'"{r}"' for r in replacements[:3])
            tips.append(
                f"Replace the weak opener \"{weak_opener}\" with a stronger "
                f"action phrase such as {alts}."
            )
        else:
            tips.append(
                f"Replace the weak opener \"{weak_opener}\" with a strong, "
                "results-oriented verb."
            )

    if not has_action_verb:
        tips.append(
            "Start the bullet with a powerful action verb (e.g. "
            "\"Engineered\", \"Spearheaded\", \"Optimized\") to immediately "
            "convey ownership and impact."
        )

    if not has_metric:
        tips.append(
            "Quantify your impact — add a measurable metric such as a "
            "percentage improvement, dollar value, time saved, or user count "
            "to make the achievement concrete."
        )
        tips.append(
            "Replace the bracket with a real number from your experience. Do not guess."
        )

    if has_action_verb and has_metric and not weak_opener:
        tips.append(
            "Strong bullet! Consider tightening language for conciseness or "
            "adding context about the business outcome."
        )

    return tips


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_heuristic_rewrites(
    bullet: str,
    has_verb: bool,
    has_metric: bool,
) -> List[str]:
    """Generate up to 2 STAR-format rewrite suggestions for *bullet*.

    Deterministic heuristic rules — no LLM or network call is required.
    Strictly avoids ungrammatical 'Verb + -ing' constructions and never
    invents false metrics or percentages.

    Args:
        bullet: Cleaned bullet text (original casing).
        has_verb: Whether the bullet already contains a strong action verb.
        has_metric: Whether the bullet already contains a quantifiable metric.

    Returns:
        A list of 1–2 rewrite strings.
    """
    if not bullet or not bullet.strip():
        return []

    bullet_lower = bullet.lower()
    weak_opener = _detect_weak_opener(bullet_lower)

    def _format_output(base_text: str, idx: int) -> str:
        clean_b = base_text.rstrip(". ,;")
        if not has_metric and not _detect_metrics(clean_b):
            suffix = _PLACEHOLDER_A if idx == 0 else _PLACEHOLDER_B
            return f"{clean_b}{suffix}."
        elif not clean_b.endswith("."):
            return clean_b + "."
        return clean_b

    # Case 1: Weak opener detected
    if weak_opener:
        opener_re = re.compile(r"^" + re.escape(weak_opener) + r"\b[:\s,]*", re.IGNORECASE)
        remainder = opener_re.sub("", bullet).strip()

        words = remainder.split()
        first_word = words[0] if words else ""
        rest_words = " ".join(words[1:]).strip()
        past_verb = _gerund_to_past(first_word) if first_word else None

        # Cooperative openers: e.g. "helped with resolving tickets" -> "Resolved tickets with the support team"
        if weak_opener in ("helped with", "assisted in", "helped to", "assisted with"):
            if past_verb and rest_words.lower().startswith("ticket"):
                base_1 = f"Resolved {rest_words} with the support team"
                base_2 = f"Collaborated with the support team to resolve {rest_words}"
                return [_format_output(base_1, 0), _format_output(base_2, 1)]
            elif past_verb:
                base_1 = f"{past_verb} {rest_words}"
                alt_verb = "Engineered" if past_verb not in ("Engineered", "Built") else "Implemented"
                base_2 = f"{alt_verb} {rest_words}"
                return [_format_output(base_1, 0), _format_output(base_2, 1)]

        # Gerund following weak opener: "worked on building X" -> "Built X", "responsible for managing X" -> "Managed X"
        if past_verb:
            base_1 = f"{past_verb} {rest_words}"
            if weak_opener == "responsible for":
                alt_verb = "Directed" if past_verb != "Directed" else "Led"
            else:
                alt_verb = "Engineered" if past_verb not in ("Engineered", "Built") else "Developed"
            base_2 = f"{alt_verb} {rest_words}"
            return [_format_output(base_1, 0), _format_output(base_2, 1)]

        # Non-gerund remainder: "responsible for database maintenance" -> "Directed database maintenance"
        clean_rem = remainder
        if clean_rem and clean_rem[0].isupper() and len(clean_rem) > 1 and clean_rem[1].islower():
            clean_rem = clean_rem[0].lower() + clean_rem[1:]

        replacements = WEAK_OPENERS.get(weak_opener, ["Spearheaded", "Directed"])
        v1 = replacements[0]
        v2 = replacements[1] if len(replacements) > 1 else "Directed"

        base_1 = f"{v1} {clean_rem}"
        base_2 = f"{v2} {clean_rem}"
        return [_format_output(base_1, 0), _format_output(base_2, 1)]

    # Case 2: No action verb detected
    if not has_verb:
        words = bullet.split()
        first_word = words[0] if words else ""
        rest_words = " ".join(words[1:]).strip()
        past_verb = _gerund_to_past(first_word) if first_word else None

        if past_verb:
            base_1 = f"{past_verb} {rest_words}"
            alt_verb = "Engineered" if past_verb not in ("Engineered", "Built") else "Developed"
            base_2 = f"{alt_verb} {rest_words}"
            return [_format_output(base_1, 0), _format_output(base_2, 1)]

        verb_candidates = ["Spearheaded", "Engineered", "Delivered", "Optimized", "Architected", "Led"]
        chosen = [v for v in verb_candidates if v.lower() != first_word.lower()][:2]
        if len(chosen) < 2:
            chosen = verb_candidates[:2]

        body = bullet
        if body and body[0].isupper() and len(body) > 1 and body[1].islower():
            body = body[0].lower() + body[1:]

        base_1 = f"{chosen[0]} {body}"
        base_2 = f"{chosen[1]} {body}"
        return [_format_output(base_1, 0), _format_output(base_2, 1)]

    # Case 3: Has action verb but no metric
    if not has_metric:
        base = bullet.rstrip(". ,;")
        return [_format_output(base, 0), _format_output(base, 1)]

    # Case 4: Bullet already has both a strong verb and a metric — preserve completely
    clean_bullet = bullet if bullet.endswith(".") else bullet + "."
    return [clean_bullet]


def analyze_bullet_point(bullet: str) -> Dict[str, Any]:
    """Perform a comprehensive quality analysis of a single resume bullet."""
    if not bullet or not bullet.strip():
        return {
            "original": "",
            "score": 0,
            "has_action_verb": False,
            "has_metric": False,
            "action_verb": None,
            "weak_opener_detected": None,
            "feedback": ["Bullet is empty — provide a meaningful achievement statement."],
            "suggested_rewrites": [],
        }

    cleaned = _clean_bullet(bullet)

    if len(cleaned.split()) <= 1:
        return {
            "original": cleaned,
            "score": 0,
            "has_action_verb": False,
            "has_metric": False,
            "action_verb": None,
            "weak_opener_detected": None,
            "feedback": [
                "Bullet is too short — expand it into a full STAR-format "
                "achievement statement (Situation, Task, Action, Result)."
            ],
            "suggested_rewrites": [],
        }

    bullet_lower = cleaned.lower()
    weak_opener = _detect_weak_opener(bullet_lower)
    action_verb = _detect_action_verb(cleaned)
    has_action_verb = action_verb is not None
    has_metric = _detect_metrics(cleaned)
    score = _compute_score(has_action_verb, has_metric)

    if weak_opener:
        score = max(0, score - 15)

    # Strictly enforce: no bullet may score above 70 without a real metric
    if not has_metric:
        score = min(score, 70)

    feedback = _build_feedback(has_action_verb, has_metric, weak_opener)
    suggested_rewrites = generate_heuristic_rewrites(
        cleaned, has_action_verb, has_metric,
    )

    return {
        "original": cleaned,
        "score": score,
        "has_action_verb": has_action_verb,
        "has_metric": has_metric,
        "action_verb": action_verb,
        "weak_opener_detected": weak_opener,
        "feedback": feedback,
        "suggested_rewrites": suggested_rewrites,
    }


def batch_analyze_bullets(bullets: List[str]) -> Dict[str, Any]:
    """Analyze a batch of resume bullets and return aggregate statistics."""
    if not bullets:
        return {
            "total_bullets": 0,
            "bullets_with_action_verbs": 0,
            "bullets_with_metrics": 0,
            "average_score": 0.0,
            "weak_openers_found": 0,
            "analyses": [],
        }

    capped = bullets[:_MAX_BATCH_SIZE]

    analyses: List[Dict[str, Any]] = []
    total_score: int = 0
    action_verb_count: int = 0
    metric_count: int = 0
    weak_opener_count: int = 0

    for bullet_text in capped:
        analysis = analyze_bullet_point(bullet_text)
        analyses.append(analysis)
        total_score += analysis["score"]
        if analysis["has_action_verb"]:
            action_verb_count += 1
        if analysis["has_metric"]:
            metric_count += 1
        if analysis["weak_opener_detected"] is not None:
            weak_opener_count += 1

    count = len(analyses)
    avg_score = round(total_score / count, 1) if count > 0 else 0.0

    return {
        "total_bullets": count,
        "bullets_with_action_verbs": action_verb_count,
        "bullets_with_metrics": metric_count,
        "average_score": avg_score,
        "weak_openers_found": weak_opener_count,
        "analyses": analyses,
    }
