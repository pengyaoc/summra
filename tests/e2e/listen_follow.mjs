// Listen page-following rules (shared Listen player, run against Distill).
//   1. Hands off: the page turns as the audio moves on, even inside a paragraph
//      that runs onto the next page.
//   2. Turning a page yourself (playing or paused) stops following; the audio
//      keeps its place.
//   3. Away from the playing page, the bar offers "Back to audio" and "Play from here".
//   4. Pause then play continues the audio and does not move the page;
//      "Back to audio" does, and following resumes.
// Usage: BASE_URL=http://localhost:5003 node listen_follow.mjs
import { webkit } from 'playwright';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const SLUG = process.env.DISTILL_LISTEN_SLUG || 'abundance-klein-thompson';
let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };

const browser = await webkit.launch({ headless: !process.env.HEADED });
const context = await browser.newContext({ viewport: { width: 375, height: 667 } });
const page = await context.newPage();
const L = (fn, arg) => page.evaluate(fn, arg);
const problems = [];
page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));

await page.goto(`${BASE}/login`);
await page.waitForURL(`${BASE}/`);
const book = await (await page.request.get(`${BASE}/api/books/${SLUG}/audio`)).json();
const chapter = book.chapters[0];
await page.goto(`${BASE}/books/${SLUG}/read?chapter=${chapter.chapter_id}`);
await page.waitForSelector('#continuous-reader-content [data-reader-anchor]', { timeout: 15000 });
await page.waitForSelector('#listen-button', { state: 'visible', timeout: 10000 });
await page.locator('#listen-button').click();
await page.waitForFunction(() => window.distillListener?.audio?.currentTime > 0.3, null, { timeout: 15000 });
await page.waitForTimeout(800);  // the bar's re-layout has settled
check(await L(() => window.distillListener.following), 'showing the player (which re-cuts the pages) does not stop following');

const currentPage = () => L(() => window.distillListener.reader.pagination.currentPage);
const pagesWith = (pid) => L((p) => window.distillListener.reader.pagination.pages
  .map((html, i) => (html.includes(`data-reader-anchor="${p}"`) ? i : -1)).filter((i) => i >= 0), pid);
const seek = (ms) => L((m) => window.distillListener.seekToMs(m), ms);
const settle = () => page.waitForTimeout(600);

// 1. A paragraph that spans two pages: the page turns partway through it.
let split = null;
for (const unit of chapter.timings) {
  const pages = await pagesWith(unit.paragraph_id);
  if (pages.length >= 2 && unit.end_ms - unit.start_ms > 4000) { split = { ...unit, pages }; break; }
}
check(split, `found a paragraph that runs onto a second page (${split?.paragraph_id})`);
if (split) {
  await seek(split.start_ms + 200);
  await settle();
  check(await currentPage() === split.pages[0], 'at the start of that paragraph its first page shows');
  await seek(split.end_ms - 300);  // same paragraph, near its end: no new paragraph starts
  await settle();
  check(await currentPage() === split.pages[split.pages.length - 1],
    `hands off, the page turns within the paragraph (page ${await currentPage()}, expected ${split.pages.at(-1)})`);
  check(await page.locator('#listen-follow').isHidden(), 'an automatic turn does not stop following');
}

// 2 + 3. Paging by hand while paused stops following; the audio keeps its place.
await L(() => window.distillListener.pause());
await settle();
const pausedAt = await L(() => window.distillListener.audio.currentTime);
await page.keyboard.press('ArrowRight');
await settle();
await page.keyboard.press('ArrowRight');
await settle();
const handPage = await currentPage();
check(await page.locator('#listen-follow').isVisible(), 'paging while paused offers "Back to audio"');
check(await page.locator('#listen-here').isVisible(), 'paging away offers "Play from here"');

// 4. Play continues the audio where it was and leaves the page alone.
await page.locator('#listen-play').click();
await page.waitForFunction(() => !window.distillListener.audio.paused, null, { timeout: 5000 });
await settle();
check(Math.abs(await L(() => window.distillListener.audio.currentTime) - pausedAt) < 2.5, 'play continues the audio where it paused');
const next = chapter.timings.find((unit) => unit.start_ms > pausedAt * 1000 + 1000);
if (next) { await seek(next.start_ms + 100); await settle(); }
check(await currentPage() === handPage, 'while not following, a new paragraph does not move the page');

// "Back to audio" shows the playing paragraph and follows again.
await page.locator('#listen-follow').click();
await settle();
const unit = await L(() => window.distillListener.unit);
check((await pagesWith(unit)).includes(await currentPage()), 'Back to audio shows the playing paragraph');
check(await page.locator('#listen-follow').isHidden() && await page.locator('#listen-here').isHidden(),
  'following again hides both buttons');

// "Play from here" restarts the audio at the page being read.
await page.keyboard.press('ArrowRight');
await settle();
await page.keyboard.press('ArrowRight');
await settle();
const target = await L(() => document.querySelector('#continuous-reader-content .pagination-page-container [data-reader-anchor]')?.dataset.readerAnchor);
await page.locator('#listen-here').click();
await page.waitForFunction(() => !window.distillListener.audio.paused && window.distillListener.audio.currentTime > 0, null, { timeout: 10000 });
await settle();
check(await L(() => window.distillListener.startedAt) === target, `Play from here starts at this page (${target})`);
check(await page.locator('#listen-here').isHidden(), 'Play from here resumes following');

check(problems.length === 0, `no page errors${problems.length ? `: ${problems.join(' | ')}` : ''}`);
await browser.close();
if (failures) { console.error(`${failures} failure(s)`); process.exit(1); }
console.log('All listen-follow checks passed.');
