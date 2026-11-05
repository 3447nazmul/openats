"""
OpenATS Command Line Interface.
Run ATS scans directly from your terminal with rich formatted output or JSON.
Supports .pdf, .docx, .txt, and .md input files and layout format simulation audits.
Created by Nazmul (@3447nazmul) - https://github.com/3447nazmul/openats
"""
import sys
import os
import argparse
import json
from openats import __version__, __author__, __repository__
from openats.engine import analyze_ats_match
from openats.extract import extract_text, ExtractionError
from openats.format_audit import audit_resume_format
from openats.star_enhancer import analyze_bullet_point
from openats.updater import check_for_updates


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description=f"OpenATS v{__version__} - Privacy-First ATS Resume Matcher by {__author__}"
    )
    parser.add_argument(
        "--resume", "-r", required=False,
        help="Path to your resume file (.pdf, .docx, .txt, .md)"
    )
    parser.add_argument(
        "--jd", "-j", required=False,
        help="Path to the target job description file (.pdf, .docx, .txt, .md)"
    )
    parser.add_argument("--json", action="store_true", help="Output results in raw JSON format")
    parser.add_argument("--bullet", "-b", help="Optimize a single resume bullet point")
    parser.add_argument("--check-update", action="store_true", help="Check for official GitHub updates")
    parser.add_argument(
        "--include-contact", action="store_true",
        help="Include raw email and phone contact values in output"
    )
    parser.add_argument(
        "--format-check", action="store_true",
        help="Run layout and formatting simulation audit"
    )
    args = parser.parse_args(argv)

    if args.check_update:
        up = check_for_updates(__version__)
        if up["update_available"]:
            print(f"\n⚡ New version {up['latest_version']} is available! ({up['release_url']})\n")
        else:
            print(f"\n✓ You are running the latest version of OpenATS (v{__version__}).\n")
        if not args.resume and not args.jd and not args.bullet:
            return 0

    if args.bullet:
        res = analyze_bullet_point(args.bullet)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print("\n--- STAR Bullet Point Analysis ---")
            print(f"Score: {res['score']}/100")
            print(f"Action Verb: {res['action_verb'] or 'None detected'}")
            print(f"Quantifiable Metric: {res['has_metric']}")
            print("Feedback:")
            for fb in res["feedback"]:
                print(f"  • {fb}")
            if res["suggested_rewrites"]:
                print("Suggested Rewrites:")
                for rw in res["suggested_rewrites"]:
                    print(f"  ✓ {rw}")
            print()
        return 0

    if not args.resume or not args.jd:
        parser.error("the following arguments are required: --resume/-r, --jd/-j")
        return 2

    if not os.path.exists(args.resume):
        print(f"Error: Resume file '{args.resume}' not found.", file=sys.stderr)
        return 1

    if not os.path.exists(args.jd):
        print(f"Error: Job description file '{args.jd}' not found.", file=sys.stderr)
        return 1

    try:
        resume_text = extract_text(args.resume)
    except (ExtractionError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error reading resume '{args.resume}': {exc}", file=sys.stderr)
        return 1

    try:
        jd_text = extract_text(args.jd)
    except (ExtractionError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error reading job description '{args.jd}': {exc}", file=sys.stderr)
        return 1

    result = analyze_ats_match(resume_text, jd_text, include_contact=args.include_contact)

    # Format layout check: runs for PDF/DOCX automatically, or with --format-check for text
    resume_ext = os.path.splitext(args.resume)[1].lower()
    should_audit_format = resume_ext in (".pdf", ".docx") or args.format_check
    format_audit_result = None
    if should_audit_format:
        format_audit_result = audit_resume_format(args.resume)

    if args.json:
        if format_audit_result:
            result["format_audit"] = format_audit_result
        print(json.dumps(result, indent=2))
        return 0

    score = result["final_score"]
    sub = result["sub_scores"]

    print("\n" + "=" * 65)
    print(f" ⚡ OpenATS v{__version__} — ATS Scorecard & Compliance Audit")
    print(f" 👤 Created by: {__author__} ({__repository__})")
    print("=" * 65)
    print(f" Overall Match Score:  {score}%  [{result['score_tier']}]")
    print("-" * 65)
    print(f" • Keyword Overlap:     {sub['keyword_match']}%  (Weight: 40%)")

    if sub.get("skill_match_available") is False or sub.get("skill_match") is None:
        skills_str = "N/A - no taxonomy skills found in this job description"
    else:
        skills_str = f"{sub['skill_match']}%  (Weight: 30%)"
    print(f" • Skills Coverage:     {skills_str}")

    print(f" • Section Compliance:  {sub['structure_compliance']}%  (Weight: 20%)")
    print(f" • STAR Impact Metrics: {sub['measurable_impact']}%  (Weight: 10%)")
    print("=" * 65)

    if result.get("stuffing_warning"):
        print(f"\n🚨 WARNING: {result['stuffing_warning']}")
    if result.get("language_warning"):
        print(f"\n⚠️  NOTICE: {result['language_warning']}")

    print("\n🚨 Missing High-Priority Keywords:")
    if result["missing_keywords"]:
        for item in result["missing_keywords"][:8]:
            print(f"  [-] {item['keyword']} (Found {item['jd_count']}x in Job Description) [{item.get('importance', 'Medium')}]")
    else:
        print("  [✓] Great job! All essential keywords found.")

    print("\n✅ Top Matched Keywords:")
    for item in result["matched_keywords"][:8]:
        print(f"  [+] {item['keyword']} ({item['resume_count']}x in Resume)")

    print("\n💡 Strategic Recommendations:")
    for rec in result["recommendations"]:
        print(f"  {rec.replace('**', '')}")

    # Format simulation warnings section
    if should_audit_format and format_audit_result:
        findings = format_audit_result.get("findings", [])
        print("\n📄 Format & Parsing Simulation Warnings:")
        if findings:
            for f in findings:
                sev = f["severity"].upper()
                pg = f" (Page {f['page']})" if f.get("page") else ""
                print(f"  [{sev}] {f['message']}{pg}")
                print(f"    Fix: {f['fix']}")
        else:
            print("  [✓] Clean layout! No multi-column, table, or margin parsing traps detected.")
        print(f"  ℹ️  {format_audit_result.get('disclaimer', '')}")

    print("\n" + "=" * 65 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
