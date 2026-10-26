// Distill web scenario: library -> book page -> reader, on the shared reader platform.
//
//   DISTILL_USER_DB=$TMPDIR/distill_user_e2e.db PORT=5003 venv/bin/python -m distill.app
//   cd tests/e2e && node distill.mjs
//
// Exits 1 on any FAIL or console error. Screenshots go to screenshots/distill_*.png.

import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const SLUG = process.env.DISTILL_SLUG || 'atomic-habits';
const ZH_SLUG = process.env.DISTILL_ZH_SLUG || 'quanqiutongshi-zhangjie-zongjie';
const SHOTS = new URL('./screenshots/', import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

let failures = 0;
const fail = (msg) => { failures++; console.error(`FAIL: ${msg}`); };
const check = (ok, msg) => { if (!ok) fail(msg); else console.log(`ok   ${msg}`); };

const browser = await chromium.launch({ headless: !process.env.HEADED });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

const problems = [];
page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
page.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
page.on('requestfailed', (r) => {
  if (r.url().startsWith(BASE)) problems.push(`request failed: ${r.url()} ${r.failure()?.errorText}`);
});
page.on('response', (r) => {
  if (r.url().startsWith(BASE) && r.status() >= 400) problems.push(`HTTP ${r.status()}: ${r.url()}`);
});

const anchorsReady = () => page.waitForSelector('#continuous-reader-content [data-reader-anchor]', { timeout: 15000 });

// The first anchored block on the current page: what "where I am" means after a reload.
const firstAnchor = () => page.evaluate(() => {
  const el = [...document.querySelectorAll('#continuous-reader-content [data-reader-anchor]')].find((e) => {
    const r = e.getBoundingClientRect();
    return r.height > 0 && r.bottom > 0 && r.top < innerHeight && getComputedStyle(e).display !== 'none';
  });
  return el ? el.getAttribute('data-reader-anchor') : null;
});

// Per-page checks, run on every page turned: anchored blocks fit the page, and
// list items / table cells keep their separating whitespace in the DOM text.
const inspectPage = () => page.evaluate(() => {
  const wrapper = document.querySelector('.pagination-wrapper');
  const pageBottom = wrapper ? wrapper.getBoundingClientRect().bottom : innerHeight;
  const overflowing = [];
  for (const el of document.querySelectorAll('#continuous-reader-content [data-reader-anchor]')) {
    const r = el.getBoundingClientRect();
    if (r.height === 0 || getComputedStyle(el).display === 'none') continue;
    if (el.matches('table.reader-table')) continue; // a table scrolls inside its own box
    if (r.bottom > pageBottom + 1) overflowing.push(`${el.tagName}.${el.className} bottom=${Math.round(r.bottom)} page=${Math.round(pageBottom)}`);
  }
  const merged = [];
  for (const list of document.querySelectorAll('#continuous-reader-content ul, #continuous-reader-content ol')) {
    const items = [...list.children].filter((c) => c.tagName === 'LI').map((c) => c.textContent);
    for (let i = 1; i < items.length; i++) if (!list.textContent.includes(`${items[i - 1]}\n${items[i]}`)) merged.push(`li: ${items[i - 1]} | ${items[i]}`);
  }
  for (const row of document.querySelectorAll('#continuous-reader-content table.reader-table tr')) {
    const cells = [...row.children].map((c) => c.textContent);
    for (let i = 1; i < cells.length; i++) if (!row.textContent.includes(`${cells[i - 1]} ${cells[i]}`)) merged.push(`td: ${cells[i - 1]} | ${cells[i]}`);
  }
  const img = [...document.querySelectorAll('#continuous-reader-content figure.reader-figure img')]
    .find((i) => i.getBoundingClientRect().height > 0);
  return {
    overflowing, merged,
    imageOk: img ? img.complete && img.naturalWidth > 0 : null,
    hasTable: !!document.querySelector('#continuous-reader-content table.reader-table'),
  };
});

try {
  // --- Library -> book page -> reader -------------------------------------
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  check(await page.locator('.distill-tile').count() > 0, 'library lists books');
  check(await page.locator('.book-cover-placeholder').count() > 0, 'books without a cover get a placeholder card');
  await page.screenshot({ path: `${SHOTS}distill_library.png`, fullPage: false });

  await page.click(`a.distill-tile[href$="/books/${SLUG}"]`);
  await page.waitForSelector('h1');
  check(/\/books\/[^/]+$/.test(new URL(page.url()).pathname) && (await page.locator('h1').innerText()).length > 0, 'library leads to the book page with an h1');
  check(await page.locator('.toc-part-title').count() > 0, 'book page has part headings');
  await page.screenshot({ path: `${SHOTS}distill_book.png`, fullPage: false });

  await page.click('a.library-read-action');
  await anchorsReady();
  check(new URL(page.url()).pathname.endsWith(`/books/${SLUG}/read`), 'read link opens the reader');
  check(await page.locator('#continuous-reader-content [data-reader-anchor]').count() > 0, 'reader shows anchored blocks');
  const modeSelector = page.locator('#reader-mode-settings');
  check(await modeSelector.count() === 0 || !(await modeSelector.isVisible()), 'mode selector is absent or hidden');
  check(!(await page.locator('#reader-toc-panel').isVisible()) && !(await page.locator('#reading-settings-panel').isVisible()),
    'contents and settings panels start closed');
  await page.screenshot({ path: `${SHOTS}distill_reader.png` });

  // --- Find a chapter with both an image and a table, via the API ---------
  const bookId = await page.evaluate(() => window.DISTILL_BOOK.id);
  const found = await page.evaluate(async (id) => {
    const manifest = (await (await fetch(`/api/reader/books/${id}/manifest`)).json()).manifest;
    const kinds = new Map();
    for (const segment of manifest.segments) {
      const data = (await (await fetch(`/api/reader/books/${id}/segments/${segment.id}?mode=summary`)).json()).segment;
      for (const unit of data.units) {
        const type = JSON.parse(unit.content).type;
        if (type === 'image' || type === 'table') {
          if (!kinds.has(unit.chapter_id)) kinds.set(unit.chapter_id, new Set());
          kinds.get(unit.chapter_id).add(type);
        }
      }
    }
    return [...kinds].map(([chapter, types]) => ({ chapter, types: [...types] }));
  }, bookId);
  const both = found.find((c) => c.types.length === 2);
  check(!!both, `a chapter with an image and a table exists (chapter ${both?.chapter})`);

  if (both) {
    await page.goto(`${BASE}/books/${SLUG}/read?chapter=${both.chapter}`, { waitUntil: 'networkidle' });
    await anchorsReady();
    let sawImage = false, sawTable = false, imageBroken = false, pages = 0;
    const overflow = [], merged = [];
    for (let i = 0; i < 150 && (!(sawImage && sawTable) || i < 20); i++, pages++) {
      const info = await inspectPage();
      overflow.push(...info.overflowing);
      merged.push(...info.merged);
      if (info.imageOk !== null) {
        if (!sawImage) await page.screenshot({ path: `${SHOTS}distill_figure.png` });
        sawImage = true;
        if (!info.imageOk) imageBroken = true;
      }
      if (info.hasTable && !sawTable) { sawTable = true; await page.screenshot({ path: `${SHOTS}distill_table.png` }); }
      await page.keyboard.press('ArrowRight');
      await page.waitForTimeout(120);
    }
    check(sawImage && !imageBroken, 'figure images load (naturalWidth > 0)');
    check(sawImage && sawTable, `paged through ${pages} pages to an image and a table`);
    check(overflow.length === 0, `no anchored block overflows its page${overflow.length ? ': ' + overflow.slice(0, 3).join('; ') : ''}`);
    check(merged.length === 0, `list items and table cells keep separating whitespace${merged.length ? ': ' + merged.slice(0, 3).join('; ') : ''}`);
  }

  // --- Key points label comes from CSS, per language ----------------------
  const label = await page.evaluate(() => {
    const ul = document.createElement('ul');
    ul.className = 'reader-keypoints';
    document.body.appendChild(ul);
    const content = getComputedStyle(ul, '::before').content;
    ul.remove();
    return content;
  });
  check(label === '"Key points"', `.reader-keypoints::before is ${label}`);

  // --- A reload restores the same place -----------------------------------
  await page.goto(`${BASE}/books/${SLUG}/read?chapter=${found.find((c) => c.types.length)?.chapter ?? ''}`, { waitUntil: 'networkidle' });
  await anchorsReady();
  // Pause past the reader's 600 ms save debounce so each forward turn is saved as sequential reading.
  for (let i = 0; i < 3; i++) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(750); }
  await page.waitForTimeout(1500);
  const before = await firstAnchor();
  await page.goto(`${BASE}/books/${SLUG}/read`, { waitUntil: 'networkidle' });
  await anchorsReady();
  await page.waitForTimeout(500);
  const after = await firstAnchor();
  check(!!before && before === after, `reload restores the first anchor (${before} -> ${after})`);

  // --- Library shows it under Reading now ---------------------------------
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  check(await page.locator(`.library-card a.library-read-action[href$="/books/${SLUG}/read"]`).count() === 1, 'library lists the book under Reading now');
  check(/Chapter \d+ of \d+|Overview/.test(await page.locator('.library-card-location').first().innerText()), 'Reading now card shows the progress label');
  await page.screenshot({ path: `${SHOTS}distill_library_reading_now.png` });

  // --- Cache isolation from Plainly (same origin in production) -----------
  const dbs = (await page.evaluate(() => indexedDB.databases())).map((d) => d.name);
  check(dbs.includes('distill-reader-v1'), `IndexedDB has distill-reader-v1 (${dbs.join(', ')})`);
  check(!dbs.includes('summra-reader-v2'), 'IndexedDB has no summra-reader-v2');

  // --- Chinese book -------------------------------------------------------
  await page.goto(`${BASE}/books/${ZH_SLUG}/read`, { waitUntil: 'networkidle' });
  await anchorsReady();
  check(await page.evaluate(() => document.documentElement.lang) === 'zh', 'zh reader has lang=zh');
  const zhLabel = await page.evaluate(() => {
    const ul = document.createElement('ul');
    ul.className = 'reader-keypoints';
    document.body.appendChild(ul);
    const content = getComputedStyle(ul, '::before').content;
    ul.remove();
    return content;
  });
  check(zhLabel === '"要点"', `zh .reader-keypoints::before is ${zhLabel}`);
  await page.screenshot({ path: `${SHOTS}distill_zh.png` });
} catch (e) {
  fail(`unexpected error: ${e.stack || e}`);
} finally {
  await browser.close();
}

for (const p of problems) fail(p);
if (failures) { console.error(`${failures} failure(s)`); process.exit(1); }
console.log('Distill e2e passed');
