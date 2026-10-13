// Author / category / all-categories pages don't serialize behind /api/books.
//
// Bug this guards against: the router awaited the full /api/books catalog
// before every one of these pages, although author pages never read it,
// category pages have their own /api/categories/<id>/books endpoint, and
// all-categories fetched /api/categories only after the catalog arrived.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();
async function visit(path, stalls, ready, budgetMs) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  for (const [pattern, ms] of stalls) {
    await page.route(pattern, async (route) => { await delay(ms); await route.continue().catch(() => {}); });
  }
  const t0 = Date.now();
  await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(ready, null, { timeout: budgetMs })
    .catch(() => fail(`${path}: not rendered within ${budgetMs}ms`));
  console.log(`${path}: rendered in ${Date.now() - t0}ms`);
  if (errors.length) fail(`${path}: page errors: ${errors.join('; ')}`);
  await ctx.close();
}

try {
  const catalogStalled = [[/\/api\/books(\?.*)?$/, 8000]];
  await visit('/authors/jules-verne', catalogStalled,
    () => (document.getElementById('author-detail-container')?.innerText || '').length > 200, 6000);
  await visit('/categories/34', catalogStalled,
    () => document.querySelectorAll('#category-books-grid > *').length > 0, 6000);

  // All-categories genuinely needs the catalog; it must fetch it in parallel
  // with /api/categories (2s + 2s serial would exceed the 3.5s budget).
  await visit('/categories', [[/\/api\/books(\?.*)?$/, 2000], [/\/api\/categories$/, 2000]],
    () => document.querySelectorAll('#all-categories-container > *').length > 0, 3500);

  // Clicking a category card (rendered from the category API, not the
  // catalog) opens the right book page.
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(`${BASE}/categories/34`, { waitUntil: 'networkidle' });
  await page.locator('#category-books-grid > *').first().click();
  await page.waitForFunction(() => /\/books\/[^/]+$/.test(location.pathname) && document.getElementById('book-title')?.textContent.trim());
  const landed = await page.evaluate(() => ({ path: location.pathname, title: document.getElementById('book-title').textContent.trim() }));
  const status = (await page.request.get(`${BASE}${landed.path}`)).status();
  console.log(`category card -> ${landed.path} (${landed.title}), direct load HTTP ${status}`);
  if (status !== 200) fail(`category card navigated to ${landed.path}, which 404s on reload`);
  await ctx.close();

  console.log('PASS');
} finally {
  await browser.close();
}
