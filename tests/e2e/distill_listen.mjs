// Distill Listen: audio player synced with the reader, in WebKit (closest to iOS Safari, plays AAC).
//
//   DISTILL_USER_DB=$TMPDIR/distill_listen_e2e.db PORT=5003 venv/bin/python -m distill.app
//   cd tests/e2e && node distill_listen.mjs
//
// Needs a book with rendered audio (make_audio). Exits 1 on any FAIL or page error.

import { webkit } from 'playwright';
import { mkdirSync } from 'node:fs';
import { unitAt, msFor } from '../../shared/static/js/listen.js';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const SLUG = process.env.DISTILL_LISTEN_SLUG || 'abundance-klein-thompson';
const SHOTS = new URL('./screenshots/', import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };

// Pure timing helpers.
const T = [
  { paragraph_id: '5.0', start_ms: 0, end_ms: 1000 },
  { paragraph_id: '5.2', start_ms: 1350, end_ms: 2350 },
];
check(unitAt(T, 500).paragraph_id === '5.0' && unitAt(T, 500).offset === 0.5, 'unitAt: inside a unit gives its offset');
check(unitAt(T, 1200).paragraph_id === '5.0' && unitAt(T, 1200).offset === 1, 'unitAt: a gap belongs to the unit before');
check(unitAt(T, 99999).paragraph_id === '5.2' && unitAt(T, 99999).offset === 1, 'unitAt: past the end clamps to the last unit');
check(msFor(T, '5.2', 0.5) === 1850, 'msFor: unit start plus offset');
check(msFor(T, '5.2', 7) === 2350 && msFor(T, 'missing', 0) === 0, 'msFor: clamps offset; unknown unit starts at 0');

const browser = await webkit.launch({ headless: !process.env.HEADED });
const problems = [];
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));

await page.goto(`${BASE}/login`);  // local auth is off: this signs in and returns to the library
await page.waitForURL(`${BASE}/`);
await page.waitForLoadState('networkidle');  // home's own audio lookups finish before the test navigates away

const book = await (await page.request.get(`${BASE}/api/books/${SLUG}/audio`)).json();
check(book.chapters.length > 1, `book ${SLUG} has audio for ${book.chapters.length} chapters`);
const first = book.chapters[0];

await page.goto(`${BASE}/books/${SLUG}/read?chapter=${first.chapter_id}`);
await page.waitForSelector('#continuous-reader-content [data-reader-anchor]', { timeout: 15000 });
check(await page.waitForSelector('#listen-button', { state: 'visible', timeout: 10000 }).then(() => true, () => false),
  'Listen button shows for a book with audio');

await page.locator('#listen-button').click();
await page.waitForFunction(() => window.distillListener?.audio?.currentTime > 0.3, null, { timeout: 15000 });
check(await page.locator('#listen-bar').isVisible(), 'mini player bar appears and audio plays');
const topAnchor = await page.evaluate(() => window.distillListener.startedAt);
check(topAnchor && topAnchor.startsWith(`${first.chapter_id}.`), `listening started at the reading position (${topAnchor})`);

const second = first.timings[1];
await page.evaluate((ms) => window.distillListener.seekToMs(ms), second.start_ms + 100);
await page.waitForFunction((pid) => document.querySelector(`#continuous-reader-content .listen-current[data-reader-anchor="${pid}"]`),
  second.paragraph_id, { timeout: 10000 }).catch(() => {});
check(await page.locator(`#continuous-reader-content .listen-current[data-reader-anchor="${second.paragraph_id}"]`).count() > 0,
  'the spoken paragraph is highlighted');
check(await page.evaluate(() => navigator.mediaSession?.metadata?.title) === first.title, 'lock-screen metadata names the chapter');
await page.waitForTimeout(800);  // the bar's re-layout has settled
check(await page.locator('#listen-follow').isHidden(), 'showing the player does not count as paging away');
await page.keyboard.press('ArrowRight');
await page.waitForTimeout(400);
await page.keyboard.press('ArrowRight');
await page.waitForSelector('#listen-follow', { state: 'visible', timeout: 3000 }).catch(() => {});
check(await page.locator('#listen-follow').isVisible(), 'paging away by hand offers "Back to audio"');

await page.locator('#listen-play').click();
await page.waitForFunction(() => window.distillListener.audio.paused);
const saved = await page.evaluate((id) => JSON.parse(localStorage.getItem(`distill-listen-${id}`) || 'null'), book.book_id);
check(saved?.paragraph_id === second.paragraph_id && Math.abs(saved.ms - (second.start_ms + 100)) < 1500,
  `pause saves the place locally (${saved?.paragraph_id} @ ${saved?.ms} ms)`);
await page.screenshot({ path: `${SHOTS}distill_listen_bar.png` });

await page.reload();
await page.waitForSelector('#continuous-reader-content [data-reader-anchor]', { timeout: 15000 });
const label = await page.locator('#listen-resume').textContent().catch(() => '');
const mmss = `${Math.floor(saved.ms / 60000)}:${String(Math.floor(saved.ms / 1000) % 60).padStart(2, '0')}`;
check(label.includes('Resume listening') && label.includes(mmss), `after a reload the bar offers "${label.trim()}"`);
// iOS only lets play() start inside the tap, so it must not wait for the audio to load first.
await page.evaluate(() => {
  window.__playReady = [];
  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () { window.__playReady.push(this.readyState); return play.call(this); };
});
await page.locator('#listen-resume').click();
await page.waitForFunction((ms) => Math.abs(window.distillListener.audio.currentTime * 1000 - ms) < 2000, saved.ms, { timeout: 10000 })
  .catch(() => {});
check(Math.abs(await page.evaluate(() => window.distillListener.audio.currentTime * 1000) - saved.ms) < 2000,
  'resume continues at the saved second');
check(await page.evaluate(() => window.__playReady[0]) === 0, 'resume calls play() inside the tap, before the audio has loaded');

await page.evaluate(() => window.distillListener.audio.dispatchEvent(new Event('ended')));
await page.waitForFunction((url) => window.distillListener.audio.src.endsWith(url), book.chapters[1].url, { timeout: 10000 }).catch(() => {});
check((await page.evaluate(() => window.distillListener.audio.src)).endsWith(book.chapters[1].url), 'end of chapter loads the next chapter');

await page.waitForFunction(() => Number.isFinite(window.distillListener.audio.duration), null, { timeout: 10000 });
await page.evaluate(() => window.distillListener.seekToMs(1e9));
check(await page.evaluate(() => window.distillListener.audio.currentTime <= window.distillListener.audio.duration + 0.01),
  'seeking past the end is clamped');

// Once paused, paging by hand and leaving the app must not post the old audio position.
// (The seek past the end above moves on to the next chapter; let it start before pausing.)
await page.waitForFunction((url) => window.distillListener.audio.src.endsWith(url) && window.distillListener.audio.currentTime > 0.3,
  book.chapters[2].url, { timeout: 10000 }).catch(() => {});
await page.evaluate(() => window.distillListener.pause());
await page.waitForTimeout(800);
check(await page.evaluate(() => window.distillListener.audio.paused), 'the player is paused');
const hasQueue = await page.evaluate(() => {
  if (!window.authModule?.queueReaderMutation) return false;
  window.__causes = [];
  const queue = window.authModule.queueReaderMutation;
  window.authModule.queueReaderMutation = (mutation) => { window.__causes.push(mutation.event_cause); return queue(mutation); };
  return true;
});
check(hasQueue, 'progress saves can be watched');
for (let i = 0; i < 3; i += 1) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(300); }
await page.waitForTimeout(1200);
const pagedTo = await page.evaluate(() => window.distillListener.reader.continuousReader.currentMarker?.paragraph_id);
await page.evaluate(() => {
  Object.defineProperty(document, 'visibilityState', { get: () => 'hidden', configurable: true });
  document.dispatchEvent(new Event('visibilitychange'));
  window.dispatchEvent(new Event('pagehide'));
});
await page.waitForTimeout(500);
const causes = await page.evaluate(() => window.__causes);
check(!causes.includes('listen'), `hiding a paused player posts no audio position (${causes.join(',')})`);
check(await page.evaluate(() => window.distillListener.reader.continuousReader.currentMarker?.paragraph_id) === pagedTo,
  'the hand-paged reading position is kept');

// A sign-in redirect while loading audio pauses with a clear message.
// The service worker would answer these requests itself; block it so the routes apply.
const failContext = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
const fresh = await failContext.newPage();
await fresh.goto(`${BASE}/login`);
await fresh.waitForURL(`${BASE}/`);
fresh.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
await fresh.route('**/api/books/*/audio', (route) => route.fulfill({ status: 200, contentType: 'text/html', body: '<html>Sign in</html>' }));
await fresh.goto(`${BASE}/books/${SLUG}/read?chapter=${first.chapter_id}`);
await fresh.waitForSelector('#continuous-reader-content [data-reader-anchor]', { timeout: 15000 });
const hidden = !(await fresh.locator('#listen-button').isVisible());
check(hidden, 'no audio info (signed out) hides Listen rather than failing silently');
await fresh.unroute('**/api/books/*/audio');
await fresh.reload();
await fresh.waitForSelector('#listen-button', { state: 'visible', timeout: 15000 });
// What the audio element receives after an expired session's redirect: the sign-in HTML page.
await fresh.route('**/books/*/audio/*.m4a', (route) => route.fulfill({ status: 200, contentType: 'text/html', body: '<html>Sign in with Google</html>' }));
await fresh.locator('#listen-button').click();
await fresh.waitForSelector('#listen-message:not(:empty)', { timeout: 15000 }).catch(() => {});
check(/sign in/i.test(await fresh.locator('#listen-message').textContent()), 'a failed load pauses and asks to sign in again');
await fresh.unroute('**/books/*/audio/*.m4a');

const listenAt = async (chapterId) => {
  // Navigating while audio is still downloading makes WebKit report the cancelled load as a page error.
  await fresh.evaluate(() => window.distillListener?.pause());
  await fresh.waitForTimeout(1500);
  await fresh.goto(`${BASE}/books/${SLUG}/read?chapter=${chapterId}`);
  await fresh.waitForSelector('#listen-button', { state: 'visible', timeout: 15000 });
  await fresh.locator('#listen-button').click();
};
const srcEndsWith = (url) => fresh.waitForFunction((u) => (window.distillListener.audio?.src || '').endsWith(u), url, { timeout: 10000 })
  .then(() => true, () => false);

// Listen in a chapter whose audio is missing or stale starts at the next chapter that has audio.
const skipped = book.chapters[1].chapter_id;
await fresh.route('**/api/books/*/audio', async (route) => {
  const response = await route.fetch();
  const data = await response.json();
  data.chapters = data.chapters.filter((c) => c.chapter_id !== skipped);
  await route.fulfill({ response, json: data });
});
await listenAt(skipped);
check(await srcEndsWith(book.chapters[2].url), 'Listen in a chapter without audio starts at the next chapter that has it');
await fresh.unroute('**/api/books/*/audio');

// Audio that went stale while the page was open (404) skips ahead instead of asking to sign in.
await fresh.route(`**/books/*/audio/${first.chapter_id}.m4a`, (route) => route.fulfill({ status: 404, contentType: 'text/html', body: 'Not found' }));
await listenAt(first.chapter_id);
check(await srcEndsWith(book.chapters[1].url), 'audio that went stale (404) skips to the next chapter');
await fresh.unroute(`**/books/*/audio/${first.chapter_id}.m4a`);

// A dropped connection says so.
await fresh.route('**/books/*/audio/*.m4a', (route) => route.abort('internetdisconnected'));
await listenAt(first.chapter_id);
await fresh.waitForSelector('#listen-message:not(:empty)', { timeout: 15000 }).catch(() => {});
check(/offline/i.test(await fresh.locator('#listen-message').textContent()), 'a dropped connection says offline, not sign in');

check(problems.length === 0, `no page errors${problems.length ? ': ' + problems.join('; ') : ''}`);
await browser.close();
console.log(failures ? `\n${failures} failure(s)` : '\nall checks passed');
process.exit(failures ? 1 : 0);
