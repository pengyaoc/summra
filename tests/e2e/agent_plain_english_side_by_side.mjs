// Books whose Plain English was written by subagents
// (docs/agent_plain_english_workflow.md) work in Side by Side: every
// original paragraph has its Plain English beside it, the cleanup left no
// footnote markers or image tags, and the reader opens a chapter on paired
// rows under its heading, with no gaps or overflow.
//
// Add a book: append an entry to BOOKS (first/last rows are sanity anchors).
// Run: node agent_plain_english_side_by_side.mjs   (Flask on :5001)
//      BOOKS=the-iliad node agent_plain_english_side_by_side.mjs

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const BOOKS = [
  {
    id: 61, slug: 'beyond-good-and-evil', chapter: 1,
    first: { original: /^1\. The Will to Truth/, plain: /^1\..*[Tt]ruth/ },
    pairs: [{ chapter: 4, index: 0, original: /^63\. He who is a thorough teacher/, plain: /^63\..*teacher/ }],
    last: { original: /Light and Dark were one that wedding-morn\.$/, plain: /[Ll]ight.*[Dd]ark/ },
  },
  {
    id: 2, slug: 'the-origin-of-species', chapter: 11,
    first: { original: /^GEOGRAPHICAL DISTRIBUTION\.$/, plain: /^GEOGRAPHICAL DISTRIBUTION\.$/ },
    pairs: [{ chapter: 14, index: 49, original: /^It is interesting to contemplate an entangled bank/, plain: /bank|plants/ }],
    last: { original: /^Zebra, stripes on, 163\.$/, plain: /^Zebra, stripes on, 163\.$/ },
  },
  {
    id: 66, slug: 'the-iliad', chapter: 1,
    first: { original: /^ARGUMENT\.$/, plain: /^ARGUMENT\.$/ },
    pairs: [{ chapter: 1, index: 3, original: /^Achilles’ wrath/, plain: /Achilles’ anger/ }],
    last: { original: /^END OF THE ILIAD$/, plain: /^END OF THE ILIAD$/ },
  },
  {
    id: 105, slug: 'the-happy-prince-and-other-tales', chapter: 1,
    first: { original: /^HIGH above the city/, plain: /Happy Prince/ },
    pairs: [{ chapter: 3, index: 0, original: /^EVERY afternoon/, plain: /Giant/ }],
    last: { original: /gasped the Rocket, and he went out\.$/, plain: /Rocket/ },
  },
  {
    id: 3, slug: 'an-inquiry-into-the-nature-and-causes-of-the-wealth-of-nations', chapter: 1,
    first: { original: /^OF THE DIVISION OF LABOUR\.$/, plain: /^OF THE DIVISION OF LABOUR\.$/ },
    pairs: [{ chapter: 2, index: 2, original: /^Whether this propensity/, plain: /butcher, the brewer, or the baker/ }],
    last: { original: /mediocrity of her circumstances\.$/, plain: /modesty of her circumstances\.$/ },
  },
  {
    id: 112, slug: 'life-on-the-mississippi', chapter: 1,
    first: { original: /^THE Mississippi is well worth reading about/, plain: /^The Mississippi is well worth reading about/ },
    pairs: [{ chapter: 3, index: 0, original: /^APPARENTLY the river was ready for business/, plain: /river was ready for business/ }],
    last: { original: /descended into the depths below\.$/, plain: /depths below\.$/ },
  },
  {
    id: 62, slug: 'grimms-fairy-tales', chapter: 1,
    first: { original: /^A certain king had a beautiful garden/, plain: /^A certain king had a beautiful garden/ },
    pairs: [{ chapter: 61, index: 0, original: /^There was once a poor widow who lived in a lonely cottage/, plain: /^Once there was a poor widow who lived in a lonely cottage/ }],
    last: { original: /ever since\.$/, plain: /children’s reading ever since\.$/ },
  },
].filter((b) => !process.env.BOOKS || process.env.BOOKS.split(',').includes(b.slug));

let failed = false;
const expect = (label, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!cond) failed = true;
};

const browser = await chromium.launch({ headless: true });
for (const book of BOOKS) {
  const tag = `[${book.slug}]`;
  // 1. API: walk every side-by-side segment.
  const manifest = (await (await fetch(`${BASE}/api/reader/books/${book.id}/manifest`)).json()).manifest;
  const sxs = manifest.modes.find((m) => m.mode === 'side_by_side');
  const original = manifest.modes.find((m) => m.mode === 'original');
  expect(`${tag} side by side is available`, sxs?.availability === 'available', JSON.stringify(sxs));
  expect(`${tag} one side-by-side row per original paragraph`, sxs?.unit_count === original?.unit_count,
    `${sxs?.unit_count} vs ${original?.unit_count}`);

  const units = [];
  for (let id = sxs?.first_segment_id; id; ) {
    const seg = (await (await fetch(`${BASE}/api/reader/books/${book.id}/segments/${id}?mode=side_by_side`)).json()).segment;
    units.push(...seg.units);
    id = seg.next_segment_id;
  }
  expect(`${tag} all segments load`, units.length === sxs?.unit_count, `${units.length} units`);
  const unpaired = units.filter((u) => !(u.members.original?.available && u.members.original.content?.trim()
    && u.members.plain?.available && u.members.plain.content?.trim()));
  expect(`${tag} every row has both an original and a Plain English paragraph`, unpaired.length === 0,
    unpaired.slice(0, 3).map((u) => u.id).join(', '));
  expect(`${tag} no footnote markers or image tags left in the original`,
    !units.some((u) => /\[\d+\]|\[Illustration\b|\[Picture/.test(u.members.original.content)));
  const inChapter = (n) => units.filter((u) => u.chapter_number === n);
  const opening = inChapter(book.chapter);
  const matches = (unit, want) => unit && want.original.test(unit.members.original.content)
    && want.plain.test(unit.members.plain.content);
  expect(`${tag} chapter ${book.chapter} opens with the expected pair`, matches(opening[0], book.first),
    JSON.stringify(opening[0]?.members && [opening[0].members.original.content.slice(0, 60), opening[0].members.plain.content.slice(0, 60)]));
  for (const pair of book.pairs || []) {
    expect(`${tag} chapter ${pair.chapter} paragraph ${pair.index + 1} pairs`, matches(inChapter(pair.chapter)[pair.index], pair));
  }
  expect(`${tag} the book ends with the expected pair`, matches(units[units.length - 1], book.last));

  // 2. Browser: open the chapter in Side by Side.
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
  await ctx.addInitScript(() => { try { localStorage.removeItem('readingSettings'); } catch (_) {} });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(`${BASE}/books/${book.slug}/read?mode=side_by_side&chapter=${opening[0]?.chapter_id}`, { waitUntil: 'networkidle' });
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
      // Each chapter starts a page, heading first (reader_chapter_starts_page.mjs).
      heading: pc.querySelector('.reader-chapter-heading, [data-reader-anchor]')?.textContent.trim(),
      firstAnchor: rows[0]?.dataset.readerAnchor,
    };
  });
  const title = manifest.structure.find((e) => e.kind === 'chapter' && Number(e.chapter_id) === Number(opening[0]?.chapter_id))?.title;
  expect(`${tag} page shows paired rows`, view.rows >= 1 && view.empty === 0, JSON.stringify(view));
  expect(`${tag} no "unavailable" gaps`, view.gaps === 0);
  expect(`${tag} page does not overflow`, view.overflow <= 1, `${view.overflow}px`);
  expect(`${tag} opens under the chapter heading at its first row`,
    view.heading === title && view.firstAnchor === opening[0]?.id, JSON.stringify({ heading: view.heading, title, first: view.firstAnchor }));
  expect(`${tag} no console errors`, errors.length === 0, errors.join(' | '));
  await ctx.close();
}
expect('at least one book checked', BOOKS.length > 0);
await browser.close();
process.exit(failed ? 1 : 0);
