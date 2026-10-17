// Touch (mobile) page turns in the continuous reader.
//
// Swipe is first class on mobile: no visible page-turn buttons cover the text
// (they stay in the accessibility tree for screen readers), the page follows
// the finger while dragging, and on release it turns (long drag or quick
// flick) or snaps back. At the start of the book the drag meets resistance.
// Like Kindle, the neighboring page is already rendered during the drag and
// both pages slide together, edge to edge across the screen.
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
// seen just before lifting the finger (and runs `probe` at that moment).
const drag = async (x0, dx, { steps = 10, stepMs = 30, dy = 0, probe = null } = {}) => {
  await touch('touchStart', x0);
  for (let i = 1; i <= steps; i += 1) {
    await touch('touchMove', x0 + (dx * i) / steps, y + (dy * i) / steps);
    await page.waitForTimeout(stepMs);
  }
  const during = await shift();
  if (probe) await probe();
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

// The neighboring page is rendered during the drag and slides in edge to edge.
const neighbor = () => page.evaluate((w) => {
  const norm = (t) => t.replace(/\s+/g, ' ').trim();
  const textOf = (html) => { const d = document.createElement('div'); d.innerHTML = html || ''; return norm(d.textContent); };
  const app = window.summraApp;
  const i = app.pagination.currentPage;
  const n = document.querySelector('.pagination-neighbor');
  const p = document.querySelector('.pagination-page-container:not(.pagination-neighbor)');
  if (!n) return null;
  const nr = n.getBoundingClientRect();
  const pr = p.getBoundingClientRect();
  // The neighbor is inert and ignores pointers, which also hides it from
  // elementFromPoint; lift both just for this visibility probe.
  const hitAt = (x) => {
    n.inert = false; n.style.pointerEvents = 'auto';
    const hit = !!document.elementFromPoint(x, pr.top + 60)?.closest('.pagination-neighbor');
    n.inert = true; n.style.pointerEvents = '';
    return hit;
  };
  return {
    text: norm(n.textContent), next: textOf(app.pagination.pages[i + 1]), prev: textOf(app.pagination.pages[i - 1]),
    gap: Math.round(nr.left - pr.left), rightEdgeHit: hitAt(w - 5), leftEdgeHit: hitAt(5),
    anchors: n.querySelectorAll('[data-reader-anchor]').length,
  };
}, width);

let seen = null;
await drag(300, -80, { stepMs: 40, probe: async () => { seen = await neighbor(); } });
expect('mid-drag forward: the next page is already rendered', seen && seen.text && seen.text === seen.next, seen ? `${seen.text.slice(0, 40)} | ${seen.next.slice(0, 40)}` : 'no neighbor');
expect('mid-drag forward: the next page sits one screen width to the right', seen && Math.abs(seen.gap - width) <= 2, seen && `gap ${seen.gap} vs ${width}`);
expect('mid-drag forward: it shows at the screen edge, not clipped', seen?.rightEdgeHit === true);
expect('the rendered neighbor carries no reading anchors', seen?.anchors === 0, seen && `${seen.anchors}`);
expect('after snapping back the neighbor is gone', await page.evaluate(() => !document.querySelector('.pagination-neighbor')));

seen = null;
await drag(60, 120, { stepMs: 40, probe: async () => { seen = await neighbor(); } });
expect('mid-drag back: the previous page is rendered on the left', seen && seen.text && seen.text === seen.prev && Math.abs(seen.gap + width) <= 2, seen ? `gap ${seen.gap}` : 'no neighbor');
expect('mid-drag back: it shows at the left screen edge', seen?.leftEdgeHit === true);

seen = null;
before = await pageIndex();
await drag(320, -180, { stepMs: 30, probe: async () => { seen = await neighbor(); } });
const landed = await page.evaluate(() => ({
  pages: document.querySelectorAll('.pagination-page-container').length,
  neighbors: document.querySelectorAll('.pagination-neighbor').length,
  text: document.querySelector('.pagination-page-container').textContent.replace(/\s+/g, ' ').trim(),
}));
expect('a committed swipe turns one page', (await pageIndex()) === before + 1);
expect('after the turn only the real page remains', landed.pages === 1 && landed.neighbors === 0, JSON.stringify({ ...landed, text: undefined }));
expect('the page that lands is the one that slid in (seamless)', seen && landed.text === seen.text, `${landed.text.slice(0, 40)} | ${seen?.text.slice(0, 40)}`);
expect('after the turn the page is in place', Math.abs(await shift()) < 1, `shift ${await shift()}`);

await page.screenshot({ path: 'screenshots/reader_nav_touch.png' });
await ctx.close();
await browser.close();
process.exit(failed ? 1 : 0);
