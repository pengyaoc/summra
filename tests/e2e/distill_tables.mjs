// Distill reader tables on a phone: a grid table taller or wider than a page
// is split across pages by rows, never shown as a scrollable box.
//
// A nested scroller swallowed the swipe on mobile web, so the reader could not
// turn past a tall table. This walks two tables of the NVIDIA research report
// at 375x667: the longest table of at most 6 columns (the 15-row risk table)
// and the widest one (the 10-column, 17-row comps table).
//
//   DISTILL_USER_DB=$TMPDIR/distill_user_e2e.db PORT=5003 venv/bin/python -m distill.app
//   cd tests/e2e && node distill_tables.mjs
//
// Exits 1 on any FAIL or console error.

import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const SLUG = process.env.DISTILL_TABLE_SLUG || 'nvidia-equity-research-2026-10-31';
const SHOTS = new URL('./screenshots/', import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };

const browser = await chromium.launch({ headless: !process.env.HEADED });
const context = await browser.newContext({ viewport: { width: 375, height: 667 }, isMobile: true, hasTouch: true });
const page = await context.newPage();
const problems = [];
page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
page.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
const cdp = await context.newCDPSession(page);

// Grid tables in the book, read from the API: chapter, header and row count.
const gridTables = () => page.evaluate(async () => {
  const id = JSON.parse(document.getElementById('page-root').dataset.book).id;
  const api = withBasePath(window.READER_CONFIG.api_base);
  const manifest = (await (await fetch(`${api}/reader/books/${id}/manifest`)).json()).manifest;
  const tables = [];
  for (const segment of manifest.segments) {
    const data = (await (await fetch(`${api}/reader/books/${id}/segments/${segment.id}?mode=summary`)).json()).segment;
    for (const unit of data.units) {
      const block = JSON.parse(unit.content);
      if (block.type === 'table' && block.presentation === 'grid') {
        tables.push({ chapter: unit.chapter_id, header: block.header || [], rows: (block.rows || []).length, first: block.rows?.[0]?.[0] || '' });
      }
    }
  }
  return tables;
});

// What the current page shows of the reader content.
const inspect = () => page.evaluate(() => {
  const root = document.querySelector('#continuous-reader-content');
  const wrapper = document.querySelector('.pagination-wrapper');
  const box = wrapper.getBoundingClientRect();
  const visible = (el) => { const r = el.getBoundingClientRect(); return r.height > 0 && r.right > 0 && r.left < innerWidth; };
  // Any element inside the reader page that can scroll, whether or not its
  // content overflows it now: a scroll box captures the touch either way.
  const scrollers = [...root.querySelectorAll('*')].filter((el) => {
    const css = getComputedStyle(el);
    return ['auto', 'scroll'].includes(css.overflowX) || ['auto', 'scroll'].includes(css.overflowY);
  }).map((el) => `${el.tagName}.${el.className}`);
  const tables = [...root.querySelectorAll('table')].filter(visible).map((t) => {
    const r = t.getBoundingClientRect();
    return {
      header: [...t.querySelectorAll('thead th')].map((th) => th.textContent.trim()),
      rows: [...t.querySelectorAll('tbody tr')].map((tr) => tr.firstElementChild?.textContent.trim() ?? ''),
      rowsBelowPage: [...t.querySelectorAll('tr')].filter((tr) => tr.getBoundingClientRect().bottom > box.bottom + 1).length,
      tooWide: r.right > box.right + 1 || r.left < box.left - 1 || t.scrollWidth > t.clientWidth + 1,
    };
  });
  // A continuation page starts with the same table anchor and header, so
  // compare the whole page's text to tell pages apart.
  const live = [...root.querySelectorAll('.pagination-page-container')].find(visible);
  return { scrollers, tables, at: live ? live.textContent : null };
});

const swipeLeftOnTable = async () => {
  const target = await page.evaluate(() => {
    const t = [...document.querySelectorAll('#continuous-reader-content table')].find((el) => el.getBoundingClientRect().height > 0);
    if (!t) return null;
    const r = t.getBoundingClientRect();
    return { x: Math.min(innerWidth - 40, r.left + r.width * 0.8), y: r.top + Math.min(r.height / 2, 120) };
  });
  if (!target) return false;
  const touch = (type, x) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y: target.y }] });
  await touch('touchStart', target.x);
  for (let i = 1; i <= 8; i++) { await touch('touchMove', target.x - 30 * i); await page.waitForTimeout(25); }
  await touch('touchEnd', target.x - 240);
  await page.waitForTimeout(700);
  return true;
};

await page.goto(`${BASE}/books/${SLUG}/read`, { waitUntil: 'networkidle' });
await page.waitForSelector('#continuous-reader-content [data-reader-anchor]', { timeout: 15000 });
const all = await gridTables();
const wide = all.reduce((a, b) => (b.header.length > a.header.length ? b : a), all[0]);
const tall = all.filter((t) => t !== wide && t.header.length <= 6).reduce((a, b) => (!a || b.rows > a.rows ? b : a), null);
check(tall && tall.rows >= 15, `the book has a tall grid table (${tall?.rows} rows, chapter ${tall?.chapter})`);
check(wide && wide.header.length >= 8, `the book has a wide grid table (${wide?.header.length} columns, chapter ${wide?.chapter})`);

for (const [name, table] of [['tall', tall], ['wide', wide]]) {
  if (!table) continue;
  await page.goto(`${BASE}/books/${SLUG}/read?chapter=${table.chapter}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#continuous-reader-content [data-reader-anchor]', { timeout: 15000 });
  await page.waitForTimeout(400);
  const scrollers = new Set();
  const seenRows = new Set();
  let pagesWithTable = 0, headerMissing = 0, rowsBelow = 0, tooWide = 0, swiped = null, shot = false;
  for (let i = 0; i < 80; i++) {
    const info = await inspect();
    info.scrollers.forEach((s) => scrollers.add(s));
    const ours = info.tables.filter((t) => t.header.join('|') === table.header.join('|') || t.rows.includes(table.first));
    for (const t of ours) {
      pagesWithTable++;
      t.rows.forEach((r) => seenRows.add(r));
      if (t.header.join('|') !== table.header.join('|')) headerMissing++;
      rowsBelow += t.rowsBelowPage;
      if (t.tooWide) tooWide++;
    }
    if (ours.length && !shot) { shot = true; await page.screenshot({ path: `${SHOTS}distill_table_${name}.png` }); }
    if (ours.length && swiped === null) {
      // Swipe left starting on the table itself: the page must turn.
      await swipeLeftOnTable();
      const after = await inspect();
      swiped = after.at !== info.at;
      continue;
    }
    if (pagesWithTable && !ours.length) break; // walked past the table
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(150);
  }
  check(scrollers.size === 0, `${name}: no scrollable element inside the reader page${scrollers.size ? ': ' + [...scrollers].slice(0, 4).join('; ') : ''}`);
  check(swiped === true, `${name}: a swipe that starts on the table turns the page`);
  check(pagesWithTable >= (name === 'tall' ? 2 : 1), `${name}: table seen on ${pagesWithTable} page(s)`);
  check(seenRows.size === table.rows, `${name}: every row is reachable by turning pages (${seenRows.size}/${table.rows})`);
  check(rowsBelow === 0, `${name}: no table row is cut off below the page (${rowsBelow})`);
  check(headerMissing === 0, `${name}: the header row repeats on each continuation page (${headerMissing} without)`);
  check(tooWide === 0, `${name}: the table fits the page width (${tooWide} pages too wide)`);
}

check(problems.length === 0, `no console errors${problems.length ? ': ' + problems.slice(0, 3).join('; ') : ''}`);
await browser.close();
console.log(failures ? `\n${failures} FAIL` : '\nall passed');
process.exit(failures ? 1 : 0);
