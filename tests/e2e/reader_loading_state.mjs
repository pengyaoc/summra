// The reader's loading state is a skeleton of the reading column, not a bare
// "Opening book…" line, and it does not flash on fast opens.
//
//  1. Slow open (manifest delayed 1.5s): a skeleton appears inside the reading
//     column, the visible status line stays hidden, and screen readers still
//     get "Opening book…". The skeleton is gone once text renders.
//  2. Fast open (no delay): the skeleton never appears.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const SLUG = process.env.BOOK_SLUG || 'paradise-lost';
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };

const browser = await chromium.launch();
async function newPage(delayManifest) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  if (delayManifest) {
    await page.route(/\/api\/reader\/books\/\d+\/manifest/, async (route) => {
      await new Promise((r) => setTimeout(r, delayManifest));
      await route.continue().catch(() => {});
    });
  }
  return { ctx, page, errors };
}
const textRendered = (page) => page.waitForFunction(
  () => document.querySelectorAll('#continuous-reader-content [data-reader-anchor]').length > 0,
  null, { timeout: 15000 });

try {
  // 1. Slow open.
  {
    const { ctx, page, errors } = await newPage(1500);
    await page.goto(`${BASE}/books/${SLUG}/read`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#continuous-reader-content .reader-skeleton', { state: 'visible', timeout: 1400 })
      .catch(() => fail('slow open: no skeleton in the reading column'));
    const during = await page.evaluate(() => {
      const status = document.getElementById('reader-status');
      const sk = document.querySelector('#continuous-reader-content .reader-skeleton');
      return {
        statusVisible: !!status && !status.classList.contains('hidden') && status.offsetHeight > 0,
        label: sk?.getAttribute('aria-label') || '',
        lines: sk?.querySelectorAll('.reader-skeleton-line').length || 0,
      };
    });
    if (during.statusVisible) fail('slow open: bare status line is still visible alongside the skeleton');
    if (during.label !== 'Opening book…') fail(`slow open: skeleton aria-label is "${during.label}"`);
    if (during.lines < 5) fail(`slow open: skeleton has ${during.lines} lines`);
    await page.screenshot({ path: 'screenshots/reader_loading_state.png' });
    await textRendered(page).catch(() => fail('slow open: text never rendered'));
    if (await page.$('#continuous-reader-content .reader-skeleton')) fail('slow open: skeleton left behind after render');
    if (errors.length) fail(`slow open: page errors: ${errors.join('; ')}`);
    await ctx.close();
    console.log('slow open: skeleton shown, then replaced by text');
  }

  // 2. Fast open: record whether the skeleton ever entered the DOM.
  {
    const { ctx, page, errors } = await newPage(0);
    await page.addInitScript(() => {
      window.__sawSkeleton = false;
      new MutationObserver(() => {
        if (document.querySelector('.reader-skeleton')) window.__sawSkeleton = true;
      }).observe(document, { childList: true, subtree: true });
    });
    // Warm the server-side manifest cache so this measures the fast path.
    await page.request.get(`${BASE}/api/reader/books/102/manifest`).catch(() => {});
    await page.goto(`${BASE}/books/${SLUG}/read`, { waitUntil: 'domcontentloaded' });
    await textRendered(page).catch(() => fail('fast open: text never rendered'));
    if (await page.evaluate(() => window.__sawSkeleton)) fail('fast open: skeleton flashed');
    if (errors.length) fail(`fast open: page errors: ${errors.join('; ')}`);
    await ctx.close();
    console.log('fast open: no skeleton flash');
  }

  console.log('PASS');
} finally {
  await browser.close();
}
