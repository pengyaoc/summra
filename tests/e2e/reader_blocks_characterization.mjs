// Reader block characterization: renders every unit in
// tests/shared/fixtures/reader_blocks/plainly_units.json through Plainly's live
// window.summraApp.continuousReaderBlock(), once with marked loaded and once
// with window.marked deleted (the fallback regexes), and compares the
// {tag, className, content} results to plainly_golden.json. Guards phase 3
// Task 6 (shared block renderer): Plainly's reader markup must not change.
//
// Run: MODE=record BASE_URL=http://localhost:5002 node reader_blocks_characterization.mjs
//      MODE=compare BASE_URL=http://localhost:5002 node reader_blocks_characterization.mjs
// MODE=compare exits 1 on any difference.

import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const MODE = process.env.MODE || 'compare';
const SLUG = process.env.SLUG || 'pride-and-prejudice';
const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'shared', 'fixtures', 'reader_blocks');
const UNITS = JSON.parse(fs.readFileSync(path.join(FIXTURES, 'plainly_units.json'), 'utf8'));
const GOLDEN = path.join(FIXTURES, 'plainly_golden.json');

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext();
await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
const page = await ctx.newPage();
await page.goto(`${BASE}/books/${SLUG}/read`, { waitUntil: 'networkidle' });
await page.waitForFunction(() => window.summraApp && typeof window.marked?.parseInline === 'function');

const render = (units) => units.map((u) => window.summraApp.continuousReaderBlock(u));
const result = { marked: await page.evaluate(render, UNITS) };
const hasMarked = await page.evaluate(() => { delete window.marked; return typeof marked !== 'undefined'; });
if (hasMarked) { console.error('FAIL: could not remove marked'); process.exit(1); }
result.fallback = await page.evaluate(render, UNITS);
await browser.close();

if (MODE === 'record') {
  fs.writeFileSync(GOLDEN, JSON.stringify(result, null, 1) + '\n');
  console.log(`Recorded ${UNITS.length} units x 2 to ${GOLDEN}`);
  process.exit(0);
}

const golden = JSON.parse(fs.readFileSync(GOLDEN, 'utf8'));
let diffs = 0;
for (const half of ['marked', 'fallback']) {
  UNITS.forEach((unit, i) => {
    const want = JSON.stringify(golden[half][i]);
    const got = JSON.stringify(result[half][i]);
    if (want !== got) {
      diffs += 1;
      console.error(`DIFF ${half}[${i}] ${JSON.stringify(unit.slice(0, 60))}\n  want ${want}\n  got  ${got}`);
    }
  });
}
if (golden.marked.length !== UNITS.length || golden.fallback.length !== UNITS.length) {
  diffs += 1;
  console.error('DIFF golden length does not match the units fixture');
}
console.log(diffs ? `FAIL: ${diffs} differences` : `PASS: ${UNITS.length} units x 2 identical`);
process.exit(diffs ? 1 : 0);
