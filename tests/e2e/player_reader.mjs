// The player and the reader: headphones, highlight, page turns, switching books (run against Distill).
//   cd tests/e2e && BASE_URL=http://localhost:5003 node player_reader.mjs
import { webkit } from 'playwright';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const FIRST = process.env.DISTILL_LISTEN_SLUG || 'abundance-klein-thompson';
const SECOND = process.env.DISTILL_LISTEN_SLUG_2 || 'how-to-feed-the-world';
const THIRD = process.env.DISTILL_LISTEN_SLUG_3 || 'the-vital-question';
let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };
const browser = await webkit.launch({ headless: !process.env.HEADED });
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
const page = await context.newPage();
const problems = [];
page.on('pageerror', (e) => problems.push(e.message));
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.waitForURL(`${BASE}/`);

const ANCHOR = '#continuous-reader-content [data-reader-anchor]';
const openReader = async (slug) => {
  await page.goto(`${BASE}/books/${slug}`);
  await page.locator('a.home-action-primary').click();
  await page.waitForSelector(ANCHOR, { timeout: 20000 });
  await page.waitForSelector('#listen-button', { state: 'visible', timeout: 15000 });
};
const accent = () => page.locator('#listen-button').evaluate((el) => el.classList.contains('is-listening'));
const P = (fn, arg) => page.evaluate(fn, arg);
const highlighted = () => page.locator('#continuous-reader-content .listen-current').count();

await openReader(FIRST);
check(!await accent(), 'idle: the headphones are plain');
check(await page.locator('#player-mini').isHidden() && await page.locator('#player-full').isHidden(), 'idle: no player on the reader page');
await page.locator('#listen-button').click();
await page.waitForFunction(() => window.distillAudio.player.audio?.currentTime > 0.2, null, { timeout: 20000 });
check(await P(() => window.distillAudio.player.source.book.slug) === FIRST, 'idle: the headphones start this book');
check(await accent(), 'playing: the headphones turn accent');
check(await page.locator('#player-mini').isHidden() && await page.locator('#player-full').isHidden(), 'playing: still no player on the reader page');
await page.waitForFunction(() => document.querySelector('#continuous-reader-content .listen-current'), null, { timeout: 8000 }).catch(() => {});
check(await highlighted() > 0, 'the spoken sentence is highlighted when book and page match');

await page.locator('#listen-button').click();
check(await page.locator('#player-full').isVisible(), 'audio in this book: the headphones open the full player');
check(await page.locator('#player-listen-here').isHidden(), 'this book: no "Listen from here instead"');
await page.locator('#player-full-close').click();

await page.keyboard.press('ArrowRight');
await page.waitForTimeout(300);
await page.keyboard.press('ArrowRight');
await page.waitForTimeout(400);
check(await highlighted() === 0, 'turned away: the highlight stays behind');
const away = await P(() => window.distillAudio.link.reader.pagination.currentPage);
await page.waitForTimeout(1500);
check(await P(() => window.distillAudio.link.following) === false, 'turned away: following stops');
check(await P(() => window.distillAudio.link.reader.pagination.currentPage) === away, 'turned away: not pulled back');
await page.keyboard.press('ArrowLeft');
await page.waitForTimeout(300);
await page.keyboard.press('ArrowLeft');
await page.waitForTimeout(500);
check(await P(() => window.distillAudio.link.following) === true, 'paging back to the spoken page follows again');

// Another book, in the same session.
await P(() => { window.__mutations = []; const q = window.authModule.queueReaderMutation; window.authModule.queueReaderMutation = (m) => { window.__mutations.push({ book: m.book_id, src: window.distillAudio.player.audio.src }); return q(m); }; });
const firstId = await P(() => window.distillAudio.player.source.book.id);
await page.evaluate((slug) => window.distillAudio.go(`/books/${slug}/read`), SECOND);
await page.waitForFunction((slug) => location.pathname.endsWith(`/books/${slug}/read`) && window.distillAudio.link?.book?.slug === slug, SECOND, { timeout: 20000 });
await page.waitForSelector('#listen-button', { state: 'visible', timeout: 15000 });
await page.waitForTimeout(400);
check(!await P(() => window.distillAudio.player.audio.paused), 'another book: audio keeps playing');
check(await accent(), 'another book: the headphones are accent');
check(await highlighted() === 0, 'another book: no highlight');
await page.locator('#listen-button').click();
check(await page.locator('#player-full').isVisible(), 'another book: the headphones open the full player');
check(await page.locator('#player-listen-here').isVisible(), 'another book: "Listen from here instead" is offered');
check((await page.locator('#player-listen-here').innerText()).includes('Listen from here instead'), 'the label reads "Listen from here instead"');
await page.locator('#player-listen-here').click();
await page.waitForFunction((slug) => window.distillAudio.player.source.book.slug === slug && window.distillAudio.player.audio.currentTime > 0.2, SECOND, { timeout: 20000 });
const saved = await P(() => window.__mutations);
const firstSave = saved.find((m) => m.book === firstId);
check(firstSave && firstSave.src.includes(`/audio/`) && !firstSave.src.includes(`/${SECOND}/`), 'the first book\'s place is saved before the second starts');
check(await page.locator('#player-listen-here').isHidden(), 'once switched the button goes away');
await page.locator('#player-full-close').click();

// A book with no recording: no button, the player still works.
await page.route(`**/api/books/${THIRD}/audio`, (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"chapters":[]}' }));
await page.evaluate((slug) => window.distillAudio.go(`/books/${slug}/read`), THIRD);
await page.waitForFunction((slug) => window.distillAudio.link?.book?.slug === slug, THIRD, { timeout: 20000 });
await page.waitForSelector('#listen-button', { state: 'visible', timeout: 15000 });
await page.locator('#listen-button').click();
check(await page.locator('#player-listen-here').isHidden(), 'a book without a recording: no "Listen from here instead"');
const paused = await P(() => { const p = window.distillAudio.player; p.pause(); return p.playing; });
check(paused === false, 'a book without a recording: the player still works');
await page.locator('#player-full-close').click();
await P(() => window.distillAudio.player.close());
await page.waitForTimeout(200);
check(await page.locator('#listen-button').isHidden() || !await page.locator('#listen-button').count(), 'no recording and nothing playing: no headphones');

// Desktop panel: the column moves, the text does not re-flow.
const desk = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
const wide = await desk.newPage();
wide.on('pageerror', (e) => problems.push(e.message));
await wide.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await wide.goto(`${BASE}/books/${FIRST}/read`);
await wide.waitForSelector(ANCHOR, { timeout: 20000 });
await wide.waitForSelector('#listen-button', { state: 'visible', timeout: 15000 });
await wide.locator('#listen-button').click();
await wide.waitForFunction(() => window.distillAudio.player.audio?.currentTime > 0.2, null, { timeout: 20000 });
const layout = () => wide.evaluate(() => {
  const content = document.getElementById('continuous-reader-content');
  const first = content.querySelector('[data-reader-anchor]');
  const r = first.getBoundingClientRect();
  return { width: Math.round(content.getBoundingClientRect().width), pages: window.distillAudio.link.reader.pagination.pages.length, h: Math.round(r.height), w: Math.round(r.width), left: Math.round(content.getBoundingClientRect().left), right: Math.round(content.getBoundingClientRect().right), text: [...content.querySelectorAll('[data-reader-anchor]')].map((a) => a.dataset.readerAnchor).join() };
});
const shut = await layout();
await wide.locator('#listen-button').click();
await wide.waitForTimeout(450);
const open = await layout();
const panel = await wide.locator('#player-full').boundingBox();
check(open.width === shut.width && open.pages === shut.pages && open.h === shut.h && open.w === shut.w && open.text === shut.text, 'desktop panel: same width, same pages, same line breaks');
check(open.left < shut.left, 'desktop panel: the column slides left');
const textRight = await wide.evaluate(() => Math.max(...[...document.querySelectorAll('#continuous-reader-content [data-reader-anchor]')].map((a) => a.getBoundingClientRect().right)));
check(textRight <= panel.x, `desktop panel: the text clears the panel (${Math.round(textRight)} <= ${Math.round(panel.x)})`);

// Stop listening, from the full player on the reading page.
await openReader(FIRST);
await page.locator('#listen-button').click();
await page.waitForFunction(() => window.distillAudio.player.audio?.currentTime > 0.2, null, { timeout: 20000 });
await page.waitForFunction(() => document.querySelector('#continuous-reader-content .listen-current'), null, { timeout: 8000 }).catch(() => {});
const pageBeforeStop = await P(() => window.distillAudio.link.reader.pagination.currentPage);
await page.locator('#listen-button').click();
await page.locator('#player-stop').click();
await page.waitForTimeout(300);
check(await page.locator('#player-full').isHidden(), 'stop: the full player closes');
check(await P(() => !window.distillAudio.player.active && window.distillAudio.player.audio.paused), 'stop: the audio ends');
check(await highlighted() === 0, 'stop: the highlight is gone');
check(!await accent(), 'stop: the headphones are plain again');
check(await P(() => window.distillAudio.link.reader.pagination.currentPage) === pageBeforeStop, 'stop: the page stays where it was');
await page.waitForTimeout(1200);
check(await P(() => window.distillAudio.link.reader.pagination.currentPage) === pageBeforeStop, 'stop: the page no longer follows');
await page.locator('#listen-button').click();
await page.waitForFunction(() => window.distillAudio.player.audio?.currentTime > 0.2 && !window.distillAudio.player.audio.paused, null, { timeout: 20000 });
check(await accent(), 'stop: Listen starts again afterwards');
await P(() => window.distillAudio.player.pause());
await page.waitForTimeout(200);
await page.locator('#listen-button').click();
await page.locator('#player-stop').click();
await page.waitForTimeout(300);
check(await P(() => !window.distillAudio.player.active) && await highlighted() === 0, 'stop: also works while paused');

check(problems.length === 0, `no page errors${problems.length ? `: ${problems.join(' | ')}` : ''}`);
await browser.close();
console.log(failures ? `${failures} FAILED` : 'All passed');
process.exit(failures ? 1 : 0);
