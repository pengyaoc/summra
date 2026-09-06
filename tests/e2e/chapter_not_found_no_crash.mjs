// Regression test: showChapterDetail must not crash when a chapter fetch
// legitimately returns nothing (e.g. a 404/missing chapter).
//
// Bug: `chapterFulltext` was declared with `const` inside the
// `if (!chapter || !chapter.summary)` block, then referenced again at the
// `if (!chapter)` guard right after that block closes — a block-scoping
// bug that throws `ReferenceError: chapterFulltext is not defined` on that
// path instead of showing the "Chapter not found" message.
//
// Usage: BASE_URL=http://localhost:5001 node chapter_not_found_no_crash.mjs

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const BOOK_SLUG = 'a-christmas-carol-in-prose';
const BOOK_URL = `${BASE}/books/${BOOK_SLUG}`;
const MISSING_CHAPTER_NUM = 9999; // not already cached in this.chapters

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

const pageErrors = [];
page.on('pageerror', (err) => pageErrors.push(String(err)));

let failed = false;
const checks = [];
function check(name, cond, detail = '') {
  checks.push({ name, cond, detail });
  if (!cond) failed = true;
}

try {
  // Force the chapter-detail fetch to report "not found" for this chapter.
  await page.route(`**/api/books/*/chapters/${MISSING_CHAPTER_NUM}`, (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, error: 'Chapter not found' }),
    });
  });

  await page.goto(BOOK_URL, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.waitForFunction(() => {
    return window.summraApp && window.summraApp.currentBook;
  }, { timeout: 10_000 });

  await page.evaluate(async (chapterNum) => {
    await window.summraApp.showChapterDetailPage(chapterNum);
  }, MISSING_CHAPTER_NUM);

  // Let any awaited fetch/catch in showChapterDetail resolve.
  await page.waitForTimeout(500);

  const crashed = pageErrors.some((e) => /chapterFulltext/.test(e));
  check('no ReferenceError referencing chapterFulltext', !crashed,
        crashed ? pageErrors.join(' | ') : '');
  check('no uncaught page errors at all', pageErrors.length === 0,
        pageErrors.join(' | '));

  const fulltextHtml = await page.evaluate(() =>
    document.getElementById('chapter-fulltext')?.innerHTML || '');
  check('fulltext panel shows "Chapter not found"',
        fulltextHtml.includes('Chapter not found'),
        `actual: ${fulltextHtml.slice(0, 200)}`);
} finally {
  await browser.close();
}

for (const c of checks) {
  const tag = c.cond ? 'PASS' : 'FAIL';
  const suffix = c.detail ? ` — ${c.detail}` : '';
  console.log(`[${tag}] ${c.name}${suffix}`);
}
process.exit(failed ? 1 : 0);
