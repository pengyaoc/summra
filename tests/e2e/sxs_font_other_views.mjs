// Confirm font switching in "original" and "modern" view modes still works
// (not just side-by-side). Verifies pagination doesn't collapse.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5004';
const CHAPTER_URL = `${BASE}/books/a-christmas-carol-in-prose/chapters/1`;

const assert = (cond, msg) => {
  if (!cond) { console.error('FAIL:', msg); process.exit(1); }
  else console.log('PASS:', msg);
};

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
const page = await ctx.newPage();

page.on('pageerror', (err) => { console.error('PAGE ERROR:', err.message); process.exit(1); });

await page.goto(CHAPTER_URL, { waitUntil: 'networkidle' });
await page.waitForSelector('#chapter-detail-section');
await page.waitForFunction(() => document.getElementById('chapter-detail-section')?.style.visibility !== 'hidden');

const get = () => page.evaluate(() => window.summraApp?.pagination?.totalPages ?? 0);

// === original view ===
await page.click('.unified-view-btn[data-mode="original"]');
await page.waitForTimeout(700);
const origBefore = await get();
assert(origBefore >= 5, `original view paginates (got ${origBefore})`);

await page.click('#sticky-settings-btn');
await page.waitForTimeout(150);
let cur = await page.evaluate(() => document.getElementById('chapter-detail-section')?.getAttribute('data-font'));
let next = cur === 'opensans' ? 'georgia' : 'opensans';
await page.click(`.font-choice[data-font="${next}"]`);
await page.waitForTimeout(1200);
const origAfter = await get();
console.log(`original: ${origBefore} -> ${origAfter}`);
assert(origAfter >= origBefore - 5, `original view font switch preserves pagination (${origBefore} -> ${origAfter})`);

// Close settings panel before next interaction
await page.click('#reading-settings-close');
await page.waitForTimeout(150);

// === modern view ===
await page.click('.unified-view-btn[data-mode="modern"]');
await page.waitForTimeout(700);
const modBefore = await get();
assert(modBefore >= 5, `modern view paginates (got ${modBefore})`);

await page.click('#sticky-settings-btn');
await page.waitForTimeout(150);
cur = await page.evaluate(() => document.getElementById('chapter-detail-section')?.getAttribute('data-font'));
next = cur === 'opensans' ? 'georgia' : 'opensans';
await page.click(`.font-choice[data-font="${next}"]`);
await page.waitForTimeout(1200);
const modAfter = await get();
console.log(`modern: ${modBefore} -> ${modAfter}`);
assert(modAfter >= modBefore - 5, `modern view font switch preserves pagination (${modBefore} -> ${modAfter})`);

await browser.close();
console.log('\nAll other-view font switches OK.');
process.exit(0);
