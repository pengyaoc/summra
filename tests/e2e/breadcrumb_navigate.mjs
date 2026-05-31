// Repro test for breadcrumb snap-in when navigating click-from-another-page.
//
// User steps: visit a category page, click a book card, observe breadcrumb area.
// The breadcrumb area should transition smoothly from the category breadcrumb
// to the book breadcrumb. Bug: it goes blank between the two states,
// content below it jumps up and back down.
//
// This test:
//   1. Opens a category page
//   2. Installs a per-frame observer on the breadcrumb area's combined
//      visibility + height
//   3. Clicks a book card to trigger SPA navigation
//   4. Records every frame's breadcrumb state for 1.5s after the click
//   5. Asserts the breadcrumb area's height never dropped to 0 mid-transition

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5003';
const CATEGORY_URL = `${BASE}/categories/46`;

async function run() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const page = await ctx.newPage();

  console.log(`Loading ${CATEGORY_URL}...`);
  const resp = await page.goto(CATEGORY_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  if (!resp || resp.status() !== 200) {
    console.error(`unexpected status: ${resp?.status()}`);
    process.exit(1);
  }

  // Wait for the category page's books to render. They're loaded via JS into
  // .book-card divs (not anchor tags — clicks are handled by JS that calls
  // selectBook), so we wait for the cards to appear in the DOM.
  await page.waitForFunction(() => {
    return document.querySelectorAll('#category-books-grid .book-card').length > 0;
  }, { timeout: 15000 });

  await page.waitForTimeout(500);

  // Find a book card.
  const bookCard = await page.$('#category-books-grid .book-card');
  if (!bookCard) {
    console.error('No book card found on category page');
    process.exit(1);
  }
  const bookTitle = await bookCard.$eval('h3', (el) => el.textContent);
  console.log(`Will click book card: "${bookTitle}"`);

  // Install per-frame observer on the breadcrumb area.
  // We measure the bounding rect of ALL breadcrumb navs combined (because the
  // active one changes during navigation). If the total height drops to 0
  // mid-transition, the page below jumps.
  await page.evaluate(() => {
    window.__breadcrumbFrames = [];
    const start = performance.now();
    const navIds = ['breadcrumb-nav-book', 'breadcrumb-nav-category', 'breadcrumb-nav-all-categories', 'breadcrumb-nav-medium', 'breadcrumb-nav-chapter', 'breadcrumb-nav-blog', 'breadcrumb-nav-blog-post', 'breadcrumb-nav-author'];
    const sample = () => {
      const t = Math.round(performance.now() - start);
      let visibleHeight = 0;
      const navDetails = [];
      for (const id of navIds) {
        const el = document.getElementById(id);
        if (!el) continue;
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        const hidden = el.classList.contains('hidden');
        const display = cs.display;
        const parentHidden = el.closest('.hidden') !== null && el.closest('.hidden') !== el;
        if (r.height > 0) {
          visibleHeight += r.height;
        }
        navDetails.push(`${id}={h=${r.height.toFixed(0)},cls=${hidden},dis=${display},parH=${parentHidden}}`);
      }
      // Also measure the top of the FIRST visible content element below the
      // breadcrumb area — that's what jumps when the breadcrumb collapses.
      const firstContentEl = document.querySelector('#book-info-cover, #category-books-grid, .book-detail-header');
      const contentTop = firstContentEl ? firstContentEl.getBoundingClientRect().top : null;
      window.__breadcrumbFrames.push({ t, visibleHeight, navDetails, contentTop });
      if (t < 2000) requestAnimationFrame(sample);
    };
    sample();
  });

  // Click the book card (SPA navigation via JS click handler that calls selectBook).
  await bookCard.click();
  // Wait for URL change.
  await page.waitForURL(/\/books\/[^/]+$/, { timeout: 10000 }).catch(() => {});

  // Wait for samples to accumulate.
  await page.waitForTimeout(2200);

  const frames = await page.evaluate(() => window.__breadcrumbFrames);
  console.log(`Captured ${frames.length} frames`);

  // Print every change in visibleHeight or visibleNavs.
  let last = null;
  for (const f of frames) {
    const key = `${f.visibleHeight}|${f.contentTop}`;
    if (key !== last) {
      console.log(`  +${f.t}ms  bcH=${f.visibleHeight.toFixed(0)}  contentTop=${f.contentTop != null ? f.contentTop.toFixed(0) : 'null'}`);
      for (const d of f.navDetails) {
        if (!d.includes('h=0')) console.log(`     ${d}`);
      }
      last = key;
    }
  }

  // Find the minimum visible height during the transition window
  // (from after first sample until end).
  let minHeight = Infinity;
  let minFrame = null;
  for (const f of frames) {
    if (f.visibleHeight < minHeight) {
      minHeight = f.visibleHeight;
      minFrame = f;
    }
  }
  console.log(`Min breadcrumb height during transition: ${minHeight.toFixed(0)}px at +${minFrame.t}ms`);
  for (const d of minFrame.navDetails) console.log(`   ${d}`);

  await browser.close();

  if (minHeight === 0) {
    console.error('\nFAIL: breadcrumb area collapsed to 0px height during navigation');
    console.error('       (content below the breadcrumb would jump up and back down)');
    process.exit(1);
  }
  console.log('\nPASS: breadcrumb area never collapsed to 0 during navigation.');
}

run().catch((e) => { console.error(e); process.exit(1); });
