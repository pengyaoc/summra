// FAILING TEST: sticky-header overlap on mobile chapter view (paginated mode).
//
// What this test does: loads Sherlock Ch. VI on a mobile-sized Chromium with
// device emulation, waits for pagination to settle and for the sticky header
// to actually become visible, then asserts the gap between the bottom of the
// sticky header and the top of the first paragraph is >= 0 (i.e. no overlap).
//
// The bug it catches: when stale CSS is served alongside fresh HTML+JS (the
// service-worker CacheFirst lock-in), the .chapter-detail-section's
// padding-top: 51px reservation for the sticky header is missing, and the
// always-on sticky header overlaps the first 51px of body content.
//
// Indirectly this test also catches any future regression where the sticky
// header height changes (e.g. extra button row) without updating the section
// padding-top reservation.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5003';
const CHAPTER_URL = `${BASE}/books/the-adventures-of-sherlock-holmes/chapters/6`;

const VIEWPORTS = [
  { name: 'iphone-12', width: 390, height: 844 },
  { name: 'iphone-se', width: 375, height: 667 },
  { name: 'pixel-5',   width: 393, height: 851 },
];

const MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1';

async function probe(page) {
  // Wait for the pagination wrapper to be created and contain at least one block.
  await page.waitForFunction(() => {
    const wrapper = document.querySelector('.pagination-wrapper');
    const pc = document.querySelector('.pagination-page-container');
    return wrapper && pc && pc.children.length > 0 && wrapper.offsetHeight > 100;
  }, { timeout: 15000 });

  // Wait for the sticky header to ACTUALLY become visible. setupStickyHeader
  // uses a MutationObserver; it may show after pagination is in place.
  await page.waitForFunction(() => {
    const h = document.querySelector('.sticky-reading-header');
    return h && !h.classList.contains('hidden') && h.offsetHeight > 0;
  }, { timeout: 15000 });

  // Settle: one extra frame so transforms have committed.
  await page.waitForTimeout(200);

  return await page.evaluate(() => {
    const sticky = document.querySelector('.sticky-reading-header');
    const pc = document.querySelector('.pagination-page-container');
    const firstBlock = pc.querySelector('p, h1, h2, h3, h4, h5, h6, blockquote');
    const sr = sticky.getBoundingClientRect();
    const br = firstBlock.getBoundingClientRect();
    return {
      stickyTop: sr.top,
      stickyBottom: sr.bottom,
      stickyHeight: sr.height,
      firstBlockTop: br.top,
      firstBlockText: firstBlock.textContent.slice(0, 60),
      gap: br.top - sr.bottom,
    };
  });
}

async function run() {
  const browser = await chromium.launch();
  const failures = [];

  for (const vp of VIEWPORTS) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      isMobile: true,
      hasTouch: true,
      deviceScaleFactor: 2,
      userAgent: MOBILE_UA,
    });
    const page = await ctx.newPage();
    try {
      const resp = await page.goto(CHAPTER_URL, { waitUntil: 'networkidle', timeout: 30000 });
      if (!resp || resp.status() >= 400) {
        failures.push(`[${vp.name}] HTTP ${resp ? resp.status() : 'no-response'}`);
        await ctx.close();
        continue;
      }
      const m = await probe(page);
      const status = m.gap >= 0 ? 'OK' : 'FAIL (overlap)';
      console.log(`[${vp.name}] sticky h=${m.stickyHeight.toFixed(1)} top=${m.stickyTop.toFixed(1)} bot=${m.stickyBottom.toFixed(1)} | first block top=${m.firstBlockTop.toFixed(1)} | gap=${m.gap.toFixed(1)}  ${status}`);
      console.log(`  first block: "${m.firstBlockText}"`);
      if (m.gap < 0) {
        failures.push(`[${vp.name}] sticky header overlaps first paragraph by ${(-m.gap).toFixed(1)}px (gap=${m.gap.toFixed(1)})`);
      }
    } catch (e) {
      failures.push(`[${vp.name}] ${e.message}`);
    } finally {
      await ctx.close();
    }
  }

  await browser.close();

  if (failures.length) {
    console.error('\nFAILURES:');
    failures.forEach(f => console.error('  ' + f));
    process.exit(1);
  }
  console.log('\nAll viewports: no overlap detected.');
}

run().catch((e) => { console.error(e); process.exit(1); });
