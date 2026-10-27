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

// An installed app must render its sign-in entry without an account cookie.
// Simulate the gateway's expired session, then use the local authenticated login.
await page.route('**/api/auth/check', route => route.fulfill({status: 200, contentType: 'application/json', body: '{"authenticated":false}'}));
await page.goto(`${BASE}/launch`);
check(await page.locator('a', {hasText: 'Sign in'}).isVisible(), 'PWA launch offers sign-in with an expired session');
check(await page.locator('link[rel="stylesheet"],script[src]').count() === 0, 'signed-out launch requires no private assets');
await page.unroute('**/api/auth/check');
await page.locator('a', {hasText: 'Sign in'}).click();
await page.waitForURL(`${BASE}/`);
check(new URL(page.url()).pathname === '/', 'sign-in returns to the library');
await page.goto(`${BASE}/launch`);
await page.waitForURL(`${BASE}/`);
check(new URL(page.url()).pathname === '/', 'PWA launch resumes an authenticated session');

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
    if (r.bottom > pageBottom + 1) {
      overflowing.push(`${el.tagName}.${el.className} bottom=${Math.round(r.bottom)} page=${Math.round(pageBottom)}`);
    }
  }
  const nestedScrollers = [...document.querySelectorAll('#continuous-reader-content .pagination-page-container *')]
    .filter(el => {
      const css = getComputedStyle(el);
      return (el.scrollHeight > el.clientHeight + 1 && ['auto', 'scroll'].includes(css.overflowY))
        || (el.scrollWidth > el.clientWidth + 1 && ['auto', 'scroll'].includes(css.overflowX));
    }).map(el => `${el.tagName}.${el.className}`);
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
    overflowing, merged, nestedScrollers,
    imageOk: img ? img.complete && img.naturalWidth > 0 : null,
    hasTable: !!document.querySelector('#continuous-reader-content .reader-flow-table-cell'),
    hasList: !!document.querySelector('#continuous-reader-content .reader-flow-item'),
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
  const seen = { image: false, table: false, list: false, nestedScrollers: [], imageBroken: false, pages: 0, overflow: [], merged: [] };
  for (let i = 0; i < 150 && (!(seen.image && seen.table) || i < minPages); i++, seen.pages++) {
    const info = await inspectPage(pg);
    seen.overflow.push(...info.overflowing);
    seen.nestedScrollers.push(...info.nestedScrollers);
    seen.merged.push(...info.merged);
    if (info.imageOk !== null) {
      if (!seen.image) await pg.screenshot({ path: `${SHOTS}${shotPrefix}_figure.png` });
      seen.image = true;
      if (!info.imageOk) seen.imageBroken = true;
    }
    if (info.hasTable && !seen.table) { seen.table = true; await pg.screenshot({ path: `${SHOTS}${shotPrefix}_table.png` }); }
    if (info.hasList && !seen.list) { seen.list = true; await pg.screenshot({ path: `${SHOTS}${shotPrefix}_list.png` }); }
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
      const el = [...document.querySelectorAll('#continuous-reader-content .reader-flow-keypoints-label')]
        .find((e) => e.getBoundingClientRect().height > 0);
      return el ? JSON.stringify(el.textContent) : null;
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
  check(await page.locator('.distill-tile .distill-cover').count() === await page.locator('.distill-tile').count(), 'every book has a cover image or placeholder');
  await page.screenshot({ path: `${SHOTS}distill_library.png`, fullPage: false });

  await page.click(`a.distill-tile[href*="/books/${SLUG}?"]`);
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
  await page.click('#reader-toc-button');
  check(await page.locator('.reader-toc-part').count() > 0, 'reader TOC preserves part headings');
  check(await page.locator('#reader-toc-list [aria-current="location"]').count() === 1, 'reader TOC marks the current chapter');
  check(await page.evaluate(() => document.getElementById('reader-toc-panel').contains(document.activeElement)), 'opening Contents transfers focus');
  await page.keyboard.press('Escape');
  check(!(await page.locator('#reader-toc-panel').isVisible()), 'Escape closes Contents');
  check(await page.evaluate(() => document.activeElement.id === 'reader-toc-button'), 'closing Contents restores focus');


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
      check(seen.nestedScrollers.length === 0, `${name}: no nested scrollable reading components`);
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
  check(await page.locator(`.library-card a.library-read-action[href*="/books/${SLUG}/read?"]`).count() === 1, 'library lists the book under Reading now');
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
  // Both apps use this same platform. A no-space Chinese paragraph must fill
  // the preceding page and continue, retaining formatting, anchors and place.
  const chineseSplit = await page.evaluate(async () => {
    const {applyReaderPlatform} = await import('/static/shared/js/platform.js');
    class Fixture {}
    applyReaderPlatform(Fixture);
    const app = new Fixture();
    app.initReaderPlatform();
    app.continuousReader = {active: true, mode: 'summary', unitsById: new Map([
      ['1.0', {word_count: 1}], ['1.1', {word_count: 1}],
    ])};
    const container = document.createElement('div');
    container.className = 'continuous-reader-content';
    container.style.cssText = 'position:absolute;left:-9999px;width:335px';
    const short = '本章以鲁道夫菲尔绍的生平开篇。'.repeat(3);
    const long = '细胞是生命的基本单位，研究者用显微镜发现了隐形的世界。'.repeat(100);
    container.innerHTML = `<p data-reader-anchor="1.0" data-reader-word-count="1">${short}</p><p data-reader-anchor="1.1" data-reader-word-count="1"><em>${long}</em>𠮷野家DNA</p>`;
    document.querySelector('#continuous-reader-section').appendChild(container);
    const style = getComputedStyle(container);
    const box = `width:${container.offsetWidth}px;padding:${style.padding};box-sizing:${style.boxSizing};font-size:${style.fontSize};line-height:${style.lineHeight}`;
    app.calculatePages(container);
    const overflows = [], texts = [], slacks = [], markers = [];
    let emphasis = true;
    for (const [index, html] of app.pagination.pages.entries()) {
      const el = document.createElement('div');
      el.className = 'pagination-page-container';
      el.style.cssText = `position:absolute;left:-9999px;${box};height:${app.pagination.containerHeight}px;overflow:hidden`;
      el.innerHTML = html;
      container.parentElement.appendChild(el);
      overflows.push(el.scrollHeight > app.pagination.containerHeight + 1);
      texts.push(el.textContent.replace(/\s/g, ''));
      const last = el.lastElementChild;
      slacks.push(el.getBoundingClientRect().bottom - last.getBoundingClientRect().bottom);
      const longFragment = el.querySelector('[data-reader-anchor="1.1"]');
      if (longFragment?.textContent.includes('细胞') && !longFragment.querySelector('em')) emphasis = false;
      app.pagination.currentPage = index;
      const anchor = el.querySelector('[data-reader-anchor]');
      const offset = app.continuousMarkerOffset(anchor);
      markers.push(app.findContinuousPageForMarker({paragraph_id: anchor.dataset.readerAnchor, offset}) === index);
      el.remove();
    }
    const first = app.pagination.pages[0];
    container.remove();
    return {pages: texts.length, allText: texts.join('') === short + long + '𠮷野家DNA',
      overflows, slacks, markers, emphasis, fillsFirst: first.includes('data-reader-anchor="1.1"')};
  });
  check(chineseSplit.pages > 2 && chineseSplit.fillsFirst, 'Chinese paragraph splits and starts in remaining page space');
  check(chineseSplit.allText && chineseSplit.emphasis, 'Chinese paragraph retains every character, inline markup and anchors');
  check(!chineseSplit.overflows.some(Boolean), 'Chinese continuation pages never clip content');
  check(chineseSplit.slacks.slice(0, -1).every(gap => gap < 90), 'Chinese continuation pages fill available height');
  check(chineseSplit.markers.every(Boolean), 'Chinese saved offsets restore each continuation page');

  await page.screenshot({ path: `${SHOTS}distill_zh.png` });
  const flatFlow = await page.evaluate(async () => {
    const {applyReaderPlatform} = await import('/static/shared/js/platform.js');
    class Fixture {classifyUnit(text) {return JSON.parse(text);}}
    applyReaderPlatform(Fixture);
    const app = new Fixture(); app.initReaderPlatform();
    app.continuousReader = {active: true, mode: 'summary', unitsById: new Map()};
    const words = (prefix, n) => Array.from({length:n}, (_, i) => `${prefix}${i}`).join(' ');
    const blocks = [
      {type:'ol', items:[words('L',500), 'Second item']},
      {type:'table', header:['Topic','Explanation'], rows:[['Cell',words('T',650)],['Energy','All preserved']]},
      {type:'keypoints', items:[words('K',450)]},
    ];
    const container = document.createElement('div'); container.className='continuous-reader-content';
    container.style.cssText='position:absolute;left:-9999px;width:335px';
    container.innerHTML=blocks.map((block,i)=>app.continuousReaderBlocks(JSON.stringify(block)).map(part=>
      `<${part.tag} class="${part.className}" data-reader-flow="true" data-reader-anchor="90.${i}" data-reader-word-count="1">${part.content}</${part.tag}>`).join('')).join('');
    const expected=container.textContent.replace(/\s/g,'');
    document.querySelector('#continuous-reader-section').appendChild(container);
    const cs=getComputedStyle(container);
    const box=`width:${container.offsetWidth}px;padding:${cs.padding};box-sizing:${cs.boxSizing};font-size:${cs.fontSize};line-height:${parseFloat(cs.lineHeight)/parseFloat(cs.fontSize)}`;
    app.calculatePages(container);
    let text='', overflow=false, scroll=false, restore=true;
    const details=[];
    const sources=new Set();
    for (const [index,html] of app.pagination.pages.entries()) {
      const el=document.createElement('div'); el.className='pagination-page-container';
      el.setAttribute('data-font',document.getElementById('continuous-reader-section').getAttribute('data-font'));
      el.style.cssText=`position:absolute;left:-9999px;${box};height:${app.pagination.containerHeight}px;overflow:hidden`;
      el.innerHTML=html; container.parentElement.appendChild(el);
      text+=el.textContent.replace(/\s/g,'');
      overflow ||= el.scrollHeight > app.pagination.containerHeight+1;
      if (el.scrollHeight > app.pagination.containerHeight+1) details.push({index,scroll:el.scrollHeight,height:app.pagination.containerHeight,font:getComputedStyle(el).fontFamily,line:getComputedStyle(el).lineHeight,last:el.lastElementChild?.outerHTML.slice(-300)});
      for (const child of el.querySelectorAll('*')) {
        const css=getComputedStyle(child);
        scroll ||= ['auto','scroll'].includes(css.overflowY) || ['auto','scroll'].includes(css.overflowX);
      }
      const anchor=el.querySelector('[data-reader-anchor]'); sources.add(anchor.dataset.readerAnchor);
      app.pagination.currentPage=index;
      restore &&= app.findContinuousPageForMarker({paragraph_id:anchor.dataset.readerAnchor,offset:app.continuousMarkerOffset(anchor)})===index;
      el.remove();
    }
    container.remove();
    return {pages:app.pagination.pages.length, exact:text===expected, overflow,scroll,restore,sources:sources.size,details};
  });
  check(flatFlow.pages > 5 && flatFlow.exact && flatFlow.sources === 3, 'long list items and table cells span pages with every word and source anchor preserved');
  check(!flatFlow.overflow && !flatFlow.scroll, `flat list/table/keypoint pages neither clip nor create nested scroll areas (${JSON.stringify(flatFlow)})`);
  check(flatFlow.restore, 'saved positions restore across all flattened-list and table pages');

  const zhLabel = await keypointsLabel(page, KEYPOINTS_ZH_SLUG);
  check(zhLabel === '"要点"', `zh .reader-keypoints::before is ${zhLabel}`);

  // --- Kindle e-ink mode (own context: a second live session on one book makes saves 409) -------
  const KINDLE_UA = 'Mozilla/5.0 (X11; U; Linux armv7l like Android; en-us) AppleWebKit/531.2+ '
    + '(KHTML, like Gecko) Version/5.0 Safari/533.2+ Kindle/3.0+';
  const kp = await newPage({ userAgent: KINDLE_UA, viewport: { width: 758, height: 950 } });
  await kp.goto(`${BASE}/`, { waitUntil: 'load' });
  check(await kp.locator('html.kindle').count() === 1, 'Kindle UA gets the Kindle library');
  check(await kp.locator('script[type="module"]').count() === 0, 'Kindle library loads no module script');
  check(await kp.locator('.list li a').count() > 0, 'Kindle library lists books');
  await kp.screenshot({ path: `${SHOTS}distill_kindle_library.png` });

  await kp.goto(`${BASE}/books/${SLUG}`, { waitUntil: 'load' });
  check(await kp.locator('html.kindle').count() === 1 && await kp.locator('.contents li a').count() > 0, 'Kindle contents are listed');
  check(await kp.locator('.contents li.part').count() > 0, 'Kindle contents have part headings');
  await kp.screenshot({ path: `${SHOTS}distill_kindle_book.png` });

  // The first chapter of the book with both a table and an image, found from the Kindle HTML itself.
  let target = null;
  for (let ch = 0; ch < 60 && !target; ch++) {
    const html = await kp.evaluate(async (u) => { const r = await fetch(u); return r.ok ? r.text() : ''; }, `${BASE}/books/${SLUG}/read?ch=${ch}`);
    if (!html) break;
    if (html.includes('<table') && html.includes('<figure')) target = ch;
  }
  check(target !== null, `a Kindle chapter with a table and an image exists (ch=${target})`);

  if (target !== null) {
    await kp.goto(`${BASE}/books/${SLUG}/read?ch=${target}`, { waitUntil: 'load' });
    check(await kp.locator('html.kindle').count() === 1 && await kp.locator('script[src*="kindle.js"]').count() === 1
      && await kp.locator('script[type="module"]').count() === 0, 'Kindle reader loads kindle.js and no module script');
    await kp.waitForFunction(() => /\S/.test(document.getElementById('right')?.textContent || ''), null, { timeout: 5000 });
    const right = () => kp.locator('#right').innerText();
    const flowLeft = () => kp.evaluate(() => document.getElementById('flow').style.left);
    check(await kp.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1), 'Kindle reader does not scroll');

    // Every table row and figure sits in one column (one page), on a fresh layout.
    const split = await kp.evaluate(() => {
      const flow = document.getElementById('flow').getBoundingClientRect();
      const step = document.getElementById('viewport').offsetWidth + 72;
      const bad = [];
      for (const el of document.querySelectorAll('#flow tr, #flow figure')) {
        const pagesTouched = new Set();
        for (const r of el.getClientRects()) {
          pagesTouched.add(Math.floor((r.left - flow.left + 2) / step));
          pagesTouched.add(Math.floor((r.right - flow.left - 2) / step));
        }
        if (pagesTouched.size > 1) bad.push(`${el.tagName} spans pages ${[...pagesTouched]}`);
      }
      return { bad, count: document.querySelectorAll('#flow tr, #flow figure').length };
    });
    check(split.count > 0 && split.bad.length === 0, `no tr or figure spans two columns (${split.count} checked; ${split.bad.join('; ')})`);
    const img = await kp.evaluate(() => [...document.querySelectorAll('#flow figure img')].map((i) => [i.complete, i.naturalWidth]));
    check(img.length > 0 && img.every(([done, w]) => done && w > 0), `Kindle figure images load (naturalWidth>0: ${JSON.stringify(img)})`);

    const before = [await right(), await flowLeft()];
    await kp.mouse.click(700, 475);
    await kp.waitForTimeout(150);
    check((await flowLeft()) !== before[1] && (await right()) !== before[0], `tap at x=700 turns the page (${before} -> ${await right()})`);
    await kp.screenshot({ path: `${SHOTS}distill_kindle_reader.png` });
    const table = await kp.evaluate(() => { const t = document.querySelector('#flow table'); return t ? t.getBoundingClientRect().left : null; });
    check(table !== null, 'Kindle reader renders the table');
  }
} catch (e) {
  fail(`unexpected error: ${e.stack || e}`);
} finally {
  await browser.close();
}

for (const p of problems) fail(p);
if (failures) { console.error(`${failures} failure(s)`); process.exit(1); }
console.log('Distill e2e passed');
