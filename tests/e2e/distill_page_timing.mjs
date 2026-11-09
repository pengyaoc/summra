// Distill page timings on a phone-like connection: the budget for in-place page loading.
//
//   DISTILL_USER_DB=$TMPDIR/du.db PORT=5003 venv/bin/python -m distill.app
//   cd tests/e2e && MODE=record node distill_page_timing.mjs    # write perf/distill_baseline.json
//   cd tests/e2e && MODE=compare node distill_page_timing.mjs   # exit 1 if any metric is slower
//
// The delay comes from a small local proxy, not page.route: routing turns off the
// browser's HTTP cache, which would make full page loads look slower than they are.
import { webkit } from 'playwright';
import http from 'node:http';
import { readFileSync, writeFileSync } from 'node:fs';

const TARGET = new URL(process.env.BASE_URL || 'http://localhost:5003');
const MODE = process.env.MODE || 'compare';
const RUNS = Number(process.env.RUNS || 7);
const DELAY_MS = 150;
const NOISE_MS = 15;  // the timer's own jitter; a difference this small is not a slowdown
const FILE = new URL('./perf/distill_baseline.json', import.meta.url);

const proxy = http.createServer((req, res) => setTimeout(() => {
  const upstream = http.request({ host: TARGET.hostname, port: TARGET.port, path: req.url, method: req.method, headers: req.headers }, (up) => {
    res.writeHead(up.statusCode, up.headers);
    up.pipe(res);
  });
  upstream.on('error', () => res.destroy());
  req.pipe(upstream);
}, DELAY_MS)).listen(0);
const BASE = `http://localhost:${proxy.address().port}`;

const browser = await webkit.launch();
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();
await page.goto(`${BASE}/login`);
await page.waitForURL(`${BASE}/`);

const HOME = 'main:not(.distill-book) a[href*="/books/"]:not([href*="/read"])';
const ANCHOR = '#continuous-reader-content [data-reader-anchor]';
const timed = async (act, selector) => {
  const start = Date.now();
  await act();
  await page.locator(selector).first().waitFor({ state: 'visible', timeout: 20000 });
  return Date.now() - start;
};
// Time until the element in the middle of the reading column changes.
const turnPage = () => page.evaluate(() => new Promise((resolve) => {
  const look = () => {
    const el = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
    return `${el?.textContent?.slice(0, 80)}|${Math.round(el?.getBoundingClientRect().top ?? 0)}`;
  };
  const before = look();
  const start = performance.now();
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  const poll = () => (look() !== before || performance.now() - start > 5000)
    ? resolve(performance.now() - start) : requestAnimationFrame(poll);
  poll();
}));

const samples = { home_ms: [], book_ms: [], reader_open_ms: [], page_turn_ms: [] };
for (let run = 0; run <= RUNS; run++) {  // run 0 only warms the cache
  await page.goto(`${BASE}/`);
  const book = await timed(() => page.locator(HOME).first().click(), 'main.distill-book');
  const reader = await timed(() => page.locator('a.home-action-primary').click(), ANCHOR);
  await page.waitForTimeout(600);
  const turn = await turnPage();
  await page.goBack();
  await page.locator('main.distill-book').waitFor();
  const home = await timed(() => page.locator('a.distill-back').click(), HOME);
  if (run) Object.entries({ home_ms: home, book_ms: book, reader_open_ms: reader, page_turn_ms: turn })
    .forEach(([key, value]) => samples[key].push(value));
}
await browser.close();
proxy.close();

const median = (list) => Math.round([...list].sort((a, b) => a - b)[Math.floor(list.length / 2)]);
const result = Object.fromEntries(Object.entries(samples).map(([key, list]) => [key, median(list)]));
console.log(JSON.stringify(result));
if (MODE === 'record') {
  writeFileSync(FILE, `${JSON.stringify(result, null, 2)}\n`);
  console.log('Baseline written.');
  process.exit(0);
}
const baseline = JSON.parse(readFileSync(FILE));
let failed = 0;
for (const [key, value] of Object.entries(result)) {
  const ok = value <= baseline[key] + NOISE_MS;
  if (!ok) failed++;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${key}: ${value} ms (baseline ${baseline[key]} ms)`);
}
process.exit(failed ? 1 : 0);
