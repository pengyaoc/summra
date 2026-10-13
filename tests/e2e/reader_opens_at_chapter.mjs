// Chapter destinations open the reader on that chapter's first page.
//
// Bug this guards against: legacy /books/<slug>/chapters/<n> links,
// /read?chapter=<id> and table-of-contents jumps loaded the segment that
// contains the chapter but showed the segment's FIRST page — often a
// chapter or two earlier (chapter 20 opened on "The Wrong Road!").

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const SLUG = 'a-journey-to-the-centre-of-the-earth';
const CH20 = { id: '2663', title: 'Water, Where Is It?' };
const CH25 = { id: '2668', title: 'The Whispering Gallery' };
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };

const browser = await chromium.launch();

// Chapters continue across pages, so the page where chapter N starts may
// begin with the end of chapter N-1. "Opened at chapter N" therefore means:
// chapter N's heading is visible on the current page. (It is the FIRST such
// page because the reader only renders each heading once.)
const visibleHeading = (page, id) => page.evaluate((chapterId) => {
  const h = document.querySelector(`#continuous-reader-content .reader-chapter-heading[data-reader-chapter="${chapterId}"]`);
  if (!h) return null;
  const r = h.getBoundingClientRect();
  return r.height > 0 && r.bottom > 0 && r.top < innerHeight && getComputedStyle(h).display !== 'none' ? h.textContent.trim() : null;
}, id);
const firstVisible = (page) => page.evaluate(() => {
  const el = [...document.querySelectorAll('#continuous-reader-content .reader-chapter-heading, #continuous-reader-content [data-reader-anchor]')]
    .find((e) => { const r = e.getBoundingClientRect(); return r.height > 0 && r.bottom > 0 && r.top < innerHeight && getComputedStyle(e).display !== 'none'; });
  return el ? { chapter: el.dataset.readerChapter, text: el.textContent.trim().slice(0, 60) } : null;
});

async function openAndCheck(path, expected, viewport) {
  const ctx = await browser.newContext({ viewport });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#continuous-reader-content [data-reader-anchor]');
  const heading = await visibleHeading(page, expected.id);
  console.log(`${path} @${viewport.width}px -> heading on page: ${JSON.stringify(heading)}; page starts ${JSON.stringify(await firstVisible(page))}`);
  if (!heading?.startsWith(expected.title)) fail(`${path}: chapter ${expected.id} ("${expected.title}") heading not on the opened page`);
  if (errors.length) fail(`${path}: page errors: ${errors.join('; ')}`);
  return { ctx, page };
}

try {
  for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    await (await openAndCheck(`/books/${SLUG}/chapters/20`, CH20, viewport)).ctx.close();
    await (await openAndCheck(`/books/${SLUG}/read?chapter=${CH20.id}`, CH20, viewport)).ctx.close();
  }

  // Table of contents jump from inside the reader.
  const { ctx, page } = await openAndCheck(`/books/${SLUG}/chapters/20`, CH20, { width: 1280, height: 800 });
  await page.click('#reader-toc-button');
  await page.click(`[data-reader-chapter-target="${CH25.id}"]`);
  await page.waitForFunction((id) => document.querySelector(`#continuous-reader-content [data-reader-chapter="${id}"]`), CH25.id);
  await page.waitForTimeout(300);
  const tocHeading = await visibleHeading(page, CH25.id);
  console.log(`TOC -> heading on page: ${JSON.stringify(tocHeading)}`);
  if (!tocHeading?.startsWith(CH25.title)) fail(`TOC jump: chapter ${CH25.id} heading not on the opened page`);
  await ctx.close();

  // The TOC jump saved a reading position in chapter 25 (local dev signs
  // every browser in as the same user). Plain /read resumes that position...
  const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const p2 = await ctx2.newPage();
  await p2.goto(`${BASE}/books/${SLUG}/read`, { waitUntil: 'networkidle' });
  await p2.waitForSelector('#continuous-reader-content [data-reader-anchor]');
  const resumed = await firstVisible(p2);
  console.log(`/read (saved place) -> ${JSON.stringify(resumed)}`);
  if (!['2667', CH25.id].includes(resumed?.chapter)) fail(`/read should resume the saved place near chapter 25, got ${JSON.stringify(resumed)}`);
  await ctx2.close();

  // ...but an explicit chapter destination outside it wins over the saved place.
  await (await openAndCheck(`/books/${SLUG}/chapters/20`, CH20, { width: 1280, height: 800 })).ctx.close();

  console.log('PASS');
} finally {
  await browser.close();
}
