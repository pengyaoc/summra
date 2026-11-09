// Distill: Listen from the home and book pages, without opening the reader. WebKit, closest to iOS Safari.
//
//   DISTILL_USER_DB=$TMPDIR/distill_listen_home.db PORT=5003 venv/bin/python -m distill.app
//   cd tests/e2e && node distill_listen_home.mjs
//
// Needs a fresh user DB and a book with rendered audio. Exits 1 on any FAIL or page error.

import { webkit } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const SLUG = process.env.DISTILL_LISTEN_SLUG || 'abundance-klein-thompson';
const SHOTS = new URL('./screenshots/', import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };

const browser = await webkit.launch({ headless: !process.env.HEADED });
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();
const problems = [];
page.on('pageerror', (e) => problems.push(e.message));

await page.goto(`${BASE}/login`);
await page.waitForURL(`${BASE}/`);
const audio = await (await page.request.get(`${BASE}/api/books/${SLUG}/audio`)).json();
const target = audio.chapters[1];

// Read a little, so the book is in progress at a chapter that has audio.
await page.goto(`${BASE}/books/${SLUG}/read?chapter=${target.chapter_id}`);
await page.waitForSelector('#continuous-reader-content [data-reader-anchor]', { timeout: 20000 });
await page.keyboard.press('ArrowRight');
await page.waitForFunction(() => window.distillListener?.reader?.continuousReader?.currentMarker, null, { timeout: 15000 });
await page.evaluate(() => window.distillListener.reader.saveContinuousReader('navigation', 1, 2));
await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });

const listen = page.locator('.home-now [data-listen-book]');
await page.waitForFunction(() => document.querySelector('.home-now [data-listen-book]')?.disabled === false, null, { timeout: 15000 });
check(await listen.innerText() === 'Listen', 'home: Listen is ready');
check(await page.locator('#listen-bar').isHidden(), 'home: no player until Listen is pressed');

await listen.click();
await page.waitForFunction(() => window.distillListener?.audio?.currentTime > 0.3, null, { timeout: 20000 });
check(await page.locator('#listen-bar').isVisible(), 'home: the player appears and audio plays');
check(await listen.innerText() === 'Pause', 'home: the button becomes Pause');
const started = await page.evaluate(() => window.distillListener.startedAt);
check(String(started).startsWith(`${target.chapter_id}.`), `home: audio starts at the reading position (${started})`);

const bar = await page.locator('#listen-bar').boundingBox();
check(Math.abs(bar.y + bar.height - 844) < 2 && bar.x === 0, 'home: the player sits along the bottom');
await page.evaluate(() => scrollTo(0, 900));
await page.waitForTimeout(200);
check(await page.locator('#listen-bar').isVisible() && !(await page.evaluate(() => window.distillListener.audio.paused)), 'home: audio keeps playing while the library scrolls');
check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'home: player fits a phone');
await page.screenshot({ path: `${SHOTS}distill_home_listening.png` });
await page.evaluate(() => scrollTo(0, 0));

// The audio moves the saved place, like listening in the reader.
const second = target.timings[target.timings.length - 1];
await page.evaluate((ms) => window.distillListener.seekToMs(ms), second.start_ms);
await page.waitForTimeout(300);
await page.evaluate(() => window.distillListener.saveAll());
await page.waitForTimeout(800);
const bookId = audio.book_id;
const state = await (await page.request.get(`${BASE}/api/progress/v2/books/${bookId}`)).json();
const marker = state.projection.modes.find((m) => m.mode === 'summary').current_marker;
check(marker.paragraph_id === second.paragraph_id, `home: listening saves the place on the server (${marker.paragraph_id})`);

await listen.click();
await page.waitForFunction(() => window.distillListener.audio.paused);
check(await listen.innerText() === 'Listen', 'home: Pause goes back to Listen');
await page.locator('#listen-close').click();
check(await page.locator('#listen-bar').isHidden(), 'home: closing hides the player');
await listen.click();
await page.waitForFunction(() => !window.distillListener.audio.paused, null, { timeout: 10000 });
check(await page.locator('#listen-bar').isVisible(), 'home: Listen after closing brings the player back');
await page.evaluate(() => window.distillListener.pause());

await page.goto(`${BASE}/books/${SLUG}`, { waitUntil: 'networkidle' });
const bookListen = page.locator('[data-listen-book]');
await page.waitForFunction(() => document.querySelector('[data-listen-book]')?.disabled === false, null, { timeout: 15000 });
await bookListen.click();
await page.waitForFunction(() => window.distillListener?.audio?.currentTime > 0.3, null, { timeout: 20000 });
check(await page.locator('#listen-bar').isVisible(), 'book page: Listen plays here too');
await page.evaluate(() => window.distillListener.pause());

check(problems.length === 0, `no page errors (${problems.join('; ')})`);
await browser.close();
console.log(failures ? `${failures} FAILED` : 'all passed');
process.exit(failures ? 1 : 0);
