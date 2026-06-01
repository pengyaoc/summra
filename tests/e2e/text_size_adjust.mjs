// Asserts -webkit-text-size-adjust is fixed at 100% on the root <html>.
//
// Why this matters: on iOS Safari and iOS Chrome (both WebKit), the URL bar
// collapses/expands on scroll. When it expands, WebKit re-runs text auto-
// sizing on fixed-position elements like .sticky-reading-header — but the
// recomputation lags behind the layout-viewport resize, so the bar visually
// jumps down while its text stays at the stale size. Pinning text-size-adjust
// to 100% disables that autosizing pass entirely and makes the bar resize
// deterministically with the viewport.
//
// We can't reproduce the iOS bug on desktop Chromium, so this test guards
// against accidental removal of the rule rather than the symptom itself.
//
// Usage: BASE_URL=http://localhost:5001 node text_size_adjust.mjs

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const URL = `${BASE}/`;

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

let failed = false;
try {
  const response = await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  if (!response || !response.ok()) {
    console.error(`FAIL: ${URL} returned ${response ? response.status() : 'no response'}`);
    failed = true;
  } else {
    const value = await page.evaluate(() => {
      const s = window.getComputedStyle(document.documentElement);
      return s.getPropertyValue('-webkit-text-size-adjust').trim() ||
             s.getPropertyValue('text-size-adjust').trim();
    });
    if (value !== '100%') {
      console.error(`FAIL: html text-size-adjust = ${JSON.stringify(value)} (expected "100%")`);
      console.error('  Without this rule, iOS Safari rescales sticky-header text on URL-bar resize.');
      failed = true;
    } else {
      console.log('PASS: html text-size-adjust = 100%');
    }
  }
} finally {
  await browser.close();
}

process.exit(failed ? 1 : 0);
