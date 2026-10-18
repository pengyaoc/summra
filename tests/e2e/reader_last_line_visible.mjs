// The reader's last line must sit above the progress footer, not under it.
//
// Bug (iPhone, 2026-10-18, Wealth of Nations "Of Public Debts"): pages were
// cut before the Figtree web font loaded. When it loaded, the text re-wrapped
// into more lines than each page was cut for, and a page's last line slid
// under the footer. The font request is held back here so it always lands
// after the reader would otherwise have paginated.
//
// Run: node reader_last_line_visible.mjs   (Flask on :5001)

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const PAGES = 50;
const browser = await chromium.launch({ headless: true });
for (const font of ['figtree', 'georgia']) {
  const ctx = await browser.newContext({ viewport: { width: 402, height: 698 }, isMobile: true, hasTouch: true });
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
  await ctx.route(/figtree.*\.woff2/, async (r) => { await new Promise((res) => setTimeout(res, 1500)); r.continue(); });
  await ctx.addInitScript((f) => { localStorage.setItem('reading_font', f); localStorage.setItem('reading_fontSize', '18'); }, font);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/books/an-inquiry-into-the-nature-and-causes-of-the-wealth-of-nations/read?chapter=224&mode=plain`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.pagination-page-container [data-reader-anchor]');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
  const bad = [];
  for (let i = 0; i < PAGES; i++) {
    const s = await page.evaluate(() => {
      const c = document.querySelector('.pagination-page-container');
      const footerTop = document.querySelector('.continuous-reader-footer').getBoundingClientRect().top;
      return { overflow: c.scrollHeight - c.clientHeight, bottom: Math.round(c.getBoundingClientRect().bottom), footerTop: Math.round(footerTop) };
    });
    if (s.overflow > 0 || s.bottom > s.footerTop) bad.push({ page: i, ...s });
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(100);
  }
  expect(`${font}: every page's text fits above the footer (${PAGES} pages)`, bad.length === 0, JSON.stringify(bad.slice(0, 3)));
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
