// Touch (mobile) page turns in the continuous reader.
//
// Swipe is first class on mobile: no visible page-turn buttons cover the text
// (they stay in the accessibility tree for screen readers), the page follows
// the finger while dragging, and on release it turns (long drag or quick
// flick) or snaps back. At the start of the book the drag meets resistance.
//
// Run: node reader_nav_touch.mjs   (Flask on :5001)

import { chromium, devices } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext(devices['iPhone 13']);
await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await page.goto(`${BASE}/books/the-iliad/read?mode=plain`, { waitUntil: 'networkidle' });
await page.waitForFunction(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
await page.waitForTimeout(800);

const width = page.viewportSize().width;
const y = 400;
const touch = (type, x, yy = y) => cdp.send('Input.dispatchTouchEvent', {
  type, touchPoints: type === 'touchEnd' ? [] : [{ x, y: yy }],
});
const shift = () => page.evaluate(() => {
  const t = getComputedStyle(document.querySelector('.pagination-page-container')).transform;
  return t === 'none' ? 0 : new DOMMatrix(t).m41;
});
const position = () => page.evaluate(() => `${window.summraApp.continuousReader.currentSegmentId}:${window.summraApp.pagination.currentPage}`);
const pageIndex = () => page.evaluate(() => window.summraApp.pagination.currentPage);
// Drags from x0 by dx in `steps` moves `stepMs` apart; returns the page shift
// seen just before lifting the finger.
const drag = async (x0, dx, { steps = 10, stepMs = 30, dy = 0 } = {}) => {
  await touch('touchStart', x0);
  for (let i = 1; i <= steps; i += 1) {
    await touch('touchMove', x0 + (dx * i) / steps, y + (dy * i) / steps);
    await page.waitForTimeout(stepMs);
  }
  const during = await shift();
  await touch('touchEnd', x0 + dx);
  await page.waitForTimeout(700);
  return during;
};

// No buttons over the text; still reachable by screen readers.
const buttons = await page.evaluate(() => [...document.querySelectorAll('.pagination-nav-button')].map((b) => {
  const r = b.getBoundingClientRect();
  return { w: r.width, h: r.height, label: b.getAttribute('aria-label'), display: getComputedStyle(b).display };
}));
expect('no visible page-turn buttons', buttons.length === 2 && buttons.every((b) => b.w <= 1 && b.h <= 1), JSON.stringify(buttons));
expect('buttons stay available to screen readers', buttons.every((b) => b.label && b.display !== 'none'), JSON.stringify(buttons));
await page.touchscreen.tap(width / 2, y);
await page.waitForTimeout(200);
const afterTap = await page.evaluate(() => [...document.querySelectorAll('.pagination-nav-button')].every((b) => b.getBoundingClientRect().width <= 1));
expect('a tap does not reveal buttons over the text', afterTap);

// Start of the book: dragging right meets resistance and turns nothing.
const start = await position();
const resisted = await drag(60, 200);
expect('at the start, a right drag moves the page less than the finger', resisted > 0 && resisted < 100, `shift ${resisted}`);
expect('at the start, a right drag turns nothing', (await position()) === start);
expect('the page settles back after the drag', Math.abs(await shift()) < 1, `shift ${await shift()}`);

// The page follows the finger, then turns or snaps back.
let before = await pageIndex();
const during = await drag(300, -80, { stepMs: 40 });
expect('the page follows the finger while dragging', during <= -70 && during >= -85, `shift ${during}`);
expect('a slow short drag snaps back without turning', (await pageIndex()) === before);
expect('after snapping back the page is in place', Math.abs(await shift()) < 1, `shift ${await shift()}`);

before = await pageIndex();
await drag(320, -160, { stepMs: 30 });
expect('a long drag left turns one page', (await pageIndex()) === before + 1);
expect('after turning the page is in place', Math.abs(await shift()) < 1, `shift ${await shift()}`);

before = await pageIndex();
await drag(250, -45, { steps: 2, stepMs: 0 });
expect('a quick short flick left turns one page', (await pageIndex()) === before + 1);

before = await pageIndex();
await drag(60, 160, { stepMs: 30 });
expect('a long drag right goes back one page', (await pageIndex()) === before - 1);

before = await pageIndex();
const vertical = await drag(200, 30, { dy: -200 });
expect('a mostly vertical drag neither moves nor turns the page', (await pageIndex()) === before && Math.abs(vertical) < 1, `shift ${vertical}`);

await page.screenshot({ path: 'screenshots/reader_nav_touch.png' });
await ctx.close();
await browser.close();
process.exit(failed ? 1 : 0);
