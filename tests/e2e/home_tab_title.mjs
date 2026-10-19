// Regression test: the home page's browser-tab title must match the
// server-rendered Plainly title, on first load and after SPA navigation.
//
// Bug: showHomeSection() overwrote document.title with the pre-rebrand
// tagline 'Free Classic Book Summaries, Chapter Summaries & Full Text |
// Plainly', so the tab never showed the brand when narrow.
//
// Usage: BASE_URL=http://localhost:5001 node home_tab_title.mjs

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const EXPECTED = 'Plainly — Read the Classics in Plain English';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

let failed = false;
const checks = [];
function check(name, cond, detail = '') {
  checks.push({ name, cond, detail });
  if (!cond) failed = true;
}

try {
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.waitForFunction(() => window.summraApp, { timeout: 10_000 });
  await page.waitForTimeout(500);
  const initial = await page.title();
  check('home tab title on first load', initial === EXPECTED, `actual: ${JSON.stringify(initial)}`);

  // Leave home, then come back through the client-side router.
  await page.goto(`${BASE}/discover`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.waitForFunction(() => window.summraApp, { timeout: 10_000 });
  await page.waitForTimeout(500);
  await page.evaluate(async () => {
    window.history.pushState(null, '', withBasePath('/'));
    await window.summraApp.handleRoute();
  });
  await page.waitForTimeout(300);
  const afterNav = await page.title();
  check('home tab title after SPA navigation', afterNav === EXPECTED, `actual: ${JSON.stringify(afterNav)}`);
} finally {
  await browser.close();
}

for (const c of checks) {
  const tag = c.cond ? 'PASS' : 'FAIL';
  const suffix = c.detail ? ` — ${c.detail}` : '';
  console.log(`[${tag}] ${c.name}${suffix}`);
}
process.exit(failed ? 1 : 0);
