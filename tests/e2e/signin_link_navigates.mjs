// Sign-in links must do a real page load of /login (2026-10-18 report:
// "the sign in button doesn't work"). /login is served by Apache's OIDC,
// not the SPA, but setupRouting()'s delegated a[href^="/"] handler was
// pushState-ing it, so the URL changed and nothing else happened.
//
// Run: node signin_link_navigates.mjs   (Flask on :5001)

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const browser = await chromium.launch({ headless: true });
for (const [label, sel, viewport] of [
  ['header (phone)', '#header-signin-link', { width: 375, height: 800 }],
  ['footer (desktop)', '#footer-signin-link', { width: 1280, height: 800 }],
]) {
  const ctx = await browser.newContext({ viewport });
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
  // Stand in for Apache's /login so the test sees whether the browser asked for it.
  let loginRequested = false;
  await ctx.route(/\/login(\?|$)/, (r) => {
    if (r.request().isNavigationRequest()) loginRequested = true;
    r.fulfill({ contentType: 'text/html', body: '<p>login</p>' });
  });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.waitForSelector(`${sel}:not(.hidden)`);
  await page.locator(sel).scrollIntoViewIfNeeded();
  await page.click(sel);
  await page.waitForTimeout(1000);
  expect(`${label}: clicking Sign in loads /login`, loginRequested, page.url());
  await ctx.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
