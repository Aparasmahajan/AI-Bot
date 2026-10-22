// Assembles parts/*.html in order, injects the contents list and generated figures, writes out/MWB-POC.html.
// Also writes out/charts-check.html (the data-driven charts only) for the single pre-publish look.
import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { FIGS, dayStats } from './figs.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const TOC = [
  [1, 'Features'], [2, 'Applications'], [3, 'Description'], [4, 'Your laptop today'], [5, 'What carries over from AI-App'],
  [6, 'Measured on this laptop'], [7, 'Requirements'], [8, 'Architecture'], [9, 'Pipelines'], [10, 'Work or Timepass'],
  [11, 'Memory and model lifecycle'], [12, 'Profiles, effort and models'], [13, 'Hotkeys and indicator'], [14, 'Data model and storage'],
  [15, 'Privacy and security'], [16, 'Tech stack and setup'], [17, 'Plan'], [18, 'Risks'], [19, 'Decisions for you'],
  [20, 'Glossary'], [21, 'Sources and revisions'],
];
const toc = `<ol class="toc">${TOC.map(([n, t]) => `<li><a href="#s${n}"><span>${n}</span>${t}</a></li>`).join('')}</ol>`;

const partsDir = join(here, 'parts');
let html = readdirSync(partsDir).filter((f) => f.endsWith('.html')).sort().map((f) => readFileSync(join(partsDir, f), 'utf8')).join('\n');
html = html.replaceAll('{{toc}}', toc);
const used = new Set();
html = html.replace(/\{\{fig:(\w+)\}\}/g, (_, k) => {
  if (!FIGS[k]) throw new Error(`unknown figure ${k}`);
  used.add(k);
  return FIGS[k]();
});
const left = html.match(/\{\{[^}]+\}\}/g);
if (left) throw new Error(`unreplaced placeholders: ${left.join(', ')}`);
const unused = Object.keys(FIGS).filter((k) => !used.has(k));

const out = join(here, 'out');
mkdirSync(out, { recursive: true });
writeFileSync(join(out, 'MWB-POC.html'), html, 'utf8');

// charts-only proof sheet, same stylesheet
const head = readFileSync(join(partsDir, '00-head.html'), 'utf8');
const charts = (process.env.CHECK || 'ram,lat,mem,day,plan,dict').split(',');
const sheet = `${head}<div style="padding:16px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;background:var(--sheet)">${charts
  .map((k) => `<div class="fig-frame">${FIGS[k]()}</div>`).join('')}</div>`;
writeFileSync(join(out, 'charts-check.html'), sheet, 'utf8');

console.log(`built ${(html.length / 1024).toFixed(1)} KB, figures used: ${used.size}, unused: ${unused.join(', ') || 'none'}`);
for (const route of ['api', 'local']) {
  const s = dayStats(route);
  console.log(`modelled day, ${route}: avg ${s.avg.toFixed(3)} GB, above Wispr ${s.above} of ${s.total} min, peak ${s.peak} GB`);
}
