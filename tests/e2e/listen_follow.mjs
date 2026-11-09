// Listen page-following rules (shared Listen player, run against Distill).
//   1. Hands off: the page turns as the audio moves on, even inside a paragraph
//      that runs onto the next page.
//   2. Turning a page yourself (playing or paused) stops following; the audio
//      keeps its place.
//   3. Pause then play continues the audio and does not move the page.
//   4. Paging back to the spoken page follows again.
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
await page.waitForFunction(() => window.distillAudio?.player?.audio?.currentTime > 0.3, null, { timeout: 15000 });
await page.waitForTimeout(800);  // the bar's re-layout has settled
check(await L(() => window.distillAudio.link.following), 'showing the player (which re-cuts the pages) does not stop following');

const currentPage = () => L(() => window.distillAudio.link.reader.pagination.currentPage);
const pagesWith = (pid) => L((p) => window.distillAudio.link.reader.pagination.pages
  .map((html, i) => (html.includes(`data-reader-anchor="${p}"`) ? i : -1)).filter((i) => i >= 0), pid);
const seek = (ms) => L((m) => window.distillAudio.player.seekToMs(m), ms);
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
  check(await L(() => window.distillAudio.link.following), 'an automatic turn does not stop following');
}

// 2 + 3. Paging by hand while paused stops following; the audio keeps its place.
await L(() => window.distillAudio.player.pause());
await settle();
const pausedAt = await L(() => window.distillAudio.player.position().ms / 1000);
await page.keyboard.press('ArrowRight');
await settle();
await page.keyboard.press('ArrowRight');
await settle();
const handPage = await currentPage();
check(!await L(() => window.distillAudio.link.following), 'paging while paused stops following');

// 4. Play continues the audio where it was and leaves the page alone.
await L(() => window.distillAudio.player.resume());
await page.waitForFunction(() => window.distillAudio.player.playing, null, { timeout: 5000 });
await settle();
check(Math.abs(await L(() => window.distillAudio.player.audio.currentTime) - pausedAt) < 2.5, 'play continues the audio where it paused');
const next = chapter.timings.find((unit) => unit.start_ms > pausedAt * 1000 + 1000);
if (next) { await seek(next.start_ms + 100); await settle(); }
check(await currentPage() === handPage, 'while not following, a new paragraph does not move the page');

// Headphones on the same book open the player; listening from a chapter jump follows again.
await L(() => window.distillAudio.player.load(window.distillAudio.player.index, 0));
await settle();
check(await L(() => window.distillAudio.link.following), 'starting a track from the player follows again');

// 5. Closing the player clears the highlight, and paging does not bring it back.
const highlighted = () => page.locator('#continuous-reader-content .listen-current').count();
await L(() => window.distillAudio.link.setFollowing(true));
await seek(chapter.timings[1].start_ms + 100);
await settle();
check(await highlighted() > 0, 'the spoken paragraph is highlighted before closing');
await L(() => window.distillAudio.player.close());
await settle();
check(!await L(() => window.distillAudio.player.active), 'closing ends listening');
check(await highlighted() === 0, 'closing the player removes the highlight');
await page.keyboard.press('ArrowRight');
await settle();
await page.keyboard.press('ArrowLeft');
await settle();
check(await highlighted() === 0, 'paging after closing does not bring the highlight back');
await L(() => window.distillAudio.player.audio.dispatchEvent(new Event('timeupdate')));
await settle();
check(await highlighted() === 0, 'a late time update after closing does not bring it back');

// detach leaves the reader as it found it.
const detached = await L(() => { const { link } = window.distillAudio; const wrapped = link.reader.navigateToNextPage; link.detach(); const restored = link.reader.navigateToNextPage !== wrapped; return { restored, own: Object.hasOwn(link.reader, 'navigateToNextPage') ? link.reader.navigateToNextPage.name : '', button: !!document.getElementById('listen-button') }; });
check(detached.restored && !detached.button, 'detach restores the reader and removes the headphones');
await page.reload();
await page.waitForSelector('#listen-button', { state: 'visible', timeout: 15000 });

// 6. Starting again shows the highlight.
await page.locator('#listen-button').click();
await page.waitForFunction(() => window.distillAudio.player.playing, null, { timeout: 15000 });
await page.waitForFunction(() => document.querySelector('#continuous-reader-content .listen-current'), null, { timeout: 10000 }).catch(() => {});
check(await highlighted() > 0, 'listening again brings the highlight back');

check(problems.length === 0, `no page errors${problems.length ? `: ${problems.join(' | ')}` : ''}`);
await browser.close();
if (failures) { console.error(`${failures} failure(s)`); process.exit(1); }
console.log('All listen-follow checks passed.');
