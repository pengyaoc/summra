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
// Books that hold real keypoints blocks (the two above have none); the label check falls back to an
// injected element, and says so, if a book has none.
const KEYPOINTS_SLUG = process.env.DISTILL_KEYPOINTS_SLUG || 'numbers-dont-lie';
const KEYPOINTS_ZH_SLUG = process.env.DISTILL_KEYPOINTS_ZH_SLUG || 'why-nations-fail';
const SHOTS = new URL('./screenshots/', import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

let failures = 0;
const fail = (msg) => { failures++; console.error(`FAIL: ${msg}`); };
const check = (ok, msg) => { if (!ok) fail(msg); else console.log(`ok   ${msg}`); };

const browser = await chromium.launch({ headless: !process.env.HEADED });
const problems = [];
async function newPage(options) {
  const context = await browser.newContext(options);
  const pg = await context.newPage();
  pg.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  pg.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
  pg.on('requestfailed', (r) => {
    if (r.url().startsWith(BASE)) problems.push(`request failed: ${r.url()} ${r.failure()?.errorText}`);
  });
  pg.on('response', (r) => {
    if (r.url().startsWith(BASE) && r.status() >= 400) problems.push(`HTTP ${r.status()}: ${r.url()} (page ${pg.url()})`);
  });
  return pg;
}
const page = await newPage({ viewport: { width: 1280, height: 900 } });

const anchorsReady = (pg = page) => pg.waitForSelector('#continuous-reader-content [data-reader-anchor]', { timeout: 15000 });

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
const inspectPage = (pg = page) => pg.evaluate(() => {
  const wrapper = document.querySelector('.pagination-wrapper');
  const pageBottom = wrapper ? wrapper.getBoundingClientRect().bottom : innerHeight;
  const overflowing = [];
  for (const el of document.querySelectorAll('#continuous-reader-content [data-reader-anchor]')) {
    const r = el.getBoundingClientRect();
    if (r.height === 0 || getComputedStyle(el).display === 'none') continue;
    // The block's own box must fit the page. A table or list may be taller inside than its box
    // (it scrolls), but only if it really scrolls; a clipped block must not pass.
    if (r.bottom > pageBottom + 1) {
      overflowing.push(`${el.tagName}.${el.className} bottom=${Math.round(r.bottom)} page=${Math.round(pageBottom)}`);
    } else if (el.matches('table.reader-table, .reader-list, .reader-keypoints') && el.scrollHeight > el.clientHeight + 1
      && !['auto', 'scroll'].includes(getComputedStyle(el).overflowY)) {
      overflowing.push(`${el.tagName}.${el.className} clipped, not scrollable (${el.scrollHeight} > ${el.clientHeight})`);
    }
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
    hasScrollingList: [...document.querySelectorAll('#continuous-reader-content .reader-list, #continuous-reader-content .reader-keypoints')]
      .some((e) => e.scrollHeight > e.clientHeight + 1),
  };
});

// Fetch every unit of a book and record which chapters hold which block types. Runs in the page.
const scanBlocks = (pg) => pg.evaluate(async () => {
  const id = window.DISTILL_BOOK.id;
  const api = withBasePath(window.READER_CONFIG.api_base);
  const manifest = (await (await fetch(`${api}/reader/books/${id}/manifest`)).json()).manifest;
  const kinds = new Map();
  for (const segment of manifest.segments) {
    const data = (await (await fetch(`${api}/reader/books/${id}/segments/${segment.id}?mode=summary`)).json()).segment;
    for (const unit of data.units) {
      const type = JSON.parse(unit.content).type;
      if (!kinds.has(unit.chapter_id)) kinds.set(unit.chapter_id, new Set());
      kinds.get(unit.chapter_id).add(type);
    }
  }
  return [...kinds].map(([chapter, types]) => ({ chapter, types: [...types] }));
});

// Page through a chapter with ArrowRight, inspecting every page. Stops once an image and a table
// have both been seen and at least `minPages` pages were walked.
async function walkChapter(pg, chapter, minPages, shotPrefix) {
  await pg.goto(`${BASE}/books/${SLUG}/read?chapter=${chapter}`, { waitUntil: 'networkidle' });
  await anchorsReady(pg);
  const seen = { image: false, table: false, scrollingList: false, imageBroken: false, pages: 0, overflow: [], merged: [] };
  for (let i = 0; i < 150 && (!(seen.image && seen.table) || i < minPages); i++, seen.pages++) {
    const info = await inspectPage(pg);
    seen.overflow.push(...info.overflowing);
    seen.merged.push(...info.merged);
    if (info.imageOk !== null) {
      if (!seen.image) await pg.screenshot({ path: `${SHOTS}${shotPrefix}_figure.png` });
      seen.image = true;
      if (!info.imageOk) seen.imageBroken = true;
    }
    if (info.hasTable && !seen.table) { seen.table = true; await pg.screenshot({ path: `${SHOTS}${shotPrefix}_table.png` }); }
    if (info.hasScrollingList && !seen.scrollingList) { seen.scrollingList = true; await pg.screenshot({ path: `${SHOTS}${shotPrefix}_list.png` }); }
    await pg.keyboard.press('ArrowRight');
    await pg.waitForTimeout(120);
  }
  return seen;
}

// The ::before label of a real rendered keypoints block, found by paging to one; null if the
// book has none. `chapters` come from scanBlocks.
async function realKeypointsLabel(pg, slug, chapters) {
  const target = chapters.find((c) => c.types.includes('keypoints'));
  if (!target) return null;
  await pg.goto(`${BASE}/books/${slug}/read?chapter=${target.chapter}`, { waitUntil: 'networkidle' });
  await anchorsReady(pg);
  for (let i = 0; i < 120; i++) {
    const content = await pg.evaluate(() => {
      const el = [...document.querySelectorAll('#continuous-reader-content .reader-keypoints')]
        .find((e) => e.getBoundingClientRect().height > 0);
      return el ? getComputedStyle(el, '::before').content : null;
    });
    if (content) return content;
    await pg.keyboard.press('ArrowRight');
    await pg.waitForTimeout(100);
  }
  return null;
}
const syntheticKeypointsLabel = (pg) => pg.evaluate(() => {
  const ul = document.createElement('ul');
  ul.className = 'reader-keypoints';
  document.body.appendChild(ul);
  const content = getComputedStyle(ul, '::before').content;
  ul.remove();
  return content;
});
async function keypointsLabel(pg, slug) {
  await pg.goto(`${BASE}/books/${slug}/read`, { waitUntil: 'networkidle' });
  await anchorsReady(pg);
  const real = await realKeypointsLabel(pg, slug, await scanBlocks(pg));
  if (real) { console.log(`     (${slug}: label read from a real keypoints block)`); return real; }
  console.log(`     (${slug}: no keypoints block in the book, using an injected element)`);
  return syntheticKeypointsLabel(pg);
}

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
  const found = await scanBlocks(page);
  const both = found.find((c) => c.types.includes('image') && c.types.includes('table'));
  check(!!both, `a chapter with an image and a table exists (chapter ${both?.chapter})`);

  if (both) {
    // Desktop, then a small phone (375x667), where lists taller than a page used to be clipped.
    for (const [name, options, minPages] of [
      ['desktop', { viewport: { width: 1280, height: 900 } }, 20],
      ['mobile', { viewport: { width: 375, height: 667 }, isMobile: true, hasTouch: true }, 60],
    ]) {
      // Leave the desktop reader first: two live sessions on one book legitimately conflict (409).
      if (name === 'mobile') await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
      const pg = name === 'desktop' ? page : await newPage(options);
      const seen = await walkChapter(pg, both.chapter, minPages, name === 'desktop' ? 'distill' : 'distill_mobile');
      check(seen.image && !seen.imageBroken, `${name}: figure images load (naturalWidth > 0)`);
      check(seen.image && seen.table, `${name}: paged through ${seen.pages} pages to an image and a table`);
      check(seen.overflow.length === 0, `${name}: no anchored block overflows its page${seen.overflow.length ? ': ' + [...new Set(seen.overflow)].slice(0, 3).join('; ') : ''}`);
      check(seen.merged.length === 0, `${name}: list items and table cells keep separating whitespace${seen.merged.length ? ': ' + seen.merged.slice(0, 3).join('; ') : ''}`);
      if (name === 'mobile') await pg.screenshot({ path: `${SHOTS}distill_mobile_reader.png` });
    }
  }

  // --- Key points label comes from CSS, per language ----------------------
  const label = await keypointsLabel(page, KEYPOINTS_SLUG);
  check(label === '"Key points"', `.reader-keypoints::before is ${label}`);

  // --- A reload restores the same place -----------------------------------
  // Deliberately navigates to /read with no ?chapter instead of page.reload(): a reload of
  // ?chapter=X would legitimately reopen chapter X's start, so only a saved place can explain a match.
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
  await page.screenshot({ path: `${SHOTS}distill_zh.png` });
  const zhLabel = await keypointsLabel(page, KEYPOINTS_ZH_SLUG);
  check(zhLabel === '"要点"', `zh .reader-keypoints::before is ${zhLabel}`);
} catch (e) {
  fail(`unexpected error: ${e.stack || e}`);
} finally {
  await browser.close();
}

for (const p of problems) fail(p);
if (failures) { console.error(`${failures} failure(s)`); process.exit(1); }
console.log('Distill e2e passed');
