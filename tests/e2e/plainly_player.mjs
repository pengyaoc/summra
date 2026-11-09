// Plainly on the shared player. The recorded-chapter half adds only a recording, then
// expects everything Distill has: headphones, highlight, page turns, saved place.
//
//   BOOK=88 node plainly_player.mjs   (against a Plainly server on BASE_URL, using a copy of the data)
import { webkit } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.BASE_URL || 'http://localhost:5007';
const BOOK = Number(process.env.BOOK || 88);
const ROOT = new URL('../../', import.meta.url).pathname;
let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };
const chapterId = Number(execFileSync(`${ROOT}venv/bin/python`, [`${ROOT}tests/e2e/plainly_seed_recording.py`, String(BOOK), 'original', 'plain'], { cwd: ROOT, encoding: 'utf8' }).trim().split('\n').pop());
const browser = await webkit.launch({ headless: !process.env.HEADED });
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
const page = await context.newPage();
const problems = [];
page.on('pageerror', (e) => problems.push(e.message));

const books = await (await page.request.get(`${BASE}/api/books/${BOOK}`)).json();
const slug = (books.book || books).slug;
const A = (fn, arg) => page.evaluate(fn, arg);
const ANCHOR = '#continuous-reader-content [data-reader-anchor]';
await page.goto(`${BASE}/books/${slug}/read`);
await page.waitForSelector(ANCHOR, { timeout: 20000 });
await page.waitForSelector('#listen-button', { state: 'visible', timeout: 15000 });
check(true, 'a book given one recording shows the headphones');
const mode = await A(() => window.plainlyAudio.link.reader.continuousReader.mode);
await page.locator('#listen-button').click();
await page.waitForFunction(() => window.plainlyAudio.player.audio?.currentTime > 0.1, null, { timeout: 15000 });
check(true, `the recording plays (reader mode ${mode})`);
check(await page.locator('#player-mini').isHidden(), 'no player on the reader page');
await page.waitForFunction(() => document.querySelector('#continuous-reader-content .listen-current'), null, { timeout: 8000 }).catch(() => {});
check(await page.locator('#continuous-reader-content .listen-current').count() > 0, 'the spoken paragraph is highlighted');

const unitCount = await A(() => window.plainlyAudio.player.timings.length);
const target = await A((last) => { const p = window.plainlyAudio.player; p.seekToMs(p.timings[last].start_ms + 100); return p.timings[last].paragraph_id; }, unitCount - 1);
await page.waitForTimeout(500);
const onPage = await A((pid) => { const r = window.plainlyAudio.link.reader; return r.pagination.pages[r.pagination.currentPage].includes(`data-reader-anchor="${pid}"`); }, target);
check(onPage, 'the page turns to follow the audio');

await A(() => window.plainlyAudio.player.pause());
await page.waitForTimeout(400);
const saved = await A((id) => JSON.parse(Object.entries(localStorage).find(([k]) => k.startsWith(`plainly-listen-${id}-`))?.[1] || 'null'), BOOK);
check(saved?.paragraph_id === target, `the saved place is kept (${saved?.paragraph_id})`);
await A(() => window.plainlyAudio.player.close());

// Summary speech: the shared mini player, with nothing that needs chapters or timings.
await page.route('**/api/tts/generate', (route) => route.fulfill({ json: { success: true, streaming: true, audio_id: 'x', audio_urls: ['/__tone/1.m4a', '/__tone/2.m4a'] } }));
let stops = 0;
await page.route('**/api/tts/stop', (route) => { stops++; return route.fulfill({ json: { success: true } }); });
const tone = await (await page.request.get(await A(() => '')  || `${BASE}/books/${slug}/audio/${chapterId}.m4a?mode=original`)).body();
await page.route('**/__tone/*', (route) => route.fulfill({ status: 200, contentType: 'audio/mp4', body: tone }));
await A(() => window.summraApp.generateTTS('Some summary text to speak.', 'concise'));
await page.waitForFunction(() => window.plainlyAudio.player.audio.src.includes('/__tone/1') && window.plainlyAudio.player.audio.currentTime > 0.05, null, { timeout: 15000 });
check(true, 'summary speech plays through the shared player');
await page.evaluate(() => window.plainlyAudio.ui.openFull());
check(await page.locator('#player-prev').isHidden() && await page.locator('#player-chapters').isHidden(), 'summary speech has no chapter buttons');
check(await page.locator('#continuous-reader-content .listen-current').count() === 0, 'summary speech highlights nothing');
await page.locator('#player-full-close').click();
await A(() => { const a = window.plainlyAudio.player.audio; a.currentTime = a.duration; });
await page.waitForFunction(() => window.plainlyAudio.player.audio.src.includes('/__tone/2'), null, { timeout: 15000 }).catch(() => {});
check((await A(() => window.plainlyAudio.player.audio.src)).includes('/__tone/2'), 'a multi-part track plays its parts in order');

// Audio carries on while navigating in Plainly.
await page.locator('#reader-back-button').click();
await page.waitForFunction(() => !document.body.classList.contains('on-reader-page'), null, { timeout: 8000 });
await page.waitForTimeout(300);
check(!await A(() => window.plainlyAudio.player.audio.paused), 'audio continues while moving around Plainly');
check(await page.locator('#player-mini').isVisible(), 'the mini player shows outside the reader');
await page.locator('#player-mini-close').click();
await page.waitForTimeout(150);
check(stops >= 1, 'stopping tells the server to clean up generated speech');

// Side by side prefers the Plain English recording and highlights its column.
const wide = await browser.newContext({ viewport: { width: 1400, height: 900 }, serviceWorkers: 'block' });
const desk = await wide.newPage();
desk.on('pageerror', (e) => problems.push(e.message));
await desk.goto(`${BASE}/books/${slug}/read`);
await desk.waitForSelector(ANCHOR, { timeout: 20000 });
await desk.evaluate(() => window.plainlyAudio.link.reader.switchContinuousReaderMode('side_by_side'));
await desk.waitForFunction(() => window.plainlyAudio.link?.reader.continuousReader.mode === 'side_by_side' && window.plainlyAudio.link.source.tracks.length, null, { timeout: 15000 });
await desk.waitForSelector('#listen-button', { state: 'visible', timeout: 10000 });
await desk.locator('#listen-button').click();
await desk.waitForFunction(() => window.plainlyAudio.player.audio?.currentTime > 0.05, null, { timeout: 15000 });
check((await desk.evaluate(() => window.plainlyAudio.player.audio.src)).includes('mode=plain'), 'side by side plays the Plain English recording');
await desk.waitForFunction(() => document.querySelector('#continuous-reader-content .listen-current'), null, { timeout: 8000 }).catch(() => {});
check(await desk.locator('.side-by-side-cell.modern.listen-current, .side-by-side-cell.plain.listen-current').count() > 0 && await desk.locator('.side-by-side-row.listen-current').count() === 0, 'side by side highlights the matching column');

check(problems.length === 0, `no page errors${problems.length ? `: ${problems.join(' | ')}` : ''}`);
await browser.close();
console.log(failures ? `${failures} FAILED` : 'All passed');
process.exit(failures ? 1 : 0);
