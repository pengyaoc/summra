// The Iliad (book 66) in Side by Side: every original paragraph has its
// Plain English beside it, and the reader shows paired rows without gaps.
//
// Its Plain English was written by Haiku subagents and checked by Sonnet
// subagents (docs/agent_plain_english_workflow.md), one paragraph per
// original paragraph. Before that the book had no Plain English, so Side by
// Side was unavailable.
//
// Run: node iliad_side_by_side.mjs   (Flask on :5001)

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const BOOK_ID = 66;
let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

// 1. API: walk every side-by-side segment.
const manifest = (await (await fetch(`${BASE}/api/reader/books/${BOOK_ID}/manifest`)).json()).manifest;
const sxs = manifest.modes.find((m) => m.mode === 'side_by_side');
expect('side by side is available', sxs?.availability === 'available', JSON.stringify(sxs));
const original = manifest.modes.find((m) => m.mode === 'original');
expect('one side-by-side row per original paragraph', sxs?.unit_count === original?.unit_count,
  `${sxs?.unit_count} vs ${original?.unit_count}`);

const units = [];
for (let id = sxs?.first_segment_id; id; ) {
  const seg = (await (await fetch(`${BASE}/api/reader/books/${BOOK_ID}/segments/${id}?mode=side_by_side`)).json()).segment;
  units.push(...seg.units);
  id = seg.next_segment_id;
}
expect('all segments load', units.length === sxs?.unit_count, `${units.length} units`);
const unpaired = units.filter((u) => !(u.members.original?.available && u.members.original.content?.trim()
  && u.members.plain?.available && u.members.plain.content?.trim()));
expect('every row has both an original and a Plain English paragraph', unpaired.length === 0,
  unpaired.slice(0, 3).map((u) => u.id).join(', '));
const bookOne = units.filter((u) => u.chapter_number === 1);
expect('Book I opens with its ARGUMENT heading on both sides',
  bookOne[0]?.members.original.content === 'ARGUMENT.' && bookOne[0]?.members.plain.content === 'ARGUMENT.');
expect('Book I first lines pair (Achilles’ wrath)',
  /^Achilles’ wrath/.test(bookOne[3]?.members.original.content || '')
  && /Achilles’ anger/.test(bookOne[3]?.members.plain.content || ''));
const last = units[units.length - 1];
expect('the book ends on END OF THE ILIAD on both sides',
  last?.members.original.content === 'END OF THE ILIAD' && last?.members.plain.content === 'END OF THE ILIAD');
expect('no editor footnotes or illustration tags left in the original',
  !units.some((u) => /\[\d+\]|\[Illustration/.test(u.members.original.content)));

// 2. Browser: Book I in Side by Side.
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
await ctx.addInitScript(() => { try { localStorage.removeItem('readingSettings'); } catch (_) {} });
const page = await ctx.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

await page.goto(`${BASE}/books/the-iliad/read?mode=side_by_side&chapter=${bookOne[0]?.chapter_id}`, { waitUntil: 'networkidle' });
await page.waitForFunction(() => window.summraApp?.continuousReader?.mode === 'side_by_side'
  && document.querySelector('.pagination-page-container .side-by-side-row'));
await page.waitForTimeout(300);

const view = await page.evaluate(() => {
  const pc = document.querySelector('.pagination-page-container');
  const rows = [...pc.querySelectorAll('.side-by-side-row')];
  return {
    rows: rows.length,
    empty: rows.filter((r) => !r.querySelector('.original')?.textContent.trim()
      || !r.querySelector('.modern')?.textContent.trim()).length,
    gaps: pc.querySelectorAll('.reader-gap').length,
    overflow: pc.scrollHeight - pc.clientHeight,
    // Each chapter starts a page, with its heading first (reader_chapter_starts_page.mjs).
    heading: pc.querySelector('.reader-chapter-heading, [data-reader-anchor]')?.textContent.trim(),
    first: (() => { const r = pc.querySelector('.side-by-side-row');
      return r && { anchor: r.dataset.readerAnchor, original: r.querySelector('.original')?.textContent.trim(),
        plain: r.querySelector('.modern')?.textContent.trim() }; })(),
  };
});
expect('page shows paired rows', view.rows >= 2, `${view.rows} rows`);
expect('no row is missing a side', view.empty === 0, `${view.empty} empty`);
expect('no "unavailable" gaps', view.gaps === 0);
expect('page does not overflow', view.overflow <= 1, `${view.overflow}px`);
expect('opens at Book I: its heading, then a row pairing ARGUMENT. with ARGUMENT.',
  view.heading === 'Book I' && view.first?.anchor === bookOne[0]?.id
  && view.first.original === 'ARGUMENT.' && view.first.plain === 'ARGUMENT.',
  JSON.stringify({ heading: view.heading, first: view.first }));
expect('no console errors', errors.length === 0, errors.join(' | '));

await browser.close();
process.exit(failed ? 1 : 0);
