const fs = require('fs');
const path = require('path');

const dir = '../public/algos';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.toml')).sort();
let total = 0, errors = 0;
const errs = [];

for (const f of files) {
  total++;
  const text = fs.readFileSync(path.join(dir, f), 'utf8');
  const steps = text.split('[[algorithm.steps]]').slice(1);
  if (steps.length < 4 || steps.length > 6) {
    errs.push(`${f}: step count = ${steps.length} (need 4-6)`); errors++;
  }
  let prev = null;
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    const cm = s.match(/code\s*=\s*"""([\s\S]*?)"""/);
    if (!cm) { errs.push(`${f}: step ${i} missing code field`); errors++; continue; }
    const code = cm[1];
    if (prev !== null) {
      const prevLines = prev.split('\n');
      const curLines = code.split('\n');
      // find longest common prefix
      let pi = 0;
      while (pi < prevLines.length && pi < curLines.length && prevLines[pi] === curLines[pi]) pi++;
      // find longest common suffix (after the prefix)
      let ps = 0, cs = 0;
      while (ps < prevLines.length - pi && cs < curLines.length - pi &&
             prevLines[prevLines.length - 1 - ps] === curLines[curLines.length - 1 - cs]) {
        ps++; cs++;
      }
      const prevMid = prevLines.slice(pi, prevLines.length - ps);
      const curMid = curLines.slice(pi, curLines.length - cs);
      if (curMid.length < prevMid.length) {
        errs.push(`${f}: step ${i} code shrunk (prev had ${prevMid.length} middle lines, cur has ${curMid.length})`); errors++;
      }
    }
    prev = code;
  }
  // check visualizationType enum
  const vts = [...text.matchAll(/visualizationType\s*=\s*"([^"]+)"/g)].map(m => m[1]);
  const valid = ['intro','code-only','map-create','array-iteration','map-add','map-found','result'];
  for (const vt of vts) if (!valid.includes(vt)) {
    errs.push(`${f}: bad visualizationType "${vt}"`); errors++;
  }
  // check uppercase booleans in TOML
  if (/\bvisualizationData\s*=[^{]*\{\s*[^{}]*\b(True|False)\b/.test(text)) {
    errs.push(`${f}: found True/False in visualizationData`); errors++;
  }
  // check visualizationData key quoting
  if (/visualizationData\s*=\s*\{\s*"/.test(text)) {
    errs.push(`${f}: visualizationData has quoted keys`); errors++;
  }
}

console.log(`\n=== Audit Results ===`);
console.log(`Total files: ${total}`);
console.log(`Errors: ${errors}`);
if (errs.length) {
  console.log(`\nIssues:`);
  for (const e of errs) console.log(`  ❌ ${e}`);
  process.exit(1);
} else {
  console.log(`\n✅ All ${total} TOML files pass audit`);
}
