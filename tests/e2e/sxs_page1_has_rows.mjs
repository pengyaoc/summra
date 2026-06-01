// Regression test: side-by-side view must show actual content rows on page 1,
// not just the "Original | Plain English" headers banner.
//
// Bug: pagination treated `.side-by-side-headers` as its own atomic block.
// Headers fit on page 1, the first `.side-by-side-row` did not — so page 1
// ended up as just the headers banner with a vast empty area. Reproduces
// 12/12 at iPad-landscape (1194×834) on pushState nav from the book page.
//
// Fix: headers are pulled out of the paginated blocks and prepended to
// every page's HTML at calc time. Every page now has the column labels
// AND content rows.
//
// Usage: BASE_URL=http://localhost:5001 node sxs_page1_has_rows.mjs

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const BOOK_URL = `${BASE}/books/the-adventures-of-sherlock-holmes`;
const TRIALS = 6;

const browser = await chromium.launch({ headless: true });
// iPad-class width so side-by-side mode is allowed (>= 1024px).
const ctx = await browser.newContext({ viewport: { width: 1194, height: 834 } });
const page = await ctx.newPage();

// Pre-seed the saved preference so the chapter lands in side-by-side directly.
await page.addInitScript(() => {
  localStorage.setItem('reading_chapterViewMode', 'side-by-side');
});

let failed = false;
const results = [];

for (let trial = 1; trial <= TRIALS; trial++) {
  // Start on the book page each trial so we exercise the pushState path.
  await page.goto(BOOK_URL, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.waitForFunction(() => {
    const s = document.getElementById('summary-section');
    return s && !s.classList.contains('hidden') &&
           window.summraApp && window.summraApp.currentBook;
  }, { timeout: 10_000 });

  await page.evaluate(() => window.summraApp.showChapterDetailPage(1));

  // Wait for pagination to settle.
  await page.waitForFunction(() => {
    const pc = document.querySelector('.pagination-page-container');
    return pc && pc.innerHTML.length > 0 && window.summraApp.pagination?.totalPages > 0;
  }, { timeout: 10_000 });
  await page.waitForTimeout(300);

  const state = await page.evaluate(() => {
    const pc = document.querySelector('.pagination-page-container');
    const sxs = document.getElementById('chapter-side-by-side');
    return {
      activeMode: document.querySelector('.unified-view-btn.active')?.dataset.mode,
      sxsHidden: sxs?.classList.contains('hidden'),
      currentPage: window.summraApp.pagination?.currentPage,
      totalPages: window.summraApp.pagination?.totalPages,
      pageRowCount: pc?.querySelectorAll('.side-by-side-row').length ?? 0,
      pageHasHeaders: !!pc?.querySelector('.side-by-side-headers'),
    };
  });

  const ok = state.activeMode === 'side-by-side' &&
             state.sxsHidden === false &&
             state.currentPage === 0 &&
             state.pageRowCount >= 1 &&
             state.pageHasHeaders === true;
  if (!ok) failed = true;
  results.push({ trial, ok, state });
}

await browser.close();

for (const r of results) {
  const tag = r.ok ? 'PASS' : 'FAIL';
  console.log(`[${tag}] trial ${r.trial} — ${JSON.stringify(r.state)}`);
}
process.exit(failed ? 1 : 0);
