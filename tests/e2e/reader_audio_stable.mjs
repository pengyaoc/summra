// The reader's text must not move because of audio: starting, pausing or closing it.
//
//   cd tests/e2e && BASE_URL=http://localhost:5003 node reader_audio_stable.mjs
import { webkit } from 'playwright';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const SLUG = process.env.DISTILL_LISTEN_SLUG || 'abundance-klein-thompson';
let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };

const measure = (page) => page.evaluate(() => {
  const content = document.getElementById('continuous-reader-content');
  const box = content.getBoundingClientRect();
  return JSON.stringify({
    contentHeight: Math.round(box.height),
    pages: window.distillAudio.link.reader.pagination.pages.length,
    anchors: [...content.querySelectorAll('[data-reader-anchor]')].map((el) => {
      const rect = el.getBoundingClientRect();
      return [el.dataset.readerAnchor, Math.round(rect.top), Math.round(rect.left), Math.round(rect.height)];
    }),
  });
});

const browser = await webkit.launch({ headless: !process.env.HEADED });
for (const [name, viewport] of [['phone', { width: 390, height: 844 }], ['desktop', { width: 1280, height: 900 }]]) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.goto(`${BASE}/login`);
  await page.goto(`${BASE}/books/${SLUG}/read`);
  await page.waitForSelector('#continuous-reader-content [data-reader-anchor]');
  await page.waitForSelector('#listen-button', { state: 'visible' });
  await page.waitForTimeout(400);
  const before = await measure(page);

  await page.locator('#listen-button').click();
  await page.waitForFunction(() => window.distillAudio?.player?.audio?.currentTime > 0.2, null, { timeout: 15000 });
  await page.waitForTimeout(200);
  check(await measure(page) === before, `${name}: text stays put when audio starts`);

  await page.evaluate(() => window.distillAudio.player.pause());
  await page.waitForTimeout(200);
  check(await measure(page) === before, `${name}: text stays put on pause`);

  await page.evaluate(() => window.distillAudio.player.close());
  await page.waitForTimeout(300);
  const after = await measure(page);
  check(after === before, `${name}: text stays put when the player closes`);
  if (after !== before) console.error(`     before ${before.slice(0, 120)}\n     after  ${after.slice(0, 120)}`);
  await context.close();
}

// A page that opens partway through a paragraph: Listen starts at that paragraph, but the page must not jump back.
{
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
  await page.goto(`${BASE}/books/${SLUG}/read`);
  await page.waitForSelector('#listen-button', { state: 'visible' });
  await page.waitForTimeout(400);
  const target = await page.evaluate(() => {
    const reader = window.distillAudio.link.reader;
    const { pages } = reader.pagination;
    const firstAnchor = (html) => /data-reader-anchor="([^"]+)"/.exec(html)?.[1];
    const index = pages.findIndex((html, i) => i > reader.pagination.currentPage && firstAnchor(html) && pages[i - 1].includes(`data-reader-anchor="${firstAnchor(html)}"`));
    return index;
  });
  for (let i = await page.evaluate(() => window.distillAudio.link.reader.pagination.currentPage); i < target; i++) {
    await page.evaluate(() => window.distillAudio.link.reader.navigateToNextPage());
    await page.waitForTimeout(150);
  }
  check(target > 0, `found a page that continues a paragraph (${target})`);
  await page.waitForTimeout(300);
  await page.locator('#listen-button').click();
  await page.waitForFunction(() => window.distillAudio?.player?.audio?.currentTime > 0.2, null, { timeout: 15000 });
  await page.waitForTimeout(300);
  const now = await page.evaluate(() => window.distillAudio.link.reader.pagination.currentPage);
  check(now === target, `Listen on a continued paragraph stays on the page (${target} -> ${now})`);
  await context.close();
}
await browser.close();
console.log(failures ? `${failures} FAILED` : 'All passed');
process.exit(failures ? 1 : 0);
