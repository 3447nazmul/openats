// OpenATS Client-Side JS Engine with exact parity to openats/engine.py
let data;
if (typeof OPENATS_DATA !== "undefined") {
  data = OPENATS_DATA;
} else if (typeof window !== "undefined" && window.OPENATS_DATA) {
  data = window.OPENATS_DATA;
} else if (typeof require !== "undefined") {
  const fs = require("fs");
  const path = require("path");
  const p = path.resolve(__dirname, "../openats/templates/skills.json");
  data = JSON.parse(fs.readFileSync(p, "utf8"));
}

const SKILL_TAXONOMY = data.SKILL_TAXONOMY;
const ALL_SKILLS = data.ALL_SKILLS;
const SKILL_ALIASES = data.SKILL_ALIASES;
const ACTION_VERBS = new Set(data.ACTION_VERBS);
const STANDARD_SECTIONS = data.STANDARD_SECTIONS;
const STOP_WORDS = new Set(data.STOP_WORDS);
const BENGALI_STOP_WORDS = new Set(data.BENGALI_STOP_WORDS || []);
const TECH_SYMBOL_MAP = data.TECH_SYMBOL_MAP;

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function protectTechSymbols(text) {
  let s = text.toLowerCase();
  for (const [sym, place] of Object.entries(TECH_SYMBOL_MAP)) {
    try {
      const reg = new RegExp('\\b' + escapeRegex(sym) + '\\b', 'g');
      s = s.replace(reg, place);
    } catch (e) {
      s = s.split(sym).join(place);
    }
  }
  return s;
}

function restoreTechSymbols(token) {
  for (const [sym, place] of Object.entries(TECH_SYMBOL_MAP)) {
    if (token === place) return sym;
  }
  return token;
}

function cleanAndTokenize(text) {
  if (!text) return [];
  const protectedText = protectTechSymbols(text);
  const rawMatches = protectedText.match(/[\p{L}\p{M}_][\p{L}\p{M}\p{N}_\-\./]{0,30}/gu) || [];
  const tokens = [];
  for (const token of rawMatches) {
    const cleanedTok = token.replace(/[\.\-]+$/, '');
    const restored = restoreTechSymbols(cleanedTok);
    if (restored && restored.length >= 1) {
      tokens.push(restored);
    }
  }
  return tokens;
}

function normalizeSkill(skill) {
  const lower = skill.toLowerCase().trim();
  if (lower in SKILL_ALIASES) return SKILL_ALIASES[lower];
  if (lower in ALL_SKILLS) return lower;
  return lower;
}

function extractNgrams(tokens, n) {
  if (tokens.length < n) return [];
  const out = [];
  for (let i = 0; i <= tokens.length - n; i++) {
    out.push(tokens.slice(i, i + n).join(' '));
  }
  return out;
}

function levenshteinDistance(s1, s2) {
  if (s1.length < s2.length) return levenshteinDistance(s2, s1);
  if (!s2.length) return s1.length;
  let prevRow = Array.from({ length: s2.length + 1 }, (_, i) => i);
  for (let i = 0; i < s1.length; i++) {
    const curRow = [i + 1];
    for (let j = 0; j < s2.length; j++) {
      const insertions = prevRow[j + 1] + 1;
      const deletions = curRow[j] + 1;
      const substitutions = prevRow[j] + (s1[i] !== s2[j] ? 1 : 0);
      curRow.push(Math.min(insertions, deletions, substitutions));
    }
    prevRow = curRow;
  }
  return prevRow[prevRow.length - 1];
}

function fuzzySkillMatch(token, candidates, maxDistance = 1) {
  const t = token.toLowerCase();
  if (t in candidates) return t;
  if (t.length <= 4) return null;
  for (const skill of Object.keys(candidates)) {
    if (Math.abs(skill.length - t.length) <= maxDistance) {
      if (levenshteinDistance(t, skill) <= maxDistance) {
        return skill;
      }
    }
  }
  return null;
}

function getAllSkillForms(term) {
  const tClean = term.toLowerCase().trim();
  const forms = new Set([tClean]);
  const canonical = SKILL_ALIASES[tClean] || tClean;
  forms.add(canonical.toLowerCase());
  for (const [alias, target] of Object.entries(SKILL_ALIASES)) {
    if (target.toLowerCase() === canonical.toLowerCase()) {
      forms.add(alias.toLowerCase());
    }
  }
  if (SKILL_ALIASES[canonical.toLowerCase()]) {
    forms.add(SKILL_ALIASES[canonical.toLowerCase()].toLowerCase());
  }
  for (const f of Array.from(forms)) {
    if (f.includes('.')) {
      forms.add(f.replace(/\./g, ''));
      forms.add(f.replace(/\./g, ' '));
    }
  }
  return forms;
}

function isSkillOrAlias(token) {
  const t = token.toLowerCase().trim();
  return (t in ALL_SKILLS) || (t in SKILL_ALIASES);
}

function isSkillConcatenation(phrase) {
  const pLower = phrase.toLowerCase().trim();
  if (pLower in ALL_SKILLS) return false;
  const words = pLower.split(/\s+/);
  if (words.length < 2) return false;
  return words.every(isSkillOrAlias);
}

function isJobTitleFragment(phrase, titleLine) {
  const pLower = phrase.toLowerCase().trim();
  if (pLower in ALL_SKILLS) return false;
  if (titleLine && titleLine.toLowerCase().includes(pLower)) return true;
  const words = pLower.split(/\s+/);
  const roleWords = new Set(["engineer", "developer", "architect", "manager", "director", "consultant", "analyst", "specialist", "intern", "associate", "candidate", "role", "position"]);
  return words.some(w => roleWords.has(w));
}

function countOccurrencesInText(term, textLower) {
  const forms = getAllSkillForms(term);
  let cnt = 0;
  for (const f of forms) {
    try {
      const reg = new RegExp('\\b' + escapeRegex(f) + '\\b', 'g');
      const m = textLower.match(reg);
      if (m) cnt += m.length;
    } catch (e) {
      cnt += textLower.split(f).length - 1;
    }
  }
  if (cnt === 0) {
    cnt = textLower.split(term.toLowerCase()).length - 1;
  }
  return Math.max(1, cnt);
}

function extractKeywordsWithFrequencies(text, topK = 40) {
  if (!text || !text.trim()) return [];
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const firstLine = lines.length ? lines[0].toLowerCase() : "";

  const tokens = cleanAndTokenize(text);
  const isBengali = /[ঀ-৿]/.test(text);
  const meaningfulTokens = tokens.filter(t => {
    const tl = t.toLowerCase();
    if (STOP_WORDS.has(tl)) return false;
    if (isBengali && BENGALI_STOP_WORDS.has(tl)) return false;
    return t.length > 1;
  });
  if (!meaningfulTokens.length) return [];

  const unigramCounts = {};
  for (const t of meaningfulTokens) {
    unigramCounts[t] = (unigramCounts[t] || 0) + 1;
  }

  const bigrams = extractNgrams(meaningfulTokens, 2);
  const trigrams = extractNgrams(meaningfulTokens, 3);

  const bigramCounts = {};
  for (const bg of bigrams) bigramCounts[bg] = (bigramCounts[bg] || 0) + 1;

  const filteredBigrams = {};
  for (const [bg, count] of Object.entries(bigramCounts)) {
    const bgLower = bg.toLowerCase().trim();
    if (bgLower in ALL_SKILLS) {
      filteredBigrams[bg] = count;
    } else if (count >= 2) {
      if (!isSkillConcatenation(bgLower) && !isJobTitleFragment(bgLower, firstLine)) {
        filteredBigrams[bg] = count;
      }
    }
  }

  const trigramCounts = {};
  for (const tg of trigrams) trigramCounts[tg] = (trigramCounts[tg] || 0) + 1;

  const filteredTrigrams = {};
  for (const [tg, count] of Object.entries(trigramCounts)) {
    const tgLower = tg.toLowerCase().trim();
    if (tgLower in ALL_SKILLS) {
      filteredTrigrams[tg] = count;
    } else if (count >= 2) {
      if (!isSkillConcatenation(tgLower) && !isJobTitleFragment(tgLower, firstLine)) {
        filteredTrigrams[tg] = count;
      }
    }
  }

  const totalTokens = meaningfulTokens.length || 1;
  const weightedKeywords = {};

  const roleWords = new Set(["engineer", "developer", "architect", "manager", "director", "consultant", "analyst", "candidate"]);
  for (const [token, count] of Object.entries(unigramCounts)) {
    const tLower = token.toLowerCase();
    if (roleWords.has(tLower) && !(tLower in ALL_SKILLS)) continue;
    const tf = count / totalTokens;
    let skillBoost = (tLower in ALL_SKILLS) ? 2.0 : 1.0;
    if (tLower in SKILL_ALIASES) skillBoost = 1.8;
    const weight = tf * skillBoost * (1 + Math.log(1 + count));
    weightedKeywords[tLower] = weight;
  }

  for (const [bigram, count] of Object.entries(filteredBigrams)) {
    const tf = count / Math.max(totalTokens - 1, 1);
    const skillBoost = (bigram.toLowerCase() in ALL_SKILLS) ? 2.5 : 1.2;
    const weight = tf * skillBoost * (1 + Math.log(1 + count));
    weightedKeywords[bigram.toLowerCase()] = weight * 1.3;
  }

  for (const [trigram, count] of Object.entries(filteredTrigrams)) {
    const tf = count / Math.max(totalTokens - 2, 1);
    const skillBoost = (trigram.toLowerCase() in ALL_SKILLS) ? 3.0 : 1.1;
    const weight = tf * skillBoost * (1 + Math.log(1 + count));
    weightedKeywords[trigram.lower ? trigram.lower() : trigram.toLowerCase()] = weight * 1.5;
  }

  const lowerText = text.toLowerCase();
  for (const skill of Object.keys(ALL_SKILLS)) {
    if (skill.length >= 2 && lowerText.includes(skill)) {
      if (!(skill in weightedKeywords)) {
        try {
          const reg = new RegExp('\\b' + escapeRegex(skill) + '\\b', 'g');
          const matches = lowerText.match(reg);
          if (matches && matches.length) {
            const count = matches.length;
            const tf = count / totalTokens;
            weightedKeywords[skill] = tf * 2.0 * (1 + Math.log(1 + count));
          }
        } catch (e) {}
      }
    }
  }

  const sortedKeywords = Object.entries(weightedKeywords).sort((a, b) => b[1] - a[1]);
  return sortedKeywords.slice(0, topK);
}

function auditResumeStructure(resumeText, includeContact = false) {
  if (!resumeText || !resumeText.trim()) {
    return {
      structure_score: 0,
      has_email: false,
      has_phone: false,
      has_links: false,
      detected_sections: [],
      missing_sections: [],
      total_bullets: 0,
      bullets_with_action_verbs: 0,
      bullets_with_metrics: 0,
      red_flags: ["Resume text is empty."],
      word_count: 0
    };
  }

  const lower = resumeText.toLowerCase();
  const emailMatch = resumeText.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/);
  const phoneMatch = resumeText.match(/(?:(?:\+?880\s*[-.]?\s*|0)1[3-9]\d{2}[\s.\-]*\d{6}\b|(?:\+?44\s*[-.]?\s*|0)(?:\d{2,4}[\s.\-]*\d{3,4}[\s.\-]*\d{3,4})\b|(?:\+?91\s*[-.]?\s*)[6-9]\d{4}[\s.\-]*\d{5}\b|\+[1-9]\d{7,14}\b|(?:\+?1\s*[-.]?\s*)?(?:\(?\d{3}\)?[\s.\-]*)\d{3}[\s.\-]*\d{4}\b)/);
  const linkedinMatch = resumeText.match(/linkedin\.com\/in\/[\w\-]+/i);
  const githubMatch = resumeText.match(/github\.com\/[\w\-]+/i);
  const portfolioMatch = resumeText.match(/(?:portfolio|website|blog)\s*[:\|]?\s*(?:https?:\/\/)?[\w.\-]+\.\w{2,}/i);

  const hasEmail = Boolean(emailMatch);
  const hasPhone = Boolean(phoneMatch);
  const hasLinks = Boolean(linkedinMatch || githubMatch || portfolioMatch);

  const keySections = {
    "Contact Info": ["email", "phone", "contact", "address"],
    "Professional Summary": ["summary", "profile", "about me", "objective", "professional summary", "executive summary", "career summary", "professional profile"],
    "Work Experience": ["experience", "employment", "work history", "work experience", "professional experience", "career history", "employment history"],
    "Education": ["education", "academic", "degree", "university", "college", "credentials", "qualifications"],
    "Skills": ["skills", "technical skills", "technologies", "competencies", "core competencies", "tech stack", "tools"],
    "Projects": ["projects", "personal projects", "portfolio", "key projects", "notable projects", "open source"]
  };

  const detectedSections = [];
  const missingSections = [];

  for (const [secName, aliases] of Object.entries(keySections)) {
    const found = aliases.some(alias => {
      const reg = new RegExp('(?:^|\\n)\\s*(?:#+\\s*)?' + escapeRegex(alias) + '\\b', 'i');
      return reg.test(lower);
    });
    if (found) detectedSections.push(secName);
    else missingSections.push(secName);
  }

  const rawLines = resumeText.split('\n');
  const bulletLines = rawLines
    .map(l => l.trim())
    .filter(l => /^[•\-*–▪●◦·]/.test(l) || /^\d+\./.test(l));

  const totalBullets = bulletLines.length;

  let bulletsWithAction = 0;
  let bulletsWithMetrics = 0;

  const metricRegexes = [
    /\d+(?:\.\d+)?%/,
    /[$€£]\s?\d[\d,]*(?:\.\d+)?[kKmMbBtT]?/i,
    /\d+(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?|sec|minutes?|min|hours?|hr)/i,
    /(?:reduced?|increased?|improved?|decreased?|grew|boosted?|cut|saved?)\s+(?:by\s+)?\d+(?:\.\d+)?%?/i,
    /\d[\d,]*(?:\.\d+)?[kKmMbB]?\+?\s*(?:users?|requests?|customers?|clients?|transactions?|records?|entries|endpoints?|servers?|msgs?|messages?|qps|events?|req\/s|rps|ops|jobs)/i,
    /from\s+\d[\d,]*(?:\.\d+)?\s+to\s+\d[\d,]*(?:\.\d+)?/i,
    /\d+(?:\.\d+)?x\b/i,
    /(?:revenue|cost\s+savings?|ROI|profit|budget)\s*(?:of\s+)?\$?\d/i,
    /\d+(?:\.\d+)?\s*(?:hours?|days?|weeks?|months?)\s+(?:saved|reduced|eliminated|freed)/i,
    /\b\d{1,3}(?:,\d{3})+\b/
  ];

  for (const line of bulletLines) {
    const cleaned = line.replace(/^[•\-*–▪●◦·\s\d\.]+/, '').trim();
    const words = cleaned.match(/[A-Za-z]+/g) || [];
    const firstFive = words.slice(0, 5).map(w => w.toLowerCase());
    if (firstFive.some(w => ACTION_VERBS.has(w))) {
      bulletsWithAction++;
    }
    if (metricRegexes.some(r => r.test(cleaned))) {
      bulletsWithMetrics++;
    }
  }

  const wordCount = (resumeText.trim().match(/\S+/g) || []).length;
  let structureScore = 20; // Base score for having any content
  if (hasEmail) structureScore += 12;
  if (hasPhone) structureScore += 8;
  if (hasLinks) structureScore += 5;

  const nSec = detectedSections.length;
  if (nSec >= 5) structureScore += 25;
  else if (nSec === 4) structureScore += 20;
  else if (nSec === 3) structureScore += 15;
  else if (nSec === 2) structureScore += 10;
  else if (nSec === 1) structureScore += 5;

  if (totalBullets >= 8) structureScore += 20;
  else if (totalBullets >= 5) structureScore += 15;
  else if (totalBullets >= 3) structureScore += 10;
  else if (totalBullets >= 1) structureScore += 5;

  if (wordCount >= 300 && wordCount <= 1000) structureScore += 10;
  else if ((wordCount >= 200 && wordCount < 300) || (wordCount > 1000 && wordCount <= 1200)) structureScore += 5;

  structureScore = Math.min(structureScore, 100);

  const out = {
    structure_score: structureScore,
    has_email: hasEmail,
    has_phone: hasPhone,
    has_links: hasLinks,
    detected_sections: detectedSections,
    missing_sections: missingSections,
    total_bullets: totalBullets,
    bullets_with_action_verbs: bulletsWithAction,
    bullets_with_metrics: bulletsWithMetrics,
    word_count: (resumeText.trim().match(/\S+/g) || []).length
  };
  if (includeContact) {
    out.email = emailMatch ? emailMatch[0] : null;
    out.phone = phoneMatch ? phoneMatch[0].trim() : null;
  }
  return out;
}

function generateRecommendations(finalScore, keywordScore, skillScore, impactScore, matchedKeywords, missingKeywords, structureAudit, categorizedBreakdown, totalBullets) {
  const recommendations = [];

  if (finalScore >= 80) {
    recommendations.append ? null : recommendations.push(
      "🌟 **Excellent ATS readiness!** Your resume matches over 80% of key requirements and is primed to pass automated screenings. Fine-tune the few gaps below for a perfect score."
    );
  } else if (finalScore >= 65) {
    recommendations.push(
      "✅ **Strong foundation with room for optimization.** You're above the typical screening threshold, but incorporating the missing keywords below can push you into the top tier."
    );
  } else if (finalScore >= 50) {
    recommendations.push(
      "⚠️ **Moderate match — optimization needed.** Your resume covers some requirements but has significant gaps. Focus on the missing high-priority keywords and structural improvements."
    );
  } else {
    recommendations.push(
      "🚨 **High risk of ATS filtering.** Significant gaps in required technical keywords and/or resume structure. Prioritize the critical missing skills and structural fixes below."
    );
  }

  if (missingKeywords && missingKeywords.length) {
    const critical = missingKeywords.filter(m => m.importance === "Critical").map(m => m.keyword).slice(0, 5);
    const high = missingKeywords.filter(m => m.importance === "High").map(m => m.keyword).slice(0, 5);
    if (critical.length) {
      recommendations.push(
        `• **Critical missing terms:** Add these high-frequency keywords where you have genuine experience: **${critical.join(", ")}**.`
      );
    }
    if (high.length) {
      recommendations.push(
        `• **High-priority gaps:** Incorporate these terms naturally into your experience bullets: **${high.join(", ")}**.`
      );
    }
  }

  if (keywordScore < 50) {
    recommendations.push(
      "• **Mirror the job description language.** Use the exact terms and phrases from the posting in your summary, skills section, and experience bullets."
    );
  }

  for (const [domain, ddata] of Object.entries(categorizedBreakdown || {})) {
    const missing = ddata.missing || [];
    if (missing.length >= 3) {
      recommendations.push(
        `• **${domain} gap:** Consider adding: ${missing.slice(0, 4).join(", ")}.`
      );
    }
  }

  if (structureAudit && structureAudit.red_flags && structureAudit.red_flags.length) {
    for (const flag of structureAudit.red_flags.slice(0, 3)) {
      recommendations.push(`• **Formatting:** ${flag}`);
    }
  }

  if (totalBullets > 0) {
    const metricRatio = structureAudit.bullets_with_metrics / totalBullets;
    const verbRatio = structureAudit.bullets_with_action_verbs / totalBullets;
    if (metricRatio < 0.4) {
      recommendations.push(
        "• **Quantify your impact.** Add measurable results (%, $, user scale, latency reduction) to at least 40% of your experience bullets."
      );
    }
    if (verbRatio < 0.5) {
      recommendations.push(
        "• **Lead with action verbs.** Start each bullet with a strong past-tense verb like 'Architected', 'Optimized', 'Spearheaded', 'Reduced', or 'Delivered'."
      );
    }
  } else if (totalBullets === 0) {
    recommendations.push(
      "• **Use bullet points.** Break your experience into concise, bulleted accomplishment statements. ATS and recruiters scan for these."
    );
  }

  if (impactScore < 40) {
    recommendations.push(
      "• **Strengthen your STAR bullets.** Each bullet should follow: Action Verb + What you did + Measurable Result."
    );
  }

  return recommendations.slice(0, 10);
}

function detectBengaliText(text) {
  if (!text) return false;
  const bengaliChars = (text.match(/[\u0980-\u09FF]/g) || []).length;
  const totalLetters = (text.match(/[\p{L}]/gu) || []).length;
  return (bengaliChars >= 15) && (bengaliChars / Math.max(totalLetters, 1) > 0.25);
}

function detectKeywordStuffing(resumeText, matchedKeywords, structureAudit) {
  if (!matchedKeywords || matchedKeywords.length === 0) return false;

  const tokens = cleanAndTokenize(resumeText);
  const totalTokens = tokens.length;
  if (totalTokens === 0) return false;

  let wordCount = structureAudit.word_count || totalTokens;
  if (wordCount === 0) wordCount = totalTokens;

  let totalKwWords = 0;
  for (const m of matchedKeywords) {
    const kwWords = (m.keyword || "").trim().split(/\s+/).filter(Boolean).length || 1;
    totalKwWords += (m.resume_count || 1) * kwWords;
  }

  const tokenCounts = {};
  for (const t of tokens) {
    const tl = t.toLowerCase();
    tokenCounts[tl] = (tokenCounts[tl] || 0) + 1;
  }

  for (const m of matchedKeywords) {
    const kw = (m.keyword || "").toLowerCase();
    const kwTokenLen = kw.trim().split(/\s+/).filter(Boolean).length || 1;
    let cnt = m.resume_count || 0;
    if (cnt === 0) {
      cnt = tokenCounts[kw] || 0;
    } else {
      cnt = Math.max(cnt, tokenCounts[kw] || 0);
    }

    // 1. Same matched keyword repeated 6+ times in a short document (under 150 words)
    if (wordCount < 150 && cnt >= 6) return true;

    // 2. One keyword making up more than 20% of all tokens
    if (totalTokens > 0 && ((cnt * kwTokenLen) / totalTokens) > 0.20) return true;
  }

  // 3. Matched keywords making up more than 40% of total words
  const effectiveWords = Math.max(totalTokens, wordCount);
  if (effectiveWords > 0 && (totalKwWords / effectiveWords) > 0.40) {
    return true;
  }

  return false;
}

function analyzeATS(resumeText, jobDescription, includeContact = false) {
  if (!resumeText || !resumeText.trim()) throw new Error("Resume empty");
  if (!jobDescription || !jobDescription.trim()) throw new Error("JD empty");

  const resumeLower = resumeText.toLowerCase();
  const jdLower = jobDescription.toLowerCase();

  const jdKeywords = extractKeywordsWithFrequencies(jobDescription, 40);

  const matchedKeywords = [];
  const missingKeywords = [];

  for (const [kw, weight] of jdKeywords) {
    const formsToCheck = getAllSkillForms(kw);
    let resumeCount = 0;
    for (const form of formsToCheck) {
      try {
        const reg = new RegExp('\\b' + escapeRegex(form) + '\\b', 'g');
        const m = resumeLower.match(reg);
        if (m) resumeCount += m.length;
      } catch (e) {
        resumeCount += resumeLower.split(form).length - 1;
      }
    }

    if (resumeCount === 0) {
      for (const form of formsToCheck) {
        const fuzzy = fuzzySkillMatch(form, ALL_SKILLS, 1);
        if (fuzzy && fuzzy !== form) {
          try {
            const reg = new RegExp('\\b' + escapeRegex(fuzzy) + '\\b', 'g');
            const m = resumeLower.match(reg);
            if (m) resumeCount += m.length;
          } catch (e) {
            resumeCount += resumeLower.split(fuzzy).length - 1;
          }
        }
        if (resumeCount > 0) break;
      }
    }

    const kwCat = ALL_SKILLS[kw.toLowerCase()] || ALL_SKILLS[SKILL_ALIASES[kw.toLowerCase()] || ""] || "General Keyword";
    const realCount = countOccurrencesInText(kw, jdLower);

    if (resumeCount > 0) {
      matchedKeywords.push({
        keyword: kw,
        jd_weight: parseFloat(weight.toFixed(4)),
        resume_count: resumeCount,
        category: kwCat
      });
    } else {
      let importance = "Medium";
      if (realCount >= 3 || (kwCat !== "General Keyword" && realCount >= 2)) {
        importance = "Critical";
      } else if (realCount >= 2 || (kwCat !== "General Keyword" && weight >= 0.02)) {
        importance = "High";
      }

      missingKeywords.push({
        keyword: kw,
        jd_weight: parseFloat(weight.toFixed(4)),
        jd_count: realCount,
        importance: importance,
        category: kwCat
      });
    }
  }

  // Deduplicate matched keywords by coverage (prefer longest match)
  const matchedPhrases = matchedKeywords.filter(m => m.keyword.includes(' ')).map(m => m.keyword.toLowerCase());
  const dedupedMatched = [];
  for (const m of matchedKeywords) {
    const kwL = m.keyword.toLowerCase();
    let isSub = false;
    for (const p of matchedPhrases) {
      if (kwL !== p && p.split(/\s+/).includes(kwL)) {
        isSub = true;
        break;
      }
    }
    if (!isSub) dedupedMatched.push(m);
  }

  const finalMatched = dedupedMatched;

  const totalJdWeight = jdKeywords.reduce((acc, [, w]) => acc + w, 0) || 1.0;
  const matchedWeight = finalMatched.reduce((acc, m) => acc + m.jd_weight, 0);
  let keywordScore = parseFloat(((matchedWeight / totalJdWeight) * 100).toFixed(1));
  keywordScore = Math.min(keywordScore, 100.0);

  // Skill taxonomy
  const jdSkills = new Set();
  const resumeSkills = new Set();
  const categorizedBreakdown = {};

  for (const [skill, category] of Object.entries(ALL_SKILLS)) {
    try {
      const reg = new RegExp('\\b' + escapeRegex(skill) + '\\b');
      if (reg.test(jdLower)) {
        jdSkills.add(skill);
        if (!categorizedBreakdown[category]) {
          categorizedBreakdown[category] = { matched: [], missing: [] };
        }

        const forms = getAllSkillForms(skill);
        let found = Array.from(forms).some(f => {
          try {
            return new RegExp('\\b' + escapeRegex(f) + '\\b').test(resumeLower);
          } catch (e) {
            return resumeLower.includes(f);
          }
        });

        if (!found) {
          const rTokens = new Set(cleanAndTokenize(resumeText));
          found = Array.from(rTokens).some(t => levenshteinDistance(t, skill) <= 1);
        }

        if (found) {
          resumeSkills.add(skill);
          categorizedBreakdown[category].matched.push(skill);
        } else {
          categorizedBreakdown[category].missing.push(skill);
        }
      }
    } catch (e) {}
  }

  let skillScore = null;
  let skillMatchAvailable = false;
  if (!jdSkills.size) {
    skillScore = null;
    skillMatchAvailable = false;
  } else {
    skillScore = parseFloat(((resumeSkills.size / jdSkills.size) * 100).toFixed(1));
    skillScore = Math.min(skillScore, 100.0);
    skillMatchAvailable = true;
  }

  const structureAudit = auditResumeStructure(resumeText, includeContact);

  const totalB = structureAudit.total_bullets;
  let impactScore = 30.0;
  if (totalB > 0) {
    const verbRatio = structureAudit.bullets_with_action_verbs / totalB;
    const metricRatio = structureAudit.bullets_with_metrics / totalB;
    impactScore = parseFloat((((verbRatio * 0.5) + (metricRatio * 0.5)) * 100).toFixed(1));
  }
  impactScore = Math.min(impactScore, 100.0);

  const isBengali = detectBengaliText(resumeText) || detectBengaliText(jobDescription);
  const languageWarning = isBengali
    ? "This resume appears to be in Bengali. The skill taxonomy is English-only, so this score is not reliable for Bengali text."
    : null;

  const stuffingDetected = detectKeywordStuffing(resumeText, finalMatched, structureAudit);
  const stuffingWarning = stuffingDetected
    ? "Keyword repetition detected - this looks like stuffing. Add real experience bullets using these skills."
    : null;

  if (stuffingDetected) {
    keywordScore = Math.min(keywordScore, 30.0);
    if (skillScore !== null) {
      skillScore = Math.min(skillScore, 30.0);
    }
  }

  let finalScore = 0;
  if (skillScore !== null) {
    finalScore = parseFloat((
      (0.40 * keywordScore) +
      (0.30 * skillScore) +
      (0.20 * structureAudit.structure_score) +
      (0.10 * impactScore)
    ).toFixed(1));
  } else {
    const reweighted = (
      (0.40 * keywordScore) +
      (0.20 * structureAudit.structure_score) +
      (0.10 * impactScore)
    ) / 0.70;
    finalScore = parseFloat(reweighted.toFixed(1));
  }
  finalScore = Math.max(0.0, Math.min(finalScore, 100.0));

  let scoreTier = "Needs Optimization";
  if (finalScore >= 80) scoreTier = "Excellent Match";
  else if (finalScore >= 65) scoreTier = "Strong Match";
  else if (finalScore >= 50) scoreTier = "Moderate Match";

  const recommendations = generateRecommendations(
    finalScore,
    keywordScore,
    skillScore,
    impactScore,
    finalMatched,
    missingKeywords,
    structureAudit,
    categorizedBreakdown,
    totalB
  );

  if (stuffingWarning) {
    recommendations.unshift(`🚨 **${stuffingWarning}**`);
  }
  if (languageWarning) {
    recommendations.unshift(`⚠️ **Notice:** ${languageWarning}`);
  }

  return {
    final_score: finalScore,
    score_tier: scoreTier,
    is_bengali: isBengali,
    language_warning: languageWarning,
    stuffing_detected: stuffingDetected,
    stuffing_warning: stuffingWarning,
    sub_scores: {
      keyword_match: keywordScore,
      skill_match: skillScore,
      skill_match_available: skillMatchAvailable,
      structure_compliance: structureAudit.structure_score,
      measurable_impact: impactScore
    },
    matched_keywords: finalMatched,
    missing_keywords: missingKeywords,
    skill_breakdown: categorizedBreakdown,
    structure_audit: structureAudit,
    recommendations: recommendations
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    analyzeATS,
    cleanAndTokenize,
    extractKeywordsWithFrequencies,
    auditResumeStructure,
    levenshteinDistance,
    protectTechSymbols,
    restoreTechSymbols,
    normalizeSkill
  };
}
if (typeof window !== "undefined") {
  window.OpenATSEngine = {
    analyzeATS,
    cleanAndTokenize,
    extractKeywordsWithFrequencies,
    auditResumeStructure,
    levenshteinDistance,
    protectTechSymbols,
    restoreTechSymbols,
    normalizeSkill
  };
}
