// Phone header (2026-10-18 iPhone report):
//  1. Categories is reachable from the header, not only the footer.
//  2. A signed-out visitor can sign in from the header.
//  3. The opened search bar doesn't overlap the page's breadcrumb.
//
// Run: node mobile_header.mjs   (Flask on :5001)

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const OUT = new URL('./screenshots/', import.meta.url).pathname;
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};
const visible = (page, sel) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { shown: r.width > 0 && r.height > 0 && r.right <= innerWidth + 0.5, right: Math.round(r.right), href: el.getAttribute('href') };
}, sel);

const browser = await chromium.launch({ headless: true });
for (const width of [360, 402]) {
  const ctx = await browser.newContext({ viewport: { width, height: 800 }, isMobile: true, hasTouch: true });
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ status: 401, json: { authenticated: false } }));
  const page = await ctx.newPage();
  await page.goto(`${BASE}/books/a-christmas-carol-in-prose`, { waitUntil: 'networkidle' });

  const cat = await visible(page, '.header #categories-nav-btn');
  expect(`${width}px: Categories link shows in the header`, cat?.shown, JSON.stringify(cat));
  const signin = await visible(page, '.header #header-signin-link');
  expect(`${width}px: signed out, header has a sign-in link`, signin?.shown && /\/login/.test(signin.href || ''), JSON.stringify(signin));
  const noOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
  expect(`${width}px: header causes no horizontal scroll`, noOverflow);

  await page.click('#header-search-toggle');
  await page.waitForSelector('#header-search-panel', { state: 'visible' });
  const geo = await page.evaluate(() => {
    const panel = document.getElementById('header-search-panel').getBoundingClientRect();
    const crumb = document.querySelector('#breadcrumb-nav-book:not(.hidden)')?.getBoundingClientRect();
    return { panelBottom: Math.round(panel.bottom), crumbTop: crumb ? Math.round(crumb.top) : null };
  });
  await page.screenshot({ path: `${OUT}mobile-header-search-${width}.png` });
  expect(`${width}px: open search bar sits above the breadcrumb`, geo.crumbTop !== null && geo.panelBottom <= geo.crumbTop, JSON.stringify(geo));

  // Results drop below the bar, unclipped by the header.
  await page.type('#header-search-input', 'dickens');
  await page.waitForSelector('#header-search-results .hero-search-result-item');
  const hit = await page.evaluate(() => {
    const item = document.querySelector('#header-search-results .hero-search-result-item');
    const r = item.getBoundingClientRect();
    const input = document.getElementById('header-search-input').getBoundingClientRect();
    const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return { onItem: !!top && item.contains(top), belowInput: r.top >= input.bottom };
  });
  expect(`${width}px: search results show below the bar`, hit.onItem && hit.belowInput, JSON.stringify(hit));
  await ctx.close();
}

// Signed in: the account button replaces the sign-in link, and Library +
// Discover + Categories + search + account fit without scrolling.
for (const width of [360, 402]) {
  const ctx = await browser.newContext({ viewport: { width, height: 800 }, isMobile: true });
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: true, user: { email: 'reader@example.test' } } }));
  const page = await ctx.newPage();
  await page.goto(`${BASE}/books/a-christmas-carol-in-prose`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#library-nav-btn:not(.hidden)');
  const s = await page.evaluate(() => {
    const hc = document.querySelector('.header-content');
    const cat = document.getElementById('categories-nav-btn').getBoundingClientRect();
    const nav = document.querySelector('.header-nav-buttons').getBoundingClientRect();
    return {
      signin: getComputedStyle(document.getElementById('header-signin-link') || document.body).display,
      hasLink: !!document.getElementById('header-signin-link'),
      headerScrolls: hc.scrollWidth > hc.clientWidth,
      categoriesClipped: cat.right > nav.right + 0.5,
    };
  });
  expect(`${width}px signed in: no header sign-in link`, s.hasLink && s.signin === 'none', JSON.stringify(s));
  expect(`${width}px signed in: nav fits on one line`, !s.headerScrolls && !s.categoriesClipped, JSON.stringify(s));
  await ctx.close();
}

await browser.close();
process.exit(failed ? 1 : 0);
