// Reader fonts: Figtree replaced Open Sans as the sans choice. Open Sans was
// never loaded, so it showed Helvetica; Figtree is bundled and must actually
// render. A saved "opensans" opens as Figtree.
//
// Run: node reader_font_figtree.mjs   (Flask on :5001)

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const browser = await chromium.launch({ headless: true });
const open = async (savedFont) => {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
  if (savedFont) await ctx.addInitScript((f) => { localStorage.setItem('reading_font', f); }, savedFont);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/books/the-iliad/read?mode=plain`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
  await page.evaluate(() => document.fonts.ready);
  const state = await page.evaluate(() => {
    const p = document.querySelector('.pagination-page-container p');
    return {
      choices: [...document.querySelectorAll('.font-choice')].map((b) => b.dataset.font),
      labels: [...document.querySelectorAll('.font-labels span')].map((s) => s.textContent.trim()),
      active: document.querySelector('.font-choice.active')?.dataset.font,
      applied: document.getElementById('continuous-reader-section').getAttribute('data-font'),
      stored: localStorage.getItem('reading_font'),
      family: p ? getComputedStyle(p).fontFamily : '',
      loaded: [...document.fonts].some((f) => f.family.replace(/"/g, '') === 'Figtree' && f.status === 'loaded'),
    };
  });
  await ctx.close();
  return state;
};

const fresh = await open(null);
expect('font picker offers Reader Serif, System, Figtree', fresh.choices.join() === 'georgia,system,figtree', fresh.choices.join());
expect('font labels read Reader Serif, System, Figtree', fresh.labels.join() === 'Reader Serif,System,Figtree', fresh.labels.join());

const fig = await open('figtree');
expect('a saved Figtree font opens as Figtree', fig.applied === 'figtree' && fig.active === 'figtree', JSON.stringify(fig));
expect('reader text uses the Figtree family', /^"?Figtree"?/.test(fig.family), fig.family);
expect('the Figtree web font is loaded', fig.loaded === true);

const migrated = await open('opensans');
expect('a saved Open Sans font opens as Figtree', migrated.applied === 'figtree' && migrated.active === 'figtree', JSON.stringify(migrated));
expect('the saved Open Sans preference is rewritten to Figtree', migrated.stored === 'figtree', migrated.stored);

await browser.close();
process.exit(failed ? 1 : 0);
