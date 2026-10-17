// Web (mouse) page-turn controls in the continuous reader.
//
// Mouse is first class on web: the page-turn controls are full-height click
// strips in the margins beside the text, visible at rest (no auto-hide) and
// never over the text, even in a narrow window. The scroll wheel keeps
// turning pages, and a sideways trackpad swipe, Space/Shift+Space and
// PageDown/PageUp turn them too.
//
// Run: node reader_nav_mouse.mjs   (Flask on :5001)

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const position = (page) => page.evaluate(() => ({
  segment: window.summraApp.continuousReader.currentSegmentId,
  page: window.summraApp.pagination.currentPage,
}));
// Turns one page with `act` and returns how far the page index moved
// (same segment) — 1 means exactly one page forward.
const moved = async (page, act) => {
  const before = await position(page);
  await act();
  await page.waitForTimeout(700);
  const after = await position(page);
  return after.segment === before.segment ? after.page - before.page : NaN;
};

const browser = await chromium.launch({ headless: true });
for (const width of [1440, 700]) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 } });
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
  const page = await ctx.newPage();
  await page.goto(`${BASE}/books/the-iliad/read?mode=plain`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
  await page.waitForTimeout(1500); // past any auto-hide timer

  const m = await page.evaluate(() => {
    const box = (el) => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, height: r.height, width: r.width }; };
    const text = document.querySelector('.pagination-page-container');
    const prev = document.querySelector('.pagination-nav-prev');
    const next = document.querySelector('.pagination-nav-next');
    return { text: box(text), prev: box(prev), next: box(next),
      nextOpacity: Number(getComputedStyle(next).opacity),
      overscrollX: getComputedStyle(document.documentElement).overscrollBehaviorX };
  });
  const tag = `${width}px`;
  expect(`${tag}: next strip visible at rest`, m.nextOpacity >= 0.25, `opacity ${m.nextOpacity}`);
  expect(`${tag}: strips sit beside the text, not over it`,
    m.prev.right <= m.text.left + 1 && m.next.left >= m.text.right - 1, JSON.stringify(m));
  expect(`${tag}: strips are full height`,
    m.next.height >= 0.8 * m.text.height && m.prev.height >= 0.8 * m.text.height, `${m.next.height} vs ${m.text.height}`);
  expect(`${tag}: strips are at least 44px wide`, m.next.width >= 44 && m.prev.width >= 44, `${m.prev.width}/${m.next.width}`);
  expect(`${tag}: strips stay inside the window`, m.prev.left >= 0 && m.next.right <= width, JSON.stringify(m));
  expect(`${tag}: sideways overscroll can't trigger browser back`, m.overscrollX === 'none', m.overscrollX);

  const click = (b) => page.mouse.click(b.left + b.width / 2, b.top + Math.min(40, b.height / 4));
  expect(`${tag}: clicking the right strip turns one page`, await moved(page, () => click(m.next)) === 1);
  expect(`${tag}: clicking the left strip goes back one page`, await moved(page, () => click(m.prev)) === -1);
  expect(`${tag}: wheel down turns one page`, await moved(page, () => page.mouse.wheel(0, 120)) === 1);
  expect(`${tag}: wheel up goes back one page`, await moved(page, () => page.mouse.wheel(0, -120)) === -1);
  expect(`${tag}: trackpad swipe left turns one page`, await moved(page, () => page.mouse.wheel(120, 0)) === 1);
  expect(`${tag}: trackpad swipe right goes back one page`, await moved(page, () => page.mouse.wheel(-120, 0)) === -1);
  expect(`${tag}: a trackpad swipe with momentum turns only one page`, await moved(page, async () => {
    for (let i = 0; i < 12; i += 1) { await page.mouse.wheel(40, 2); await page.waitForTimeout(16); }
  }) === 1);
  expect(`${tag}: Space turns one page`, await moved(page, () => page.keyboard.press('Space')) === 1);
  expect(`${tag}: Shift+Space goes back one page`, await moved(page, () => page.keyboard.press('Shift+Space')) === -1);
  expect(`${tag}: PageDown turns one page`, await moved(page, () => page.keyboard.press('PageDown')) === 1);
  expect(`${tag}: PageUp goes back one page`, await moved(page, () => page.keyboard.press('PageUp')) === -1);
  expect(`${tag}: ArrowRight still turns one page`, await moved(page, () => page.keyboard.press('ArrowRight')) === 1);
  await page.screenshot({ path: `screenshots/reader_nav_mouse_${width}.png` });
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
