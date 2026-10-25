// Reader style snapshot: records computed styles of the reader chrome and
// panels, then compares later runs against the recording. Guards the move of
// Plainly's reader files into shared/ (phase 3): the reader must look the
// same afterwards.
//
// Run: MODE=record BASE_URL=http://localhost:5002 node reader_style_snapshot.mjs
//      MODE=compare BASE_URL=http://localhost:5002 node reader_style_snapshot.mjs
// MODE=compare exits 1 on any difference. The JSON is written to
// screenshots/reader_styles.json (gitignored), so re-record on main if lost.

import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const MODE = process.env.MODE || 'compare';
const SLUG = process.env.SLUG || 'pride-and-prejudice';
const FILE = path.join(path.dirname(fileURLToPath(import.meta.url)), 'screenshots', 'reader_styles.json');

const SELECTORS = [
  '.continuous-reader-chrome', '.reader-toolbar-btn', '.continuous-reader-content',
  '.pagination-page-container', '.pagination-page-container p', '.reader-chapter-heading',
  '.continuous-reader-footer', '#reader-progress-fill', '.reading-settings-panel',
  '.font-choice', '.size-btn', '.theme-choice', '.reader-panel',
];
// The book card only renders on the home page, so it is measured there.
const HOME_SELECTORS = [
  '.library-card', '.library-card-cover-frame', '.library-card-body', '.library-card-meta', '.library-card-author',
];
const PROPS = [
  'font-family', 'font-size', 'font-weight', 'line-height', 'color', 'background-color',
  'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'width', 'height', 'display', 'position',
];
const VIEWPORTS = { desktop: { width: 1280, height: 900 }, mobile: { width: 390, height: 844 } };

const browser = await chromium.launch({ headless: true });
const result = {};

for (const [vpName, viewport] of Object.entries(VIEWPORTS)) {
  for (const theme of ['light', 'dark']) {
    const ctx = await browser.newContext({ viewport });
    await ctx.addInitScript((t) => { try { localStorage.clear(); localStorage.setItem('reading_theme', t); } catch (_) {} }, theme);
    await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
    const page = await ctx.newPage();
    await page.goto(`${BASE}/books/${SLUG}/read`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
    // Open the panels so they are measured while visible.
    const settings = page.locator('#reader-settings-button, [aria-label="Reading settings"], .reader-settings-btn').first();
    if (await settings.count()) await settings.click().catch(() => {});
    const toc = page.locator('#reader-toc-button, [aria-label="Table of contents"], .reader-toc-btn').first();
    if (await toc.count()) await toc.click().catch(() => {});
    await page.waitForTimeout(400);
    // Fall back to unhiding the panels if the buttons were not found.
    await page.evaluate(() => {
      document.querySelectorAll('.reading-settings-panel.hidden, .reader-panel.hidden').forEach((e) => e.classList.remove('hidden'));
    });
    const measure = ({ selectors, props }) => {
      const out = {};
      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (!el) { out[sel] = null; continue; }
        const cs = getComputedStyle(el);
        out[sel] = Object.fromEntries(props.map((p) => [p, cs.getPropertyValue(p)]));
      }
      return out;
    };
    result[`${vpName}-${theme}`] = await page.evaluate(measure, { selectors: SELECTORS, props: PROPS });
    // Fresh context, no auth mock: the signed-out home only shows the cards then.
    const homeCtx = await browser.newContext({ viewport });
    await homeCtx.addInitScript((t) => { try { localStorage.setItem('reading_theme', t); } catch (_) {} }, theme);
    const home = await homeCtx.newPage();
    await home.goto(`${BASE}/`, { waitUntil: 'networkidle' });
    await home.waitForSelector('.library-card', { state: 'visible' });
    result[`${vpName}-${theme}-home`] = await home.evaluate(measure, { selectors: HOME_SELECTORS, props: PROPS });
    await homeCtx.close();
    await ctx.close();
  }
}
await browser.close();

if (MODE === 'record') {
  fs.mkdirSync(path.dirname(FILE), { recursive: true });
  fs.writeFileSync(FILE, JSON.stringify(result, null, 2));
  const found = Object.values(result).flatMap((v) => Object.values(v)).filter(Boolean).length;
  const missingCard = Object.entries(result).filter(([k, v]) => k.endsWith('-home') && !v['.library-card']);
  if (missingCard.length) { console.log('library-card not found on home'); process.exit(1); }
  console.log(`recorded ${Object.keys(result).length} variants, ${found} measured elements -> ${FILE}`);
  process.exit(0);
}

const before = JSON.parse(fs.readFileSync(FILE, 'utf8'));
const diffs = [];
for (const variant of Object.keys(before)) {
  for (const sel of variant.endsWith('-home') ? HOME_SELECTORS : SELECTORS) {
    const a = before[variant]?.[sel];
    const b = result[variant]?.[sel];
    if (JSON.stringify(a) === JSON.stringify(b)) continue;
    if (!a || !b) { diffs.push(`${variant} ${sel}: ${a ? 'now missing' : 'newly present'}`); continue; }
    for (const p of PROPS) if (a[p] !== b[p]) diffs.push(`${variant} ${sel} ${p}: ${a[p]} -> ${b[p]}`);
  }
}
if (diffs.length) {
  console.log(diffs.join('\n'));
  console.log(`${diffs.length} differences`);
  process.exit(1);
}
console.log('no differences');
