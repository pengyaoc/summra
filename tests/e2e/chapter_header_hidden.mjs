// Regression test: site .header must be display:none immediately after
// navigating into a chapter page, with no reliance on :has() re-evaluation
// timing.
//
// Why this matters: on iOS Safari/WebKit, body:has(.chapter-detail-section:
// not(.hidden)) .header { display: none } can defer to the next style recalc,
// so for one frame the site nav covers the top of the chapter text. We
// replace the :has() rule with a deterministic body.on-chapter-page class
// toggled from JS. This test asserts the toggle happened.
//
// We can't reproduce the iOS race on desktop Chromium (its :has() is fast),
// so the test guards two things:
//   1. body.on-chapter-page is set after showChapterDetail runs.
//   2. .header computed display is 'none' on the chapter page.
//
// Usage: BASE_URL=http://localhost:5001 node chapter_header_hidden.mjs

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const BOOK_URL = `${BASE}/books/the-adventures-of-sherlock-holmes`;
const CHAPTER_URL = `${BASE}/books/the-adventures-of-sherlock-holmes/chapters/1`;

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

let failed = false;
const checks = [];

function check(name, cond, detail = '') {
  checks.push({ name, cond, detail });
  if (!cond) failed = true;
}

try {
  // 1. Direct nav into chapter URL — server renders chapter section visible.
  const resp = await page.goto(CHAPTER_URL, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  check('chapter URL loads 200', !!resp && resp.ok(),
        resp ? `status ${resp.status()}` : 'no response');

  // Wait for the SPA boot to settle (showChapterDetail runs from the router).
  await page.waitForFunction(() => {
    const s = document.getElementById('chapter-detail-section');
    return s && !s.classList.contains('hidden');
  }, { timeout: 5000 });

  // Give the SPA's class-toggle code one tick to run.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => r())));

  const onClass = await page.evaluate(() => document.body.classList.contains('on-chapter-page'));
  check('body has .on-chapter-page after direct chapter URL nav', onClass);

  const headerDisplay = await page.evaluate(() => {
    const h = document.querySelector('.header');
    return h ? window.getComputedStyle(h).display : null;
  });
  check('.header computed display is "none" on chapter page',
        headerDisplay === 'none',
        `actual: ${JSON.stringify(headerDisplay)}`);

  // 2. pushState nav: book → chapter. This is the path the user described
  //    ("click in from book page"). Header must hide deterministically.
  await page.goto(BOOK_URL, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.waitForFunction(() => {
    const s = document.getElementById('summary-section');
    const ready = s && !s.classList.contains('hidden') &&
                  window.summraApp && window.summraApp.currentBook;
    return ready;
  }, { timeout: 10_000 });

  const headerOnBook = await page.evaluate(() =>
    window.getComputedStyle(document.querySelector('.header')).display);
  check('.header is visible on book page (pre-nav baseline)',
        headerOnBook !== 'none',
        `actual: ${JSON.stringify(headerOnBook)}`);

  // Trigger pushState chapter navigation the way the app does it.
  await page.evaluate(async () => {
    if (window.summraApp && typeof window.summraApp.showChapterDetailPage === 'function') {
      await window.summraApp.showChapterDetailPage(1);
      // Let any awaited fetch in showChapterDetail resolve.
      await new Promise((r) => setTimeout(r, 800));
    }
  });

  const onClassAfterPush = await page.evaluate(() =>
    document.body.classList.contains('on-chapter-page'));
  check('body has .on-chapter-page after pushState nav from book page', onClassAfterPush);

  const headerAfterPush = await page.evaluate(() =>
    window.getComputedStyle(document.querySelector('.header')).display);
  check('.header is display:none after pushState nav from book page',
        headerAfterPush === 'none',
        `actual: ${JSON.stringify(headerAfterPush)}`);

} finally {
  await browser.close();
}

for (const c of checks) {
  const tag = c.cond ? 'PASS' : 'FAIL';
  const suffix = c.detail ? ` — ${c.detail}` : '';
  console.log(`[${tag}] ${c.name}${suffix}`);
}
process.exit(failed ? 1 : 0);
