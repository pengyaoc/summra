// The full /api/books catalog is fetched at most once per page load, and not
// at all by pages that don't need it until the reader uses search.
//
// Bug this guards against: HeroSearch and SummraApp each fetched /api/books
// on every page load (two identical ~57 KB downloads), even on pages that
// render without it (home and book pages are server-rendered).

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  let catalogFetches = 0;
  page.on('request', (r) => { if (/\/api\/books(\?.*)?$/.test(new URL(r.url()).pathname + new URL(r.url()).search)) catalogFetches++; });

  for (const path of ['/', '/books/a-journey-to-the-centre-of-the-earth']) {
    catalogFetches = 0;
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
    console.log(`${path}: ${catalogFetches} catalog fetch(es) on load`);
    if (catalogFetches !== 0) fail(`${path} fetched /api/books ${catalogFetches}x on load; expected 0`);
  }

  // A page that does need the catalog fetches it exactly once.
  catalogFetches = 0;
  await page.goto(`${BASE}/books`, { waitUntil: 'networkidle' });
  console.log(`/books: ${catalogFetches} catalog fetch(es) on load`);
  if (catalogFetches !== 1) fail(`/books fetched /api/books ${catalogFetches}x; expected exactly 1`);

  // Search still works on home: catalog loads on demand.
  catalogFetches = 0;
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.click('#hero-search-input');
  await page.keyboard.type('frank');
  await page.waitForSelector('#hero-search-results .hero-search-result-item', { timeout: 5000 })
    .catch(() => fail('search returned no results after typing'));
  console.log(`search: ${catalogFetches} catalog fetch(es); results shown`);
  if (catalogFetches !== 1) fail(`search fetched /api/books ${catalogFetches}x; expected exactly 1`);

  console.log('PASS');
} finally {
  await browser.close();
}
