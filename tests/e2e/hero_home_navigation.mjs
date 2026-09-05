// Regression test for the hero-section dedup (2026-09 refactor).
//
// Bug this guards against: the hero section used to be SSR'd in full only
// on the home page itself; every other page got an empty
// `<div id="hero-section" class="hidden"></div>` placeholder, and
// showHomeSection() rebuilt the hero from a ~150-line JS template literal
// when navigating there client-side — a second copy of the markup that had
// already drifted from the SSR copy (different hero title/subtitle text).
//
// This test: loads a book detail page (hero is the hidden, always-rendered
// version), clicks the header logo to navigate home client-side, and
// asserts the hero section becomes visible with real content — not an
// empty div, and not a JS-rebuilt copy with different text than what SSR
// would have produced.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const BOOK_URL = `${BASE}/books/a-christmas-carol-in-prose`;

async function run() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();

  console.log(`Loading ${BOOK_URL}...`);
  const resp = await page.goto(BOOK_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  if (!resp || resp.status() !== 200) {
    console.error(`unexpected status: ${resp?.status()}`);
    process.exit(1);
  }

  // On a sub-page, the hero section must be present in the DOM (not an
  // empty placeholder) but hidden.
  const subpageHero = await page.evaluate(() => {
    const el = document.getElementById('hero-section');
    return {
      exists: !!el,
      hidden: el ? el.classList.contains('hidden') : null,
      hasSearchInput: !!document.getElementById('hero-search-input'),
      childCount: el ? el.children.length : 0,
    };
  });
  console.log('Sub-page hero state:', subpageHero);
  if (!subpageHero.exists || !subpageHero.hidden || subpageHero.childCount === 0) {
    console.error('FAIL: hero-section on a sub-page must exist, be hidden, and have real content (not an empty placeholder)');
    process.exit(1);
  }
  if (!subpageHero.hasSearchInput) {
    console.error('FAIL: hero-search-input must exist on page load (for HeroSearch() to wire up at bootstrap)');
    process.exit(1);
  }

  // Click the header logo to navigate home client-side (pushState, no reload).
  await page.click('#header-home-link');
  await page.waitForFunction(() => {
    const el = document.getElementById('hero-section');
    return el && !el.classList.contains('hidden');
  }, { timeout: 5000 });

  const homeHero = await page.evaluate(() => {
    const el = document.getElementById('hero-section');
    const title = document.querySelector('.hero-banner-title');
    return {
      hidden: el.classList.contains('hidden'),
      titleText: title ? title.textContent.trim() : null,
      hasSearchInput: !!document.getElementById('hero-search-input'),
    };
  });
  console.log('Post-navigation home hero state:', homeHero);

  if (homeHero.hidden) {
    console.error('FAIL: hero-section still hidden after navigating home');
    process.exit(1);
  }
  if (!homeHero.titleText) {
    console.error('FAIL: no hero title text found after client-side navigation to home');
    process.exit(1);
  }
  if (!homeHero.hasSearchInput) {
    console.error('FAIL: hero-search-input missing after navigating home (would mean HeroSearch lost its element reference)');
    process.exit(1);
  }

  console.log(`PASS: hero section shows real content ("${homeHero.titleText}") after client-side navigation home.`);
  await browser.close();
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
