// Every chapter starts on a new page, and Side by Side shows chapter headings.
//
// Bugs this guards against:
//  1. Pagination packed chapters back to back, so the page holding chapter
//     N's heading usually began with the end of chapter N-1. The reading
//     position is the page's first paragraph, so opening chapter N recorded a
//     place in chapter N-1: the title bar named the previous chapter, and
//     switching to Side by Side landed on the end of the previous chapter.
//  2. Side by Side paginated only rows and illustrations, so chapter headings
//     were dropped in every book.
//
// Run: node reader_chapter_starts_page.mjs   (Flask on :5001)

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
await ctx.addInitScript(() => { try { localStorage.removeItem('readingSettings'); } catch (_) {} });
const page = await ctx.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

// What the current page starts with, and what the chrome says.
const pageState = () => page.evaluate(() => {
  const pc = document.querySelector('.pagination-page-container');
  const first = pc?.querySelector('.reader-chapter-heading, [data-reader-anchor]');
  return {
    mode: window.summraApp.continuousReader.mode,
    title: document.getElementById('reader-chapter-title')?.textContent.trim(),
    firstIsHeading: !!first?.classList.contains('reader-chapter-heading'),
    firstText: first?.textContent.trim().slice(0, 40),
    headings: [...(pc?.querySelectorAll('.reader-chapter-heading') || [])].map((h) => h.textContent.trim()),
    marker: window.summraApp.continuousReader.currentMarker?.paragraph_id,
    firstRowAnchor: pc?.querySelector('.side-by-side-row')?.dataset.readerAnchor,
  };
});
const settle = async (cond) => {
  await page.waitForFunction(cond);
  await page.waitForTimeout(400);
};

for (const [slug, number, title] of [['the-iliad', 2, 'Book II'], ['a-journey-to-the-centre-of-the-earth', 20, null]]) {
  await page.goto(`${BASE}/books/${slug}/chapters/${number}`, { waitUntil: 'networkidle' });
  await settle(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
  const s = await pageState();
  expect(`${slug} ch.${number}: page starts with the chapter heading`, s.firstIsHeading, JSON.stringify(s));
  expect(`${slug} ch.${number}: title bar names the opened chapter`, s.title === s.headings[0] && (!title || s.title === title), JSON.stringify(s));
}

// Plain English at Book I, then switch to Side by Side: stays at Book I.
await page.goto(`${BASE}/books/the-iliad/chapters/1`, { waitUntil: 'networkidle' });
await settle(() => document.querySelector('.pagination-page-container [data-reader-anchor]'));
await page.click('#reader-settings-button');
await page.waitForSelector('#reading-settings-panel:not(.hidden)');
await page.click('[data-reader-settings-mode="side_by_side"]');
await settle(() => window.summraApp.continuousReader.mode === 'side_by_side'
  && document.querySelector('.pagination-page-container .side-by-side-row'));
const sxs = await pageState();
expect('switch to Side by Side at Book I: page shows the Book I heading', sxs.headings.includes('Book I'), JSON.stringify(sxs));
expect('switch to Side by Side at Book I: first row is Book I\'s first paragraph', /^\d+\.0$/.test(sxs.firstRowAnchor || ''), JSON.stringify(sxs));
expect('switch to Side by Side at Book I: title bar says Book I', sxs.title === 'Book I', JSON.stringify(sxs));

// Side by Side opened directly at a chapter shows its heading first.
await page.goto(`${BASE}/books/frankenstein/read?mode=side_by_side`, { waitUntil: 'networkidle' });
await settle(() => document.querySelector('.pagination-page-container .side-by-side-row'));
const fr = await pageState();
expect('Side by Side shows the chapter heading (Frankenstein, first page)', fr.firstIsHeading && fr.headings.length === 1, JSON.stringify(fr));

// Turning pages forward across a chapter end: the next chapter starts a page.
// Start at the Iliad's shortest Book (XIX) and page into Book XX.
const manifest = (await (await fetch(`${BASE}/api/reader/books/66/manifest`)).json()).manifest;
const bookXIX = manifest.structure.find((e) => e.kind === 'chapter' && Number(e.chapter_number) === 19);
await page.goto(`${BASE}/books/the-iliad/read?mode=side_by_side&chapter=${bookXIX?.chapter_id}`, { waitUntil: 'networkidle' });
await settle(() => document.querySelector('.pagination-page-container .side-by-side-row'));
let crossed = null;
for (let i = 0; i < 80 && !crossed; i++) {
  const before = await pageState();
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(250);
  const after = await pageState();
  if (after.headings.length && after.title !== 'Book XIX') crossed = { before: before.title, after };
}
expect('paging into a new chapter: its heading is the first thing on the page',
  crossed && crossed.after.firstIsHeading && crossed.after.title === crossed.after.headings[0], JSON.stringify(crossed));

expect('no console errors', errors.length === 0, errors.join(' | '));
await browser.close();
process.exit(failed ? 1 : 0);
