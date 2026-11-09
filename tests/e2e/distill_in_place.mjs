// Distill loads pages in place, so audio survives browsing.
//   cd tests/e2e && BASE_URL=http://localhost:5003 node distill_in_place.mjs
import { webkit } from 'playwright';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const SLUG = process.env.DISTILL_LISTEN_SLUG || 'abundance-klein-thompson';
const OTHER = process.env.DISTILL_LISTEN_SLUG_2 || 'how-to-feed-the-world';
let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };
const browser = await webkit.launch({ headless: !process.env.HEADED });
const problems = [];
async function open(options = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block', ...options });
  const page = await context.newPage();
  page.on('pageerror', (e) => problems.push(e.message));
  await page.addInitScript(() => {
    window.__listeners = 0;
    for (const target of [document, window]) {
      const add = target.addEventListener;
      const remove = target.removeEventListener;
      target.addEventListener = function (...args) { window.__listeners++; return add.apply(this, args); };
      target.removeEventListener = function (...args) { window.__listeners--; return remove.apply(this, args); };
    }
  });
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });  // WebKit reports a fetch cancelled by leaving as a page error
  await page.waitForURL(`${BASE}/`);
  return page;
}
const BOOK = 'main.distill-book';
const ANCHOR = '#continuous-reader-content [data-reader-anchor]';
const page = await open();
await page.evaluate(() => { window.__stamp = 'kept'; });
const stamped = async (msg) => check(await page.evaluate(() => window.__stamp) === 'kept', msg);

await page.goto(`${BASE}/books/${SLUG}`);
await page.evaluate(() => { window.__stamp = 'kept'; });
await page.waitForFunction(() => document.querySelector('[data-listen-book]')?.disabled === false, null, { timeout: 20000 });
await page.locator('[data-listen-book]').click();
await page.waitForFunction(() => window.distillAudio?.player?.audio?.currentTime > 0.2, null, { timeout: 20000 });
const clockRises = async (msg) => {
  const a = await page.evaluate(() => window.distillAudio.player.audio.currentTime);
  await page.waitForTimeout(700);
  const b = await page.evaluate(() => window.distillAudio.player.audio.currentTime);
  check(b > a, `${msg} (${a.toFixed(1)} -> ${b.toFixed(1)})`);
};
await page.locator('a.distill-back').click();
await page.waitForFunction(() => !document.querySelector('main.distill-book') && document.querySelector('main a[href*="/books/"]'));
await stamped('book -> home: no page reload');
await clockRises('book -> home: audio keeps playing');
check(new URL(page.url()).pathname === '/', 'home: the address is right');
check((await page.title()) === 'Distill', `home: the title is right (${await page.title()})`);
check(await page.locator('#player-mini').isVisible(), 'home: the mini player shows');

const firstBook = page.locator('main a[href*="/books/"]:not([href*="/read"])').first();
const href = await firstBook.getAttribute('href');
await firstBook.click();
await page.waitForSelector(BOOK);
await stamped('home -> book: no page reload');
await clockRises('home -> book: audio keeps playing');
check(page.url().includes(href.split('?')[0]), 'book: the address is right');
check((await page.title()).endsWith('· Distill'), 'book: the title is right');

await page.locator('a.home-action-primary').click();
await page.waitForSelector(ANCHOR, { timeout: 20000 });
await stamped('book -> reader: no page reload');
await clockRises('book -> reader: audio keeps playing');
check(await page.locator('#player-mini').isHidden(), 'reader: no mini player');
check(await page.evaluate(() => document.body.classList.contains('on-reader-page')), 'reader: the body class is set');

await page.goBack();
await page.waitForSelector(BOOK);
await stamped('Back to the book: no page reload');
await clockRises('Back: audio keeps playing');
check(await page.locator('#continuous-reader-section').isHidden(), 'Back: the reader is gone');
check(!await page.evaluate(() => document.body.classList.contains('on-reader-page')), 'Back: the reader body class is gone');
await page.goBack();
await page.waitForFunction(() => !document.querySelector('main.distill-book') && document.querySelector('main a[href*="/books/"]'));
await stamped('Back to home: no page reload');

// Library filters and the suggestions script still work after returning.
const input = page.locator('.distill-filters [name="q"]');
await input.fill('abun');
await page.waitForSelector('#distill-search-options li', { timeout: 3000 }).catch(() => {});
check(await page.locator('#distill-search-options li').count() > 0, 'search suggestions work after coming back');
await input.fill('');
await page.locator('.distill-filters').evaluate((form) => { form.querySelector('[name="q"]').value = 'the'; form.requestSubmit(); });
await page.waitForFunction(() => location.search.includes('q=the'), null, { timeout: 8000 });
await stamped('a filter applies in place');
const filteredCount = await page.locator('main a[href*="/books/"]').count();

// Back and Forward restore filters and scroll.
await page.evaluate(() => scrollTo(0, 300));
await page.waitForTimeout(100);
const scrolled = await page.evaluate(() => scrollY);
await page.locator('main a[href*="/books/"]:not([href*="/read"])').first().click();
await page.waitForSelector(BOOK);
await page.goBack();
await page.waitForFunction(() => location.search.includes('q=the') && !document.querySelector('main.distill-book'));
await page.waitForTimeout(150);
check(await page.evaluate(() => document.querySelector('.distill-filters [name="q"]').value) === 'the', 'Back keeps the filter');
check(await page.locator('main a[href*="/books/"]').count() === filteredCount, 'Back shows the same filtered shelf');
check(Math.abs(await page.evaluate(() => scrollY) - scrolled) < 3 || scrolled === 0, 'Back restores the scroll position');
await page.goForward();
await page.waitForSelector(BOOK);
check(true, 'Forward works');
await page.goBack();
await page.waitForFunction(() => !document.querySelector('main.distill-book'));

// Rapid taps: only the last page appears.
await page.route(`**/books/${SLUG}`, async (route) => { await new Promise((r) => setTimeout(r, 700)); await route.continue(); });
await page.evaluate(([one, two]) => { window.distillAudio.go(`/books/${one}`); window.distillAudio.go(`/books/${two}`); }, [SLUG, OTHER]);
await page.waitForFunction((slug) => location.pathname === `/books/${slug}`, OTHER, { timeout: 8000 });
await page.waitForTimeout(1000);
check(new URL(page.url()).pathname === `/books/${OTHER}` && (await page.locator('h1').first().innerText()).length > 0, 'two quick taps: only the last page appears');
const shownSlug = await page.locator('a.home-action-primary').getAttribute('href');
check(shownSlug.includes(OTHER), 'two quick taps: the content is the last page');
await page.unroute(`**/books/${SLUG}`);

// Reader open/close cycles do not pile up listeners.
await page.evaluate(() => window.distillAudio.player.close());
const cycle = async () => {
  await page.evaluate((slug) => window.distillAudio.go(`/books/${slug}/read`), SLUG);
  await page.waitForSelector(ANCHOR, { timeout: 20000 });
  await page.waitForTimeout(50);
  await page.evaluate((slug) => window.distillAudio.go(`/books/${slug}`), SLUG);
  await page.waitForSelector(BOOK);
};
await cycle();
const start = await page.evaluate(() => window.__listeners);
for (let i = 0; i < 20; i++) await cycle();
const growth = await page.evaluate(() => window.__listeners) - start;
check(growth <= 2, `20 reader open/close cycles add no listeners (grew by ${growth})`);

// Sign-in expired: the audio place is saved, then an ordinary load.
const expired = await open();
await expired.goto(`${BASE}/books/${SLUG}`);
await expired.waitForFunction(() => document.querySelector('[data-listen-book]')?.disabled === false, null, { timeout: 20000 });
await expired.locator('[data-listen-book]').click();
await expired.waitForFunction(() => window.distillAudio?.player?.audio?.currentTime > 0.5, null, { timeout: 20000 });
await expired.evaluate(() => { window.__marker = 'alive'; localStorage.removeItem(`distill-listen-${window.distillAudio.player.source.book.id}`); sessionStorage.setItem('wasSaved', ''); const s = window.distillAudio.player.saveAll.bind(window.distillAudio.player); window.distillAudio.player.saveAll = () => { sessionStorage.setItem('wasSaved', 'yes'); return s(); }; });
await expired.route(`${BASE}/`, (route) => route.request().headers()['x-requested-with'] ? route.fulfill({ status: 401, body: 'Sign in' }) : route.continue());
await expired.locator('a.distill-back').click();
await expired.waitForFunction(() => !window.__marker, null, { timeout: 8000 });
check(await expired.evaluate(() => sessionStorage.getItem('wasSaved')) === 'yes', '401: the audio place is saved before the full load');
await expired.unroute(`${BASE}/`);

// Network failure: an ordinary load.
const offline = await open();
await offline.evaluate(() => { window.__marker = 'alive'; });
const link = offline.locator('main a[href*="/books/"]:not([href*="/read"])').first();
await offline.route('**/books/**', (route) => route.request().headers()['x-requested-with'] ? route.abort('internetdisconnected') : route.continue());
await link.click();
await offline.waitForFunction(() => !window.__marker && document.querySelector('main.distill-book'), null, { timeout: 8000 });
check(true, 'a failed fetch does a full load');

// Kindle gets ordinary pages.
const kindle = await browser.newContext({ userAgent: 'Mozilla/5.0 (X11; U; Linux armv7l like Android; en-us) AppleWebKit/531.2+ (KHTML, like Gecko) Version/5.0 Safari/533.2+ Kindle/3.0+' });
const kpage = await kindle.newPage();
await kpage.goto(`${BASE}/login`);
const scripts = await kpage.evaluate(() => [...document.scripts].map((s) => s.src).join());
check(!scripts.includes('page_swap') && !scripts.includes('distill_shell'), 'Kindle: no in-place loading');

check(problems.length === 0, `no page errors${problems.length ? `: ${problems.join(' | ')}` : ''}`);
await browser.close();
console.log(failures ? `${failures} FAILED` : 'All passed');
process.exit(failures ? 1 : 0);
