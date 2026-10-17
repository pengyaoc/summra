// One-time page-turn hint in the continuous reader.
//
// Mobile: "Swipe to turn pages" with a small nudge of the page. Mouse: a tip
// naming the margins, the wheel and the arrow keys. A signed-in reader sees
// each hint once per account (the server remembers it, so a new device does
// not show it again); a signed-out reader sees it once per browser.
//
// Run: node reader_nav_hint.mjs   (Flask on :5001)

import { chromium, devices } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const URL = `${BASE}/books/the-iliad/read?mode=plain`;
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const browser = await chromium.launch({ headless: true });
const MOBILE = devices['iPhone 13'];
const DESKTOP = { viewport: { width: 1280, height: 900 } };

// signedIn: null for signed out, else the hints the server says were seen.
const open = async (options, signedIn, ctx = null) => {
  ctx ||= await browser.newContext(options);
  const posted = [];
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: signedIn
    ? { authenticated: true, user: { id: 1, email: 'me@example.com' }, hints_seen: signedIn }
    : { authenticated: false } }));
  await ctx.route(/\/api\/hints\/[^/]+\/seen$/, (r) => { posted.push(r.request().url().split('/hints/')[1]); r.fulfill({ json: { success: true } }); });
  await ctx.route(/\/api\/progress\/v2\/books\//, (r) => r.fulfill({ json: { success: true, book: null, modes: [] } }));
  const page = await ctx.newPage();
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
  // Wait for the hint (or give it 1.5s to not appear), then let any POST land.
  await page.waitForSelector('.page-turn-hint', { timeout: 1500 }).catch(() => {});
  await page.waitForTimeout(300);
  const hint = await page.evaluate(() => document.querySelector('.page-turn-hint')?.textContent.trim() || null);
  return { ctx, page, posted, hint };
};

{
  const { ctx, page, posted, hint } = await open(MOBILE, []);
  expect('mobile, signed in, first time: swipe hint shows', /swipe/i.test(hint || ''), hint);
  expect('mobile: the page nudges to show it moves', await page.evaluate(() => !!document.querySelector('.hint-nudge')));
  expect('mobile: hint is recorded on the account as soon as it shows', posted.join() === 'reader_swipe_mobile/seen', posted.join());
  await page.touchscreen.tap(195, 400);
  await page.waitForTimeout(500);
  expect('mobile: the first touch dismisses the hint', await page.evaluate(() => !document.querySelector('.page-turn-hint')));
  await ctx.close();
}
{
  const { ctx, posted, hint } = await open(MOBILE, ['reader_swipe_mobile']);
  expect('mobile, signed in, already seen on another device: no hint', hint === null, hint);
  expect('mobile, already seen: nothing posted', posted.length === 0, posted.join());
  await ctx.close();
}
{
  const first = await open(MOBILE, null);
  expect('mobile, signed out, first visit: swipe hint shows', /swipe/i.test(first.hint || ''), first.hint);
  expect('mobile, signed out: nothing posted to the server', first.posted.length === 0, first.posted.join());
  await first.page.close();
  const again = await open(MOBILE, null, first.ctx);
  expect('mobile, signed out, same browser again: no hint', again.hint === null, again.hint);
  await first.ctx.close();
}
{
  const { ctx, posted, hint } = await open(DESKTOP, []);
  expect('desktop, signed in, first time: mouse tip shows', /margin/i.test(hint || '') && /←/.test(hint || ''), hint);
  expect('desktop: tip recorded under its own key', posted.join() === 'reader_nav_desktop/seen', posted.join());
  await ctx.close();
}
{
  const { ctx, hint } = await open(DESKTOP, ['reader_nav_desktop']);
  expect('desktop, already seen: no tip', hint === null, hint);
  await ctx.close();
}
{
  // The reader can rebuild its page wrapper (here: a resize) while the
  // sign-in check is still pending. The hint must still show, once.
  const ctx = await browser.newContext(MOBILE);
  await ctx.route(/\/auth\/check$/, async (r) => { await new Promise((ok) => setTimeout(ok, 1500)); r.fulfill({ json: { authenticated: false } }); });
  const page = await ctx.newPage();
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
  await page.setViewportSize({ width: 380, height: 700 });
  await page.waitForTimeout(2500);
  const hints = await page.evaluate(() => document.querySelectorAll('.page-turn-hint').length);
  expect('wrapper rebuilt while sign-in check pending: hint still shows once', hints === 1, `${hints} hints`);
  await ctx.close();
}
{
  // ...or right after the hint appears: the hint and nudge must survive it.
  const { ctx, page, hint } = await open(MOBILE, null);
  await page.setViewportSize({ width: 380, height: 700 });
  await page.waitForTimeout(1200);
  const after = await page.evaluate(() => ({ hints: document.querySelectorAll('.page-turn-hint').length, nudge: !!document.querySelector('.hint-nudge') }));
  expect('wrapper rebuilt after the hint shows: hint and nudge survive', hint && after.hints === 1 && after.nudge, JSON.stringify(after));
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
