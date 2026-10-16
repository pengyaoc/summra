// Two reader bugs that made smoke.mjs fail on /books/paradise-lost/read.
//
//  1. A saved place from an older content version is sent to
//     /api/reader/books/<id>/recover without its `mode` (the progress
//     projection stores markers per mode), so the server rejects it with a
//     404 and the reader silently falls back to the book's opening.
//  2. calculatePages() capped its loop at 3x the *initial* block count. Long
//     paragraphs are split into remainders that are added to the block list,
//     so a few long paragraphs legitimately need more pages than that; the
//     guard logged "INFINITE LOOP DETECTED" and dropped the rest of the text.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };

// A plain-mode marker saved against Paradise Lost's content version 1 (the
// local database publishes version 2), captured from a real local session.
const STALE_MARKER = {
  chapter_id: 7992, content_version: 1, offset: 0.17, ordinal: 285,
  paragraph_id: 'para_f6575ed5c27a4caf90e935f75581b450',
  quote: 'He will select one special nation from all the rest to call upon Him',
  word_position: 54619,
};

const browser = await chromium.launch();
try {
  // 1. Stale saved place is recovered, not rejected.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await page.route(/\/api\/auth\/check/, (route) => route.fulfill({
      json: { authenticated: true, user: { id: 1, email: 'reader@example.test' } },
    }));
    await page.route(/\/api\/progress\/v2\/books\/\d+/, (route) => {
      if (route.request().method() !== 'GET') return route.fulfill({ json: { success: true } });
      return route.fulfill({ json: { success: true, projection: {
        book: { book_id: 102, last_mode: 'plain' },
        modes: [{ mode: 'plain', revision: 1, current_marker: STALE_MARKER, furthest_marker: STALE_MARKER }],
      } } });
    });
    // Never persist anything from this test into the local user's state.
    await page.route(/\/api\/progress\/v2\/(mutations|events)/, (route) => route.fulfill({ json: { success: true } }));
    const recoverResponse = page.waitForResponse(/\/api\/reader\/books\/102\/recover/, { timeout: 15000 });
    await page.goto(`${BASE}/books/paradise-lost/read`, { waitUntil: 'domcontentloaded' });
    const res = await recoverResponse.catch(() => fail('reader never asked to recover the stale place'));
    const body = JSON.parse(res.request().postData() || '{}');
    if (body.marker?.mode !== 'plain') fail(`recover request marker has mode ${JSON.stringify(body.marker?.mode)}, expected "plain"`);
    if (res.status() !== 200) fail(`recover returned HTTP ${res.status()}`);
    await page.waitForFunction(() => document.querySelectorAll('#continuous-reader-content [data-reader-anchor]').length > 0,
      null, { timeout: 15000 }).catch(() => fail('reader text never rendered'));
    if (errors.length) fail(`page errors: ${errors.join('; ')}`);
    await ctx.close();
    console.log('stale marker: recovered with mode, HTTP 200');
  }

  // 2. A few very long paragraphs paginate completely.
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.summraApp, null, { timeout: 10000 });
    const result = await page.evaluate(() => {
      const app = window.summraApp;
      const words = (n, tag) => Array.from({ length: n }, (_, i) => `${tag}${i}`).join(' ');
      const container = document.createElement('div');
      container.style.width = '700px';
      container.innerHTML = `<p>${words(3000, 'a')}</p><p>${words(3000, 'b')} ENDMARK</p>`;
      document.body.appendChild(container);
      app.calculatePages(container);
      container.remove();
      const text = app.pagination.pages.join(' ');
      return { pages: app.pagination.pages.length, hasEnd: text.includes('ENDMARK'), hasA2999: text.includes('a2999') };
    });
    if (errors.some((e) => e.includes('INFINITE LOOP'))) fail(`paginator gave up: ${errors.join('; ')}`);
    if (!result.hasA2999 || !result.hasEnd) fail(`text lost: ${result.pages} pages, last word of paragraph 1 ${result.hasA2999}, final word ${result.hasEnd}`);
    if (result.pages <= 6) fail(`expected more than 6 pages for 6,000 words, got ${result.pages}`);
    await ctx.close();
    console.log(`long paragraphs: ${result.pages} pages, all text kept`);
  }

  console.log('PASS');
} finally {
  await browser.close();
}
