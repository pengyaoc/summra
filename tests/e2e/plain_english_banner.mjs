// Regression test: book page must adapt its chapters header + show a
// "Plain English version coming soon" banner when the book has no
// modern-English translation yet.
//
// Two scenarios:
//   1. Book WITH modern translation (alices-adventures-in-wonderland):
//      - H3 #chapters-section-heading reads "Chapters in Plain English"
//      - #plain-english-coming-soon banner is hidden
//   2. Book WITHOUT modern translation (a-journey-to-the-centre-of-the-earth):
//      - H3 reads "Chapters"
//      - Banner is visible and contains "Plain English version coming soon"
//
// Usage: BASE_URL=http://localhost:5001 node plain_english_banner.mjs

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const WITH_MODERN = `${BASE}/books/alices-adventures-in-wonderland`;
const WITHOUT_MODERN = `${BASE}/books/a-journey-to-the-centre-of-the-earth`;

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

let failed = false;
const checks = [];

function check(name, cond, detail = '') {
  checks.push({ name, cond, detail });
  if (!cond) failed = true;
}

async function waitForChaptersLoaded() {
  await page.waitForFunction(() => {
    const list = document.getElementById('chapters-list');
    const app = window.summraApp;
    return list && app && Array.isArray(app.chapters) && app.chapters.length > 0;
  }, { timeout: 15_000 });
  // One extra tick so the post-load DOM updates flush.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => r())));
}

async function readState() {
  return page.evaluate(() => {
    const h = document.getElementById('chapters-section-heading');
    const banner = document.getElementById('plain-english-coming-soon');
    const bannerVisible = banner ? !banner.classList.contains('hidden') &&
                                   window.getComputedStyle(banner).display !== 'none'
                                 : false;
    return {
      headingText: h ? h.textContent.trim() : null,
      bannerExists: !!banner,
      bannerVisible,
      bannerText: banner ? banner.textContent.trim() : null,
    };
  });
}

try {
  // --- Scenario 1: book WITH modern translation ---
  await page.goto(WITH_MODERN, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await waitForChaptersLoaded();
  const withModern = await readState();

  check('with-modern: heading element exists', withModern.headingText !== null,
        `got: ${JSON.stringify(withModern.headingText)}`);
  check('with-modern: heading reads "Chapters in Plain English"',
        withModern.headingText === 'Chapters in Plain English',
        `got: ${JSON.stringify(withModern.headingText)}`);
  check('with-modern: coming-soon banner exists in DOM', withModern.bannerExists);
  check('with-modern: coming-soon banner is hidden',
        withModern.bannerExists && !withModern.bannerVisible,
        `visible=${withModern.bannerVisible}`);

  // --- Scenario 2: book WITHOUT modern translation ---
  await page.goto(WITHOUT_MODERN, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await waitForChaptersLoaded();
  const withoutModern = await readState();

  check('without-modern: heading reads "Chapters"',
        withoutModern.headingText === 'Chapters',
        `got: ${JSON.stringify(withoutModern.headingText)}`);
  check('without-modern: coming-soon banner is visible',
        withoutModern.bannerExists && withoutModern.bannerVisible,
        `exists=${withoutModern.bannerExists} visible=${withoutModern.bannerVisible}`);
  check('without-modern: banner mentions "Plain English" and "coming soon"',
        withoutModern.bannerText &&
        /plain english/i.test(withoutModern.bannerText) &&
        /coming soon/i.test(withoutModern.bannerText),
        `got: ${JSON.stringify(withoutModern.bannerText)}`);

} finally {
  await browser.close();
}

for (const c of checks) {
  const tag = c.cond ? 'PASS' : 'FAIL';
  const suffix = c.detail ? ` — ${c.detail}` : '';
  console.log(`[${tag}] ${c.name}${suffix}`);
}
process.exit(failed ? 1 : 0);
