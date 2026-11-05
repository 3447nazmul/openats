#!/usr/bin/env node
/**
 * Parity Check Script for OpenATS
 * Asserts exact score and sub-score agreement between Python engine and JS engine.
 * Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { analyzeATS } = require('./parity_engine.js');

const rootDir = path.resolve(__dirname, '..');
const resumePath = path.join(rootDir, 'sample_data', 'sample_resume.txt');
const jdPath = path.join(rootDir, 'sample_data', 'sample_job_desc.txt');

if (!fs.existsSync(resumePath) || !fs.existsSync(jdPath)) {
  console.error("Error: sample files not found at:", resumePath, jdPath);
  process.exit(1);
}

const resume = fs.readFileSync(resumePath, 'utf8');
const jd = fs.readFileSync(jdPath, 'utf8');

// 1. Calculate scores via JS engine
const jsRes = analyzeATS(resume, jd);

// 2. Calculate scores via Python engine
const pyExec = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const safeRootDir = rootDir.replace(/\\/g, '/');
const safeResume = resumePath.replace(/\\/g, '/');
const safeJd = jdPath.replace(/\\/g, '/');
const pyCmd = `"${pyExec}" -c "import sys, json; sys.path.insert(0, '${safeRootDir}'); from openats.engine import analyze_ats_match; r = open('${safeResume}', encoding='utf-8').read(); j = open('${safeJd}', encoding='utf-8').read(); res = analyze_ats_match(r, j); print(json.dumps({'final_score': res['final_score'], 'sub_scores': res['sub_scores']}))"`;

let pyRes;
try {
  const pyOut = execSync(pyCmd, { cwd: rootDir, encoding: 'utf8' }).trim();
  pyRes = JSON.parse(pyOut);
} catch (e) {
  console.error("Failed to run Python engine:", e.message);
  process.exit(1);
}

console.log("=================================================================");
console.log(" 🧪 OpenATS Cross-Platform Score Parity Verification");
console.log("=================================================================");
console.log(`Input: sample_data/sample_resume.txt vs sample_job_desc.txt\n`);

const metrics = [
  ['Overall Final Score (100%)', pyRes.final_score, jsRes.final_score],
  ['Keyword Overlap (40%)', pyRes.sub_scores.keyword_match, jsRes.sub_scores.keyword_match],
  ['Skills Coverage (30%)', pyRes.sub_scores.skill_match, jsRes.sub_scores.skill_match],
  ['Structure Compliance (20%)', pyRes.sub_scores.structure_compliance, jsRes.sub_scores.structure_compliance],
  ['STAR Impact Metrics (10%)', pyRes.sub_scores.measurable_impact, jsRes.sub_scores.measurable_impact]
];

let allPassed = true;

console.log(
  'Metric'.padEnd(30) +
  ' | ' + 'Python'.padStart(8) +
  ' | ' + 'Browser JS'.padStart(10) +
  ' | ' + 'Diff'.padStart(6) +
  ' | Status'
);
console.log('-'.repeat(68));

for (const [name, pyVal, jsVal] of metrics) {
  const diff = Math.abs(Number(pyVal) - Number(jsVal));
  const passed = diff <= 0.1;
  if (!passed) allPassed = false;
  const status = passed ? '✅ PASS' : '❌ FAIL';
  console.log(
    name.padEnd(30) +
    ' | ' + String(pyVal).padStart(8) +
    ' | ' + String(jsVal).padStart(10) +
    ' | ' + diff.toFixed(1).padStart(6) +
    ' | ' + status
  );
}

console.log("=================================================================");
if (allPassed) {
  console.log(" ✅ PARITY VERIFIED: 100% Score Parity Achieved between Python & JS!");
  console.log("=================================================================\n");
  process.exit(0);
} else {
  console.error(" ❌ PARITY FAILED: Discrepancy exceeds allowed tolerance!");
  console.log("=================================================================\n");
  process.exit(1);
}
