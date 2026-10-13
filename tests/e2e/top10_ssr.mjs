// "Where Most Readers Start" carousel is server-rendered on the home page.
//
// Bug this guards against: the carousel used to show skeleton cards until
// app.min.js loaded, ran, and fetched all of /api/books — ~4-5s on mobile
// networks. Now index.html ships the cards, so this test asserts:
//   1. cards + cover <img>s are in the HTML before any JS runs,
//   2. clicking a card opens that book in-app,
//   3. returning home via SPA nav keeps one set of cards and the nav arrow
//      scrolls one step (no stacked duplicate listeners).

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };

const browser = await chromium.launch();
try {
  // 1. Server HTML alone (JS disabled) already contains the cards.
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const p0 = await noJs.newPage();
  await p0.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  const ssr = await p0.evaluate(() => ({
    cards: document.querySelectorAll('#top-10-scroll a.top-10-book-card').length,
    skeletons: document.querySelectorAll('#top-10-scroll .skeleton-book-card').length,
    firstImgSrc: document.querySelector('#top-10-scroll img')?.getAttribute('src'),
  }));
  console.log('SSR (no JS):', ssr);
  if (ssr.cards < 5) fail(`expected server-rendered cards, got ${ssr.cards}`);
  if (ssr.skeletons !== 0) fail('skeletons should not render when cards are server-rendered');
  if (!ssr.firstImgSrc) fail('cover <img> must be in the server HTML');
  await noJs.close();

  // 2. Clicking a card opens the book in-app.
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  const href = await page.getAttribute('#top-10-scroll a.top-10-book-card', 'href');
  await page.click('#top-10-scroll a.top-10-book-card');
  await page.waitForFunction((h) => location.pathname === h, href, { timeout: 10000 });
  await page.waitForSelector('#book-detail-section:not(.hidden), .book-page:not(.hidden)', { timeout: 10000 })
    .catch(() => {});
  const onHome = await page.evaluate(() => !document.getElementById('hero-section').classList.contains('hidden'));
  if (onHome) fail('clicking a card should leave the home view');
  console.log(`Card click navigated to ${href}`);

  // 3. Back to home via SPA navigation: still one set of cards, nav works once.
  await page.click('#header-home-link');
  await page.waitForFunction(() => !document.getElementById('hero-section').classList.contains('hidden'));
  await page.click('#header-home-link');
  await page.waitForFunction(() => !document.getElementById('hero-section').classList.contains('hidden'));
  const count = await page.locator('#top-10-scroll a.top-10-book-card').count();
  if (count < 5 || count > 10) fail(`expected 5-10 cards after SPA nav, got ${count}`);
  await page.click('#top-10-nav-right');
  await page.waitForTimeout(800);
  const scrolled = await page.evaluate(() => document.getElementById('top-10-scroll').scrollLeft);
  console.log(`Cards after SPA nav: ${count}; one arrow click scrolled ${scrolled}px`);
  if (scrolled <= 0) fail('nav arrow did not scroll');
  if (scrolled > 170 * 3 + 5) fail(`nav arrow scrolled ${scrolled}px — duplicate listeners stacked`);

  if (errors.length) fail(`page errors: ${errors.join('; ')}`);
  console.log('PASS');
} finally {
  await browser.close();
}
