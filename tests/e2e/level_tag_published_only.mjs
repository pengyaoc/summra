// Client-rendered cards show only published reading levels: "Original:
// Grade N" from ATOS, and nothing for a book that has only an estimated
// CEFR level (no Easy / Moderate / Challenging fallback). Mirrors
// test_no_level_tag_without_a_published_grade for the Jinja card.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exit(1); };

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.summraApp, null, { timeout: 10000 });
  const tags = await page.evaluate(() => {
    const app = window.summraApp;
    return {
      graded: app.difficultyTagHtml({ grade_label: 'Grade 7', grade_band: '6-8', level: 'Moderate' }),
      cefrOnly: app.difficultyTagHtml({ grade_label: null, level: 'Moderate', cefr_level: 'B2' }),
      none: app.difficultyTagHtml({}),
    };
  });
  if (tags.graded !== '<span class="grade-tag grade-tag--6-8">Original: Grade 7</span>') fail(`graded book tag: ${tags.graded}`);
  if (tags.cefrOnly !== '') fail(`CEFR-only book still tagged: ${tags.cefrOnly}`);
  if (tags.none !== '') fail(`book with no level tagged: ${tags.none}`);
  console.log('PASS');
} finally {
  await browser.close();
}
