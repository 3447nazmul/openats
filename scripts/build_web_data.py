#!/usr/bin/env python3
"""
Build Web Data Script for OpenATS.
Exports taxonomy, aliases, verbs, sections, stop words, and tech symbol maps
from openats/taxonomy.py and openats/star_enhancer.py to a clean JSON file and embeds it into index.html.
Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""

import os
import sys
import json
import shutil

# Ensure project root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from openats.taxonomy import (
    SKILL_TAXONOMY,
    ALL_SKILLS,
    SKILL_ALIASES,
    ACTION_VERBS,
    STANDARD_SECTIONS,
    STOP_WORDS,
    BENGALI_STOP_WORDS,
)
from openats.engine import TECH_SYMBOL_MAP
from openats.star_enhancer import GERUND_TO_PAST

def build_data():
    # Flatten ACTION_VERBS into a set/list of lowercase verbs
    verbs_list = []
    if isinstance(ACTION_VERBS, dict):
        for vlist in ACTION_VERBS.values():
            for v in vlist:
                if v.lower() not in verbs_list:
                    verbs_list.append(v.lower())
    else:
        verbs_list = sorted(list({v.lower() for v in ACTION_VERBS}))

    web_data = {
        "SKILL_TAXONOMY": SKILL_TAXONOMY,
        "ALL_SKILLS": ALL_SKILLS,
        "SKILL_ALIASES": SKILL_ALIASES,
        "ACTION_VERBS": verbs_list,
        "STANDARD_SECTIONS": STANDARD_SECTIONS,
        "STOP_WORDS": sorted(list(STOP_WORDS)),
        "BENGALI_STOP_WORDS": sorted(list(BENGALI_STOP_WORDS)),
        "TECH_SYMBOL_MAP": TECH_SYMBOL_MAP,
        "GERUND_TO_PAST": GERUND_TO_PAST,
    }

    # 1. Write standalone JSON file
    templates_dir = os.path.join(repo_root, "openats", "templates")
    os.makedirs(templates_dir, exist_ok=True)
    json_path = os.path.join(templates_dir, "skills.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(web_data, f, indent=2, ensure_ascii=False)
    print(f"Exported taxonomy JSON: {json_path} ({os.path.getsize(json_path):,} bytes)")

    # 2. Embed into root index.html and sync to openats/templates/index.html
    update_index_html(web_data)

    return web_data

def update_index_html(web_data):
    root_html_path = os.path.join(repo_root, "index.html")
    tmpl_html_path = os.path.join(repo_root, "openats", "templates", "index.html")
    engine_js_path = os.path.join(repo_root, "scripts", "parity_engine.js")

    with open(root_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    with open(engine_js_path, "r", encoding="utf-8") as f:
        engine_js = f.read()

    # Create the embedded engine block
    json_str = json.dumps(web_data, ensure_ascii=False)
    
    embedded_engine = f"""/* === BEGIN OPENATS CLIENT ENGINE (GENERATED) === */
const OPENATS_DATA = {json_str};

{engine_js}

function analyze(resume, jd) {{
  const res = analyzeATS(resume, jd);
  
  const kws = [];
  for (const m of res.matched_keywords) {{
    kws.push({{
      w: m.keyword,
      cat: m.category || (m.importance === 'Critical' ? 'Hard skills' : 'Role terms'),
      wt: m.weight,
      ok: true
    }});
  }}
  for (const m of res.missing_keywords) {{
    kws.push({{
      w: m.keyword,
      cat: m.category || (m.importance === 'Critical' ? 'Hard skills' : 'Role terms'),
      wt: m.weight,
      ok: false
    }});
  }}
  
  const formattedRecs = [];
  if (res.recommendations && res.recommendations.length) {{
    for (const rec of res.recommendations) {{
      let level = 'med';
      if (rec.includes('🌟') || rec.includes('Low') || rec.includes('Strong')) level = 'low';
      else if (rec.includes('🚨') || rec.includes('Critical') || rec.includes('Mirror') || rec.includes('Formatting')) level = 'high';
      formattedRecs.push([level, rec.replace(/^[•🌟✅⚠️🚨\\s]+/, '').replace(/\\*\\*/g, '')]);
    }}
  }}

  return {{
    raw: res,
    kws: kws,
    kw: res.sub_scores.keyword_match,
    skills: res.sub_scores.skill_match !== null ? res.sub_scores.skill_match : res.sub_scores.keyword_match,
    st: {{
      score: res.sub_scores.structure_compliance,
      checks: [
        {{ ok: res.structure_audit.has_email, pts: 12, label: 'Email address', fix: 'Add a professional email address to your header.' }},
        {{ ok: res.structure_audit.has_phone, pts: 8, label: 'Phone number', fix: 'Add a phone number to your header.' }},
        {{ ok: res.structure_audit.has_links, pts: 5, label: 'Professional links', fix: 'Add a LinkedIn, GitHub, or portfolio URL.' }},
        {{ ok: res.structure_audit.detected_sections.includes('Work Experience'), pts: 20, label: 'Experience section', fix: 'Add an "Experience" or "Work Experience" section.' }},
        {{ ok: res.structure_audit.detected_sections.includes('Education'), pts: 15, label: 'Education section', fix: 'Add an "Education" section with a standard heading.' }},
        {{ ok: res.structure_audit.detected_sections.includes('Skills'), pts: 15, label: 'Skills section', fix: 'Add a dedicated "Skills" section listing your tools.' }},
        {{ ok: res.structure_audit.detected_sections.includes('Professional Summary'), pts: 5, label: 'Summary', fix: 'Open with a concise professional summary.' }},
        {{ ok: res.structure_audit.word_count >= 300 && res.structure_audit.word_count <= 1000, pts: 10, label: 'Length', fix: res.structure_audit.word_count < 300 ? 'Expand your resume. Aim for 300 words or more.' : 'Trim to 1-2 pages. Aim for under 1,000 words.' }},
        {{ ok: res.structure_audit.total_bullets >= 3, pts: 10, label: 'Scannable bullets', fix: 'Use bullet points for your achievements.' }}
      ]
    }},
    star: {{
      score: res.sub_scores.measurable_impact,
      m: res.structure_audit.bullets_with_metrics,
      a: res.structure_audit.bullets_with_action_verbs,
      n: res.structure_audit.total_bullets
    }},
    total: res.final_score,
    recs: formattedRecs
  }};
}}

function recs(r) {{
  if (r.recs && r.recs.length) return r.recs;
  return [];
}}

const tier = s => s >= 80 ? ['Excellent match', '#4ade80'] : s >= 65 ? ['Strong match', '#86efac'] : s >= 50 ? ['Moderate match', '#fbbf24'] : ['Needs optimization', '#f87171'];

const hasMetric = s => /(\\d\\s?%|[$£€]\\s?\\d|\\b\\d+(?:\\.\\d+)?\\s?(?:x|k|m|million|billion|users|clients|customers|hours|days|weeks|months|people|members|projects|accounts|leads|orders)\\b)/i.test(s) || /\\b(?!(?:19|20)\\d\\d\\b)\\d{{2,}}\\b/.test(s);

const GERUND_MAP = OPENATS_DATA.GERUND_TO_PAST || {{}};
function gerundToPast(w) {{
  const low = w.toLowerCase().trim();
  if (GERUND_MAP[low]) return GERUND_MAP[low];
  if (!low.endsWith('ing') || low.length <= 4) return null;
  const base = low.slice(0, -3);
  if (base.length >= 3 && base[base.length - 1] === base[base.length - 2] && 'bcdgklmnprstz'.includes(base[base.length - 1])) {{
    return (base + 'ed')[0].toUpperCase() + (base + 'ed').slice(1);
  }}
  if (base.endsWith('at') || base.endsWith('iz') || base.endsWith('us') || base.endsWith('clos') || base.endsWith('mov') || base.endsWith('liv') || base.endsWith('sav')) {{
    return (base + 'ed')[0].toUpperCase() + (base + 'ed').slice(1);
  }}
  return (base + 'ed')[0].toUpperCase() + (base + 'ed').slice(1);
}}

const LEAD = /^(?:was |were )?(?:responsible for|in charge of|tasked with|duties included|involved in|worked on|helped with|helped to|assisted with|assisted in|helping with|participated in)\\s+(?:the\\s+)?/i;

function optimize(raw) {{
  let s = raw.replace(/^[\\s•\\-*▪●◦·–\\d\\.]+/, '').replace(/\\s+/g, ' ').trim(), weak = false;
  if (LEAD.test(s)) {{
    const leadMatch = s.match(LEAD)[0].toLowerCase().trim();
    const r = s.replace(LEAD, '').trim();
    const words = r.split(' ');
    const firstWord = words[0] || '';
    const rest = words.slice(1).join(' ').trim();
    const pastVerb = gerundToPast(firstWord);

    if (leadMatch.includes('helped with') && rest.toLowerCase().startsWith('ticket')) {{
      s = 'Resolved ' + rest + ' with the support team';
    }} else if (pastVerb) {{
      s = pastVerb + ' ' + rest;
    }} else {{
      const v = leadMatch.includes('responsible') ? 'Directed' : 'Spearheaded';
      s = v + ' ' + (r.length > 1 ? r[0].toLowerCase() + r.slice(1) : r);
    }}
    weak = true;
  }}
  s = s[0].toUpperCase() + s.slice(1);
  const first = s.split(' ')[0].toLowerCase().replace(/[^a-z]/g, '');
  const verb = ACTION_VERBS.has(first) || weak;
  const words = s.split(' ').length;
  const metric = hasMetric(s);
  const draft = s.replace(/[.\\s]+$/, '') + (metric ? '' : ' [ADD YOUR REAL RESULT: e.g. reduced time by __%]') + '.';
  const tips = [];
  if (!verb) tips.push('Open with a strong action verb such as Led, Built, Architected or Optimized.');
  if (words < 9) tips.push('Add context: the project, team size or tool you used.');
  if (!metric) {{
    tips.push('Quantify your impact with a measurable metric (%, $, time saved, user volume).');
    tips.push('Replace the bracket with a real number from your experience. Do not guess.');
  }}
  tips.push('Follow the STAR flow: Situation, Task, Action, Result. Put the result last.');
  const low = s.toLowerCase();
  const ks = S.res ? S.res.kws.filter(k => !k.ok && !low.includes(k.w)).slice(0, 5) : [];
  const chips = [['Action verb', verb], ['Context', words >= 9], ['Quantified result', metric]].map(([l, ok]) => `<div class="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm" style="color:${{ok ? '#86efac' : '#fca5a5'}};border-color:${{ok ? '#1f5f3b' : '#5f2a2a'}}">${{ico(ok ? 'check' : 'x')}}${{l}}</div>`).join('');
  return `<div class="grid gap-3 sm:grid-cols-3">${{chips}}</div>
<p class="mb-2 mt-6 text-sm text-mute">Optimized draft</p>
<div class="flex items-start justify-between gap-3 rounded-lg border border-line bg-canvas p-4 text-sm"><p>${{esc(draft)}}</p><button class="btn btn-ghost shrink-0" data-act="copy" data-t="${{esc(draft)}}" aria-label="Copy draft">${{ico('copy')}}</button></div>
<ul class="mt-4 space-y-1.5 text-sm text-mute">${{tips.map(t => `<li>${{esc(t)}}</li>`).join('')}}</ul>
${{ks.length ? `<p class="mb-2 mt-5 text-sm text-mute">Weave in if true for you</p><div class="flex flex-wrap gap-2">${{ks.map(k => `<button class="tag" data-act="copy" data-t="${{esc(k.w)}}">${{ico('copy', 'h-3 w-3')}}${{esc(k.w)}}</button>`).join('')}}</div>` : ''}}`;
}}
/* === END OPENATS CLIENT ENGINE (GENERATED) === */"""

    start_marker = "/* === BEGIN OPENATS CLIENT ENGINE (GENERATED) === */"
    end_marker = "/* === END OPENATS CLIENT ENGINE (GENERATED) === */"
    
    if start_marker in html_content and end_marker in html_content:
        pre = html_content[:html_content.find(start_marker)]
        post = html_content[html_content.find(end_marker) + len(end_marker):]
        new_html = pre + embedded_engine + post
    else:
        # Fallback to initial markers
        old_start = "/* Keyword data */"
        old_end = "/* State and inputs */"
        pre = html_content[:html_content.find(old_start)]
        post = html_content[html_content.find(old_end):]
        new_html = pre + embedded_engine + "\n\n" + post

    with open(root_html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    print(f"Updated {root_html_path} ({os.path.getsize(root_html_path):,} bytes)")

    shutil.copyfile(root_html_path, tmpl_html_path)
    print(f"Synced {tmpl_html_path}")

if __name__ == "__main__":
    build_data()
