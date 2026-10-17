// Reader themes: Light and Dark only. Sepia was nearly the same as Light
// (both warm paper), so it was merged into Light; a saved "sepia" opens as
// Light.
//
// Run: node reader_themes.mjs   (Flask on :5001)

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const browser = await chromium.launch({ headless: true });
const open = async (savedTheme) => {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
  if (savedTheme) await ctx.addInitScript((t) => { localStorage.setItem('reading_theme', t); }, savedTheme);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/books/the-iliad/read?mode=plain`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
  const state = await page.evaluate(() => ({
    choices: [...document.querySelectorAll('.theme-choice')].map((b) => b.dataset.theme),
    active: document.querySelector('.theme-choice.active')?.dataset.theme,
    applied: document.getElementById('continuous-reader-section').getAttribute('data-theme'),
    stored: localStorage.getItem('reading_theme'),
  }));
  await ctx.close();
  return state;
};

const fresh = await open(null);
expect('theme picker offers only Light and Dark', fresh.choices.join() === 'light,dark', fresh.choices.join());
expect('default theme is Light', fresh.applied === 'light' && fresh.active === 'light', JSON.stringify(fresh));

const migrated = await open('sepia');
expect('a saved Sepia theme opens as Light', migrated.applied === 'light' && migrated.active === 'light', JSON.stringify(migrated));
expect('the saved Sepia preference is rewritten to Light', migrated.stored === 'light', migrated.stored);

const dark = await open('dark');
expect('a saved Dark theme still opens as Dark', dark.applied === 'dark' && dark.active === 'dark', JSON.stringify(dark));

await browser.close();
process.exit(failed ? 1 : 0);
