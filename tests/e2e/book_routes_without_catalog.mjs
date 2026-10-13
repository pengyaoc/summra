// Every per-book route renders without waiting for the /api/books catalog.
//
// Bug this guards against: /books/<slug>/summary, /read and the legacy
// /chapters/<n> routes awaited the full catalog just to resolve the slug,
// even though the server already embeds the book in __INITIAL_DATA__.
// /api/books is stalled for 8s here; each page must show content within 6s.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const SLUG = process.env.BOOK_SLUG || 'a-journey-to-the-centre-of-the-earth';
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };

const browser = await chromium.launch();
try {
  for (const path of [`/books/${SLUG}`, `/books/${SLUG}/summary`, `/books/${SLUG}/read`, `/books/${SLUG}/chapters/3`]) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.route(/\/api\/books(\?.*)?$/, async (route) => {
      await new Promise((r) => setTimeout(r, 8000));
      await route.continue().catch(() => {});
    });
    const t0 = Date.now();
    await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => {
      const section = [...document.querySelectorAll('section')].find((s) =>
        s.id !== 'hero-section' && !s.classList.contains('hidden') && s.offsetParent !== null);
      return section && section.innerText.replace(/\s+/g, ' ').length > 400;
    }, null, { timeout: 6000 }).catch(() => fail(`${path}: no content within 6s while /api/books was stalled`));
    console.log(`${path}: content in ${Date.now() - t0}ms`);
    if (errors.length) fail(`${path}: page errors: ${errors.join('; ')}`);
    await ctx.close();
  }
  console.log('PASS');
} finally {
  await browser.close();
}
