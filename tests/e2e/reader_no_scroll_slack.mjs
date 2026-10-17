// The continuous reader's document must not scroll: the toolbar and footer
// are fixed, so any scroll slides the page's first lines under the toolbar.
//
// Bug this guards against (iPhone Safari, 2026-10-17): the reader section used
// `min-height: 100vh` and the site's `.main-content` added 40px of bottom
// padding below it. The document was taller than the viewport, so a swipe (or
// iOS resting a few px into the slack) hid the top lines under the toolbar.
// `100vh` on iOS is also the LARGE viewport (toolbar collapsed), taller than
// what is visible; the earlier chapter-page fix used `100svh` for that.
//
// Run: node reader_no_scroll_slack.mjs   (Flask on :5001)

import { chromium, devices } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const browser = await chromium.launch({ headless: true });
for (const [label, options] of [['iPhone 13', devices['iPhone 13']], ['desktop', { viewport: { width: 1280, height: 900 } }]]) {
  for (const mode of ['plain', 'side_by_side']) {
    if (mode === 'side_by_side' && label !== 'desktop') continue; // side by side needs >= 1024px
    const ctx = await browser.newContext(options);
    await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
    const page = await ctx.newPage();
    await page.goto(`${BASE}/books/the-iliad/read?mode=${mode}`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
    await page.waitForTimeout(500);
    const s = await page.evaluate(async () => {
      const slack = document.documentElement.scrollHeight - innerHeight;
      window.scrollTo(0, 200); // a swipe or iOS settling into slack
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      const chromeBottom = document.getElementById('continuous-reader-chrome').getBoundingClientRect().bottom;
      const first = document.querySelector('.pagination-page-container [data-reader-anchor], .pagination-page-container .reader-chapter-heading');
      return { slack, scrollY, chromeBottom: Math.round(chromeBottom), firstTop: Math.round(first.getBoundingClientRect().top) };
    });
    expect(`${label} ${mode}: no scroll slack below the reader`, s.slack <= 0, JSON.stringify(s));
    expect(`${label} ${mode}: a scroll attempt leaves the page in place`, s.scrollY === 0, JSON.stringify(s));
    expect(`${label} ${mode}: first line starts below the toolbar`, s.firstTop >= s.chromeBottom, JSON.stringify(s));
    await ctx.close();
  }
}
// The fix is scoped to the reader: the summary page (also a reading page)
// still scrolls and keeps the site's bottom padding.
{
  const ctx = await browser.newContext(devices['iPhone 13']);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/books/the-iliad/summary`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  const s = await page.evaluate(() => ({ reader: document.body.classList.contains('on-reader-page'),
    pad: getComputedStyle(document.querySelector('.main-content')).paddingBottom }));
  expect('summary page keeps its bottom padding', !s.reader && s.pad === '40px', JSON.stringify(s));
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
