// Book detail page renders without waiting for the /api/books catalog.
//
// Bug this guards against: on a direct load of /books/<slug>, the router
// awaited the full /api/books list (every book in the library) just to
// resolve the slug, before fetching the book's own summary and chapters —
// seconds of empty page on mobile. The server now embeds the book in
// window.__INITIAL_DATA__ and renders the header, so this test stalls
// /api/books for 8s and asserts the page still fills in well before that.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const SLUG = process.env.BOOK_SLUG || 'a-journey-to-the-centre-of-the-earth';
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };

const browser = await chromium.launch();
try {
  // 1. Header is in the server HTML (no JS needed).
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const p0 = await noJs.newPage();
  await p0.goto(`${BASE}/books/${SLUG}`, { waitUntil: 'domcontentloaded' });
  const ssr = await p0.evaluate(() => ({
    title: document.getElementById('book-title')?.textContent.trim(),
    author: document.getElementById('book-author')?.textContent.trim(),
    cover: document.querySelector('#book-info-cover img')?.getAttribute('src'),
  }));
  console.log('SSR (no JS):', ssr);
  if (!ssr.title) fail('book title not server-rendered');
  if (!ssr.author?.startsWith('by ')) fail('book author not server-rendered');
  if (!ssr.cover) fail('book cover not server-rendered');
  await noJs.close();

  // 2. With /api/books stalled, summary + chapters still render promptly.
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.route(/\/api\/books(\?.*)?$/, async (route) => {
    await new Promise((r) => setTimeout(r, 8000));
    await route.continue().catch(() => {});
  });
  const t0 = Date.now();
  await page.goto(`${BASE}/books/${SLUG}`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => {
    const chapters = document.querySelectorAll('#chapters-list .chapter-box');
    const summary = document.getElementById('concise-summary-text')?.textContent.trim();
    return chapters.length > 0 && summary;
  }, null, { timeout: 6000 }).catch(() => fail(`book content not rendered within 6s while /api/books was stalled`));
  console.log(`Summary + chapters rendered in ${Date.now() - t0}ms with /api/books stalled 8s`);

  // 3. The cover stays visible after JS takes over.
  const coverVisible = await page.evaluate(() => {
    const c = document.getElementById('book-info-cover');
    return !!c && !c.classList.contains('hidden');
  });
  if (!coverVisible) fail('cover hidden after hydration');

  if (errors.length) fail(`page errors: ${errors.join('; ')}`);
  console.log('PASS');
} finally {
  await browser.close();
}
