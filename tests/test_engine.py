import os
import sys
import unittest
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openats.engine import (
    clean_and_tokenize,
    extract_ngrams,
    extract_keywords_with_frequencies,
    normalize_skill,
    _levenshtein_distance,
    _fuzzy_skill_match,
    audit_resume_structure,
    analyze_ats_match,
    TECH_SYMBOL_MAP,
)
from openats.taxonomy import (
    SKILL_TAXONOMY,
    ALL_SKILLS,
    SKILL_ALIASES,
    ACTION_VERBS,
    STANDARD_SECTIONS,
    STOP_WORDS,
)

class TestTextPreprocessing(unittest.TestCase):
    """Section 1: Advanced Text Preprocessing & Cleaning Tests."""

    def test_tech_symbol_preservation_cpp(self):
        tokens = clean_and_tokenize("Deep experience with C++ and C# systems.")
        tokens_lower = [t.lower() for t in tokens]
        self.assertTrue(
            "c++" in tokens_lower or "cpp_lang" in tokens or "cpp" in tokens_lower,
            f"C++ was not preserved: {tokens}",
        )

    def test_tech_symbol_preservation_csharp(self):
        tokens = clean_and_tokenize("Proficient in C# and .NET development.")
        tokens_lower = [t.lower() for t in tokens]
        self.assertTrue(
            "c#" in tokens_lower or "csharp_lang" in tokens or "csharp" in tokens_lower,
            f"C# was not preserved: {tokens}",
        )
        self.assertTrue(
            ".net" in tokens_lower or "dotnet_framework" in tokens or "dotnet" in tokens_lower,
            f".NET was not preserved: {tokens}",
        )

    def test_tech_symbol_preservation_web_frameworks(self):
        tokens = clean_and_tokenize("Modern stack: Node.js, Next.js, and CI/CD automation.")
        tokens_lower = [t.lower() for t in tokens]
        self.assertTrue(
            any("node.js" in t or "nodejs" in t for t in tokens_lower),
            f"Node.js not preserved: {tokens}",
        )
        self.assertTrue(
            any("next.js" in t or "nextjs" in t for t in tokens_lower),
            f"Next.js not preserved: {tokens}",
        )
        self.assertTrue(
            any("ci/cd" in t or "cicd" in t for t in tokens_lower),
            f"CI/CD not preserved: {tokens}",
        )

    def test_tech_symbol_preservation_protocols(self):
        tokens = clean_and_tokenize("Low-level networking: TCP/IP sockets and RESTful API design.")
        tokens_lower = [t.lower() for t in tokens]
        self.assertTrue(
            any("tcp/ip" in t or "tcpip" in t for t in tokens_lower),
            f"TCP/IP not preserved: {tokens}",
        )

    def test_unicode_aware_tokenization(self):
        text = "Développeur sénior avec expérience en España et München: Python, FastAPI."
        tokens = clean_and_tokenize(text)
        self.assertGreater(len(tokens), 4)
        tokens_lower = [t.lower() for t in tokens]
        self.assertIn("python", tokens_lower)
        self.assertIn("fastapi", tokens_lower)

        # Regression tests required by P2-1:
        # 1. Bengali words and English tech term preserved
        bengali_tokens = clean_and_tokenize("আমি Python ডেভেলপার")
        self.assertEqual(bengali_tokens, ["আমি", "python", "ডেভেলপার"])

        # 2. Accented Latin characters preserved in full (not truncated to 'jos'/'garc')
        name_tokens = clean_and_tokenize("José García")
        self.assertEqual(name_tokens, ["josé", "garcía"])

    def test_empty_and_whitespace_tokenization(self):
        self.assertEqual(clean_and_tokenize(""), [])
        self.assertEqual(clean_and_tokenize("   \n\t  "), [])
        self.assertEqual(clean_and_tokenize(None), [])


    def test_stop_words_filter(self):
        self.assertIn("responsibilities", STOP_WORDS)
        self.assertIn("qualifications", STOP_WORDS)
        self.assertIn("candidate", STOP_WORDS)
        self.assertIn("opportunity", STOP_WORDS)
        self.assertIn("the", STOP_WORDS)
        self.assertIn("and", STOP_WORDS)
        self.assertGreaterEqual(len(STOP_WORDS), 200)


class TestTaxonomyAndAliases(unittest.TestCase):
    def test_no_duplicate_skills_across_categories(self):
        seen = {}
        for category, skills in SKILL_TAXONOMY.items():
            for s in skills:
                s_lower = s.lower().strip()
                self.assertNotIn(
                    s_lower,
                    seen,
                    f"Skill '{s_lower}' appears in multiple categories: '{seen.get(s_lower)}' and '{category}'",
                )
                seen[s_lower] = category

    """Section 2: Curated 1,000+ Multi-Discipline Skill Taxonomy Tests."""

    def test_taxonomy_domains_count(self):
        expected_domains = [
            "Languages & Runtimes",
            "Frontend & Mobile",
            "Backend & Frameworks",
            "Cloud, DevOps & Infrastructure",
            "Databases & Cache",
            "System Design & Architecture",
            "Testing & QA",
            "Methodologies, Soft Skills & Business",
            "Healthcare & Nursing",
            "Finance & Accounting",
            "Marketing & Sales",
            "Education & Training",
            "HR & Recruitment",
            "Operations & Logistics",
        ]
        for domain in expected_domains:
            self.assertIn(domain, SKILL_TAXONOMY, f"Missing domain: {domain}")
        self.assertEqual(len(SKILL_TAXONOMY), 14)

    def test_total_skills_lexicon_size(self):
        self.assertGreaterEqual(
            len(ALL_SKILLS), 1000,
            f"Expected at least 1,000 skills in taxonomy, got {len(ALL_SKILLS)}",
        )

    def test_domain_lexicon_sizes(self):
        for domain, skills in SKILL_TAXONOMY.items():
            self.assertGreaterEqual(
                len(skills), 50,
                f"Domain {domain} has only {len(skills)} skills",
            )

    def test_skill_alias_resolution(self):
        self.assertEqual(normalize_skill("k8s"), "kubernetes")
        self.assertEqual(normalize_skill("postgres"), "postgresql")
        self.assertEqual(normalize_skill("react.js"), "react")
        self.assertEqual(normalize_skill("js"), "javascript")
        self.assertEqual(normalize_skill("ts"), "typescript")
        self.assertEqual(normalize_skill("py"), "python")
        self.assertEqual(normalize_skill("tf"), "terraform")
        self.assertEqual(normalize_skill("gha"), "github actions")

    def test_action_verbs_comprehensive(self):
        self.assertGreaterEqual(len(ACTION_VERBS), 50)
        required_verbs = [
            "architected", "engineered", "designed", "developed",
            "spearheaded", "optimized", "scaled", "automated",
            "led", "mentored", "orchestrated", "reduced", "delivered",
        ]
        for v in required_verbs:
            self.assertIn(v, ACTION_VERBS)

    def test_standard_sections_count(self):
        self.assertGreaterEqual(len(STANDARD_SECTIONS), 20)
        self.assertIn("work experience", STANDARD_SECTIONS)
        self.assertIn("education", STANDARD_SECTIONS)
        self.assertIn("skills", STANDARD_SECTIONS)


class TestNGramAndFuzzyMatching(unittest.TestCase):
    """Section 3: N-Gram & Semantic Phrase Extraction Tests."""

    def test_unigram_bigram_trigram_extraction(self):
        tokens = ["distributed", "event", "driven", "architecture", "microservices"]
        unigrams = extract_ngrams(tokens, 1)
        bigrams = extract_ngrams(tokens, 2)
        trigrams = extract_ngrams(tokens, 3)

        self.assertEqual(len(unigrams), 5)
        self.assertEqual(len(bigrams), 4)
        self.assertEqual(len(trigrams), 3)
        self.assertEqual(bigrams[0], "distributed event")
        self.assertEqual(trigrams[0], "distributed event driven")

    def test_levenshtein_distance(self):
        self.assertEqual(_levenshtein_distance("docker", "docker"), 0)
        self.assertEqual(_levenshtein_distance("docker", "dockers"), 1)
        self.assertEqual(_levenshtein_distance("postgre", "postgres"), 1)
        self.assertEqual(_levenshtein_distance("react", "angular"), 7)

    def test_fuzzy_skill_matching(self):
        # 1-distance variation should match
        matched = _fuzzy_skill_match("kubernete", ALL_SKILLS, max_distance=1)
        self.assertEqual(matched, "kubernetes")

        # Completely different word should not match
        unmatched = _fuzzy_skill_match("xylophone", ALL_SKILLS, max_distance=1)
        self.assertIsNone(unmatched)

    def test_keyword_extraction_with_frequencies(self):
        jd = """
        Looking for a Senior Python Developer with FastAPI and PostgreSQL experience.
        Must have deep knowledge of Python, Docker, Kubernetes, and AWS.
        FastAPI microservices and PostgreSQL optimization required.
        """
        kws = extract_keywords_with_frequencies(jd, top_k=20)
        kw_names = [k for k, _ in kws]

        self.assertIn("python", kw_names)
        self.assertIn("fastapi", kw_names)
        self.assertIn("postgresql", kw_names)
        self.assertIn("docker", kw_names)




if __name__ == "__main__":
    unittest.main()


class TestInternationalAndNonTechSupport(unittest.TestCase):
    """Section 5: P2-1 Regression Tests for International Formats & Non-Tech Disciplines."""

    def test_international_phone_formats(self):
        """Verify Bangladesh (+880), UK (+44), India (+91), E.164, and US (555) phones are detected."""
        from openats.engine import audit_resume_structure

        # Bangladesh +880 format
        res_bd = audit_resume_structure("Nazmul Hossain\nPhone: +880 1712-345678\nEmail: test@example.com")
        self.assertTrue(res_bd["has_phone"], "+880 1712-345678 must set has_phone True")

        # UK +44 format
        res_uk = audit_resume_structure("John Smith\nTel: +44 20 7946 0912\nEmail: john@uk.co")
        self.assertTrue(res_uk["has_phone"], "+44 UK phone must set has_phone True")

        # India +91 format
        res_in = audit_resume_structure("Aarav Sharma\nMobile: +91 98765 43210\nEmail: aarav@in.com")
        self.assertTrue(res_in["has_phone"], "+91 India phone must set has_phone True")

        # Generic E.164 format
        res_e164 = audit_resume_structure("Elena Rostova\nPhone: +491701234567\nEmail: elena@de.de")
        self.assertTrue(res_e164["has_phone"], "Generic E.164 phone must set has_phone True")

        # Existing North American (555) format still passing
        res_us = audit_resume_structure("Jane Doe\nPhone: (555) 123-4567\nEmail: jane@us.com")
        self.assertTrue(res_us["has_phone"], "(555) US phone must set has_phone True")

    def test_bengali_stop_words_filtering(self):
        """Verify Bengali stop words are excluded from extracted keywords when Bengali script is present."""
        from openats.engine import extract_keywords_with_frequencies
        bengali_text = "আমি একজন সিনিয়র পাইথন ডেভেলপার এবং এর জন্য পাঁচ বছর ধরে কাজ করছি।"
        keywords = [k for k, _ in extract_keywords_with_frequencies(bengali_text, 20)]
        self.assertNotIn("আমি", keywords)
        self.assertNotIn("এবং", keywords)
        self.assertNotIn("এর", keywords)
        self.assertNotIn("জন্য", keywords)

    def test_healthcare_nurse_non_tech_matching(self):
        """Verify Nurse JD matching populates Healthcare & Nursing in skill_breakdown with a realistic score."""
        from openats.engine import analyze_ats_match

        jd = """
        Registered Nurse (RN) - Intensive Care Unit
        Requirements:
        - Acute patient care and emergency triage
        - IV therapy and sterile technique
        - Active BLS certification
        - Proficiency in electronic health records
        """

        resume = """
        Staff Nurse RN
        Email: nurse@example.com
        Phone: +880 1712-345678

        Professional Summary:
        Experienced registered nurse providing patient care, triage, and iv therapy.

        Work Experience:
        ICU Staff Nurse (2021 - Present)
        - Maintained patient care and performed rapid triage for trauma admissions.
        - Administered iv therapy and medications following sterile technique protocols.
        - Certified in bls and acls life support.

        Education:
        B.S. in Nursing
        """

        res = analyze_ats_match(resume, jd)
        breakdown = res.get("skill_breakdown", {})
        self.assertIn("Healthcare & Nursing", breakdown, "Healthcare & Nursing must appear in skill_breakdown")
        matched_healthcare = breakdown["Healthcare & Nursing"]["matched"]
        self.assertIn("patient care", matched_healthcare)
        self.assertIn("triage", matched_healthcare)
        self.assertIn("iv therapy", matched_healthcare)
        self.assertIn("bls", matched_healthcare)

        sub = res["sub_scores"]
        self.assertTrue(sub["skill_match_available"])
        self.assertIsNotNone(sub["skill_match"])
        # Should be a real match percentage, not defaulted to 100% or None
        self.assertGreater(sub["skill_match"], 50.0)
        self.assertLessEqual(sub["skill_match"], 100.0)
