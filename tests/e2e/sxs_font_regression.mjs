// E2E regression: switching font in side-by-side view must NOT collapse
// the chapter into 2-3 pages. The chapter should keep ~the same number of
// pages, and the underlying page content must still contain side-by-side rows.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5004';
const CHAPTER_URL = `${BASE}/books/a-christmas-carol-in-prose/chapters/1`;

const assert = (cond, msg) => {
  if (!cond) {
    console.error('FAIL:', msg);
    process.exit(1);
  } else {
    console.log('PASS:', msg);
  }
};

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
const page = await ctx.newPage();

page.on('pageerror', (err) => { console.error('PAGE ERROR:', err.message); process.exit(1); });

await page.goto(CHAPTER_URL, { waitUntil: 'networkidle' });
await page.waitForSelector('#chapter-detail-section');
await page.waitForFunction(
  () => document.getElementById('chapter-detail-section')?.style.visibility !== 'hidden'
);

await page.evaluate(() => {
  document.querySelectorAll('.unified-view-btn[data-mode="side-by-side"]').forEach((b) => b.classList.remove('hidden'));
});
await page.click('.unified-view-btn[data-mode="side-by-side"]');
await page.waitForTimeout(800);

// Probe the pagination state directly — the pages array is the source of truth
const inspect = () => page.evaluate(() => {
  const p = window.summraApp?.pagination;
  if (!p) return null;
  const sxsPages = p.pages.filter(html => html && html.includes('side-by-side-row')).length;
  const sampleSxs = p.pages.find(html => html?.includes('side-by-side-row')) ?? null;
  const rowsInSample = sampleSxs ? (sampleSxs.match(/class="side-by-side-row"/g) ?? []).length : 0;
  return {
    totalPages: p.totalPages,
    sxsPages,
    rowsInFirstSxsPage: rowsInSample,
    sampleLen: sampleSxs?.length ?? 0,
  };
});

const before = await inspect();
console.log('before:', JSON.stringify(before));
assert(before.totalPages >= 10, `side-by-side has many pages before font switch (got ${before.totalPages})`);
assert(before.sxsPages >= 5, `chapter has multiple side-by-side text pages (got ${before.sxsPages})`);
assert(before.rowsInFirstSxsPage >= 1, `text page has at least one row before font switch`);

// === ACTION UNDER TEST ===
await page.click('#sticky-settings-btn');
await page.waitForTimeout(200);
const currentFont = await page.evaluate(() => document.getElementById('chapter-detail-section')?.getAttribute('data-font'));
const targetFont = currentFont === 'opensans' ? 'georgia' : 'opensans';
console.log(`switching font ${currentFont} -> ${targetFont}`);
await page.click(`.font-choice[data-font="${targetFont}"]`);
await page.waitForTimeout(1500);

const after = await inspect();
console.log('after:', JSON.stringify(after));

// Bug signature: pages collapse from 41 -> 3, sxsPages drops to 1 with a single mega-row
assert(
  after.totalPages >= before.totalPages - 5,
  `font switch must not collapse pagination (before=${before.totalPages}, after=${after.totalPages})`
);
assert(
  after.sxsPages >= before.sxsPages - 3,
  `font switch must preserve text-page count (before=${before.sxsPages}, after=${after.sxsPages})`
);
assert(
  after.rowsInFirstSxsPage >= 1,
  `text page still has rows after font switch (got ${after.rowsInFirstSxsPage})`
);

await browser.close();
console.log('\nAll assertions passed.');
process.exit(0);
