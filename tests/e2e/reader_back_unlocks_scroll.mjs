// Leaving the reader with browser back (iOS Chrome's edge swipe, or the back
// button) must leave the home page scrollable.
//
// Bug (iOS Chrome, 2026-10-17): after reader → back, the home page could not
// scroll. The reader locks html/body scrolling while open. Browser back
// unlocked it but left the reader "active", so reader work finishing later
// (a section still loading, or the page turn of the swipe that was the back
// gesture) re-ran pagination and locked the home page again.
//
// Run: node reader_back_unlocks_scroll.mjs   (Flask on :5001)
//      ENGINE=webkit node reader_back_unlocks_scroll.mjs   (iOS's engine)

import { chromium, webkit, devices } from 'playwright';

const ENGINE = process.env.ENGINE === 'webkit' ? webkit : chromium;

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const browser = await ENGINE.launch({ headless: true });

// Home → reader (in-app navigation, so browser back is a popstate), moved a
// couple of sections in so there is a previous section to load.
const openReaderFromHome = async (delaySegments = 0) => {
  const ctx = await browser.newContext(devices['iPhone 13']);
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
  await ctx.addInitScript(() => { localStorage.setItem('summra-hint-reader_swipe_mobile', '1'); });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.evaluate(() => { history.pushState({}, '', `${window.APP_BASE_PATH || ''}/books/the-iliad/read?mode=plain`); window.summraApp.handleRoute(); });
  await page.waitForFunction(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
  for (let i = 0; i < 2; i += 1) {
    const before = await page.evaluate(() => window.summraApp.continuousReader.currentSegmentId);
    await page.evaluate(() => window.summraApp.navigateContinuousSegment(1));
    await page.waitForFunction((id) => window.summraApp.continuousReader.currentSegmentId !== id, before);
  }
  await page.waitForTimeout(400);
  if (delaySegments) {
    await ctx.route(/\/reader\/books\/\d+\/segments\//, async (r) => { await new Promise((ok) => setTimeout(ok, delaySegments)); r.continue(); });
    await page.evaluate(() => { window.summraApp.continuousReader.requests = new Map(); }); // force a real fetch
  }
  return { ctx, page };
};

const goBackHome = async (page) => {
  await page.evaluate(() => history.back());
  await page.waitForFunction(() => !location.pathname.includes('/read'));
};

const homeScrolls = async (page, label) => {
  await page.waitForTimeout(2500); // let any late reader work finish
  const s = await page.evaluate(() => ({
    path: location.pathname,
    html: getComputedStyle(document.documentElement).overflow,
    body: getComputedStyle(document.body).overflow,
    classes: `${document.documentElement.className}|${document.body.className}`,
  }));
  const unlocked = s.html !== 'hidden' && s.body !== 'hidden' && !s.classes.includes('pagination-active');
  // Mobile WebKit has no synthetic scroll input; there the lock itself is checked.
  let scrolled = null;
  if (ENGINE === chromium) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.mouse.move(200, 600);
    await page.mouse.wheel(0, 500);
    await page.waitForTimeout(400);
    scrolled = await page.evaluate(() => scrollY);
  }
  expect(`${label}: home page scrolls`, unlocked && (scrolled === null || scrolled > 100), JSON.stringify({ ...s, scrolled }));
};

{
  const { ctx, page } = await openReaderFromHome();
  await goBackHome(page);
  await homeScrolls(page, 'plain browser back');
  await ctx.close();
}
{
  // iOS Chrome's back gesture is a swipe from the left edge; the reader sees
  // the same touches as a drag to the previous page.
  const { ctx, page } = await openReaderFromHome();
  // Touch-shaped events dispatched in the page: WebKit forbids new Touch(),
  // and the reader only reads touches/changedTouches/clientX/clientY.
  const send = (target, type, x) => {
    const point = { identifier: 1, target, clientX: x, clientY: 400 };
    const event = new Event(type, { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'touches', { value: type === 'touchend' ? [] : [point] });
    Object.defineProperty(event, 'changedTouches', { value: [point] });
    target.dispatchEvent(event);
  };
  const wrapper = await page.evaluateHandle(() => document.querySelector('.pagination-wrapper'));
  const touch = (type, x) => wrapper.evaluate((w, [send, type, x]) => new Function('return ' + send)()(w, type, x), [send.toString(), type, x]);
  await touch('touchstart', 8);
  for (let x = 40; x <= 280; x += 40) { await touch('touchmove', x); await page.waitForTimeout(16); }
  await goBackHome(page);
  // The finger lifts after the page has gone back; the touch still ends on
  // the reader's (now hidden) page, as on iOS.
  await touch('touchend', 280);
  await homeScrolls(page, 'back by edge swipe');
  await ctx.close();
}
{
  const { ctx, page } = await openReaderFromHome(1500);
  await page.evaluate(() => { window.summraApp.navigateContinuousSegment(-1); });
  await goBackHome(page);
  await homeScrolls(page, 'back while a section is loading');
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
