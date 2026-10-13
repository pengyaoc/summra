// The reader opens without serial segment round trips.
//
// Bugs this guards against:
//  1. loadContinuousReaderAt() fetched the current segment, then the next
//     one, then rendered — two serial round trips before any text showed.
//  2. Opening at chapter N (legacy /chapters/<n> links) downloaded segments
//     one by one from the start of the book until one contained chapter N.
// Each segment response is delayed 1.5s here.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const SLUG = process.env.BOOK_SLUG || 'a-journey-to-the-centre-of-the-earth';
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };
const SEGMENT_DELAY = 1500;

const browser = await chromium.launch();
async function open(path) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  const segmentRequests = [];
  await page.route(/\/api\/reader\/books\/\d+\/segments\//, async (route) => {
    segmentRequests.push(route.request().url());
    await new Promise((r) => setTimeout(r, SEGMENT_DELAY));
    await route.continue().catch(() => {});
  });
  const t0 = Date.now();
  await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelectorAll('#continuous-reader-content [data-reader-anchor]').length > 0,
    null, { timeout: 15000 }).catch(() => fail(`${path}: reader text never rendered`));
  const ms = Date.now() - t0;
  const heading = await page.evaluate(() => document.querySelector('#continuous-reader-content .reader-chapter-heading')?.textContent || '');
  if (errors.length) fail(`${path}: page errors: ${errors.join('; ')}`);
  await ctx.close();
  return { ms, segmentsBeforeRender: segmentRequests.length, heading };
}

try {
  const start = await open(`/books/${SLUG}/read`);
  console.log(`/read: text in ${start.ms}ms after ${start.segmentsBeforeRender} segment request(s)`);
  // Two serial fetches would take >= 2 x 1.5s.
  if (start.ms >= 2 * SEGMENT_DELAY) fail(`/read took ${start.ms}ms — current and next segments fetched serially`);

  const deep = await open(`/books/${SLUG}/chapters/20`);
  console.log(`/chapters/20: text in ${deep.ms}ms after ${deep.segmentsBeforeRender} segment request(s); first heading "${deep.heading}"`);
  if (deep.segmentsBeforeRender > 2) fail(`opening chapter 20 requested ${deep.segmentsBeforeRender} segments; expected <= 2 (target + next)`);
  if (deep.ms >= 2 * SEGMENT_DELAY) fail(`/chapters/20 took ${deep.ms}ms — segment lookup is serial`);

  console.log('PASS');
} finally {
  await browser.close();
}
