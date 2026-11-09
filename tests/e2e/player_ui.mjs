// Shared player UI: mini player and full player, on a phone and on desktop (run against Distill).
//   cd tests/e2e && BASE_URL=http://localhost:5003 node player_ui.mjs
import { webkit } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const SLUG = process.env.DISTILL_LISTEN_SLUG || 'abundance-klein-thompson';
const SHOTS = new URL('./screenshots/', import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });
let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };
const browser = await webkit.launch({ headless: !process.env.HEADED });
const problems = [];

async function bookPage(viewport, prepare) {
  const context = await browser.newContext({ viewport, serviceWorkers: 'block' });
  const page = await context.newPage();
  page.on('pageerror', (e) => problems.push(e.message));
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });  // WebKit reports a fetch cancelled by leaving as a page error
  await prepare?.(page);
  await page.goto(`${BASE}/books/${SLUG}`);
  await page.waitForFunction(() => document.querySelector('[data-listen-book]')?.disabled === false, null, { timeout: 20000 });
  await page.locator('[data-listen-book]').click();
  await page.waitForFunction(() => window.distillAudio?.player?.audio?.currentTime > 0.2, null, { timeout: 20000 });
  return page;
}
const box = (page, selector) => page.locator(selector).boundingBox();
const near = (a, b, within = 2) => Math.abs(a - b) <= within;
const currentMs = (page) => page.evaluate(() => window.distillAudio.player.position().ms);

// Phone
const phone = await bookPage({ width: 390, height: 844 });
let mini = await box(phone, '#player-mini');
check(mini && near(mini.y + mini.height, 844) && mini.x === 0 && near(mini.width, 390), 'phone: the mini player runs along the bottom edge');
check(await phone.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'phone: the mini player fits');
await phone.screenshot({ path: `${SHOTS}player_mini_phone.png` });
await phone.locator('#player-mini-open').click();
let full = await box(phone, '#player-full');
check(full && near(full.width, 390) && near(full.height, 844) && full.x === 0, 'phone: the full player fills the screen');
await phone.screenshot({ path: `${SHOTS}player_full_phone.png` });
await phone.evaluate(() => window.distillAudio.player.seekToMs(60000));
await phone.waitForTimeout(200);
let before = await currentMs(phone);
await phone.locator('#player-back').click();
await phone.waitForTimeout(100);
check(near(await currentMs(phone), before - 15000, 1500), 'back goes 15 seconds');
before = await currentMs(phone);
await phone.locator('#player-fwd').click();
await phone.waitForTimeout(100);
check(near(await currentMs(phone), before + 30000, 1500), 'forward goes 30 seconds');
const rates = [];
for (let i = 0; i < 5; i++) { await phone.locator('#player-rate').click(); rates.push(await phone.locator('#player-rate').innerText()); }
check(rates.join(' ') === '1.25× 1.5× 1.75× 2× 1×', `speed cycles (${rates.join(' ')})`);
check(await phone.locator('#player-prev').isVisible() && await phone.locator('#player-next').isVisible() && await phone.locator('#player-chapters').isVisible(),
  'a book with several chapters has chapter buttons');
await phone.locator('#player-chapters').click();
await phone.locator('#player-chapter-list button').nth(1).click();
await phone.waitForFunction(() => window.distillAudio.player.index === 1, null, { timeout: 8000 });
check(true, 'Chapters jumps to the chosen chapter');
await phone.locator('#player-full-close').click();
check(await phone.locator('#player-full').isHidden() && await phone.locator('#player-mini').isVisible(), 'the down arrow closes the full player');
await phone.locator('#player-mini-close').click();
check(await phone.locator('#player-mini').isHidden(), 'closing hides the mini player');
await phone.waitForTimeout(100);
check(await phone.evaluate(() => { const p = window.distillAudio.player; return p.audio.paused && !p.active; }), 'closing stops the audio and ends the silent hold');

// Desktop
const desktop = await bookPage({ width: 1280, height: 900 });
mini = await box(desktop, '#player-mini');
check(mini && mini.width <= 370 && near(mini.x + mini.width, 1280, 40) && near(mini.y + mini.height, 900, 40) && mini.x > 800, `desktop: the mini player is a card at the bottom right (${JSON.stringify(mini)})`);
await desktop.screenshot({ path: `${SHOTS}player_mini_desktop.png` });
await desktop.locator('#player-mini-open').click();
full = await box(desktop, '#player-full');
check(full && near(full.x + full.width, 1280) && full.width < 460 && near(full.height, 900), 'desktop: the full player is a right-edge panel');
check(await desktop.locator('.player-scrim').count() === 0, 'desktop: no dimming behind the panel');
await desktop.screenshot({ path: `${SHOTS}player_full_desktop.png` });
await desktop.setViewportSize({ width: 1000, height: 800 });
await desktop.waitForTimeout(100);
full = await box(desktop, '#player-full');
check(full && near(full.x + full.width, 1000) && full.width < 460, 'at 1000 px the panel lies over the page');

// One track: no chapter controls.
const single = await bookPage({ width: 390, height: 844 }, (page) => page.route('**/api/books/*/audio', async (route) => {
  const response = await route.fetch();
  const data = await response.json();
  data.chapters = data.chapters.slice(-1);  // the last chapter, so it is after any saved place
  await route.fulfill({ response, json: data });
}));
await single.locator('#player-mini-open').click();
check(await single.locator('#player-prev').isHidden() && await single.locator('#player-next').isHidden() && await single.locator('#player-chapters').isHidden(),
  'one track: previous, next and Chapters are hidden');

check(problems.length === 0, `no page errors${problems.length ? `: ${problems.join(' | ')}` : ''}`);
await browser.close();
console.log(failures ? `${failures} FAILED` : 'All passed');
process.exit(failures ? 1 : 0);
