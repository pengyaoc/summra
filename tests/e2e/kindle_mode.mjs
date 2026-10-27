// Kindle e-ink mode: a Kindle user agent gets the paginated, tap-to-turn
// reader; a desktop browser keeps the SPA.
//
//   BASE_URL=http://localhost:5001 node kindle_mode.mjs
//
// Screenshots land in ./screenshots/kindle_*.png.

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const shots = join(here, "screenshots");
await mkdir(shots, { recursive: true });

const base = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const SLUG = process.env.KINDLE_SLUG || "pride-and-prejudice";
const KINDLE_UA =
  "Mozilla/5.0 (X11; U; Linux armv7l like Android; en-us) AppleWebKit/531.2+ " +
  "(KHTML, like Gecko) Version/5.0 Safari/533.2+ Kindle/3.0+";

const failures = [];
const check = (ok, label) => {
  console.log(`${ok ? "PASS" : "FAIL"} ${label}`);
  if (!ok) failures.push(label);
};

const browser = await chromium.launch({ headless: !process.env.HEADED });
// Paperwhite's browser viewport is roughly 758x1024 CSS px under its toolbar.
const ctx = await browser.newContext({ userAgent: KINDLE_UA, viewport: { width: 758, height: 950 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

// Library
await page.goto(`${base}/`);
check(await page.locator("html.kindle").count() === 1, "home is the Kindle library");
check(await page.locator('script[src*="app.min.js"], script[src*="/app.js"]').count() === 0, "SPA bundle not loaded");
check(await page.locator(".list li a").count() > 0, "library lists books");
await page.screenshot({ path: join(shots, "kindle_library.png") });

// Book page
await page.goto(`${base}/books/${SLUG}`);
check(await page.locator("h1").count() === 1, "book page has a title");
check(await page.locator(".contents li").count() > 0, "book page lists chapters");
await page.screenshot({ path: join(shots, "kindle_book.png") });

// Reader
await ctx.clearCookies();
await page.goto(`${base}/books/${SLUG}/read?ch=1&text=plain`);
const vp = page.viewportSize();
const noScroll = await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight + 1);
check(noScroll, "reader page does not scroll");
const footer = async () => (await page.locator("#foot").innerText()).trim();
const flowLeft = () => page.evaluate(() => document.getElementById("flow").style.left);
const cancelsDrag = async (selector) => page.locator(selector).evaluate((el) =>
  !el.dispatchEvent(new Event("touchmove", { bubbles: true, cancelable: true })));
check(await cancelsDrag("#viewport"), "touch drag cannot pan the document on initial load");
check(await cancelsDrag("body"), "touch drag in the reader gutter cannot pan the document");
check(/%/.test(await footer()), "footer shows progress");
await page.screenshot({ path: join(shots, "kindle_reader_p1.png") });

const left0 = await flowLeft();
await page.mouse.click(vp.width * 0.8, vp.height / 2);
const left1 = await flowLeft();
check(left0 !== left1, `tap right turns the page (${left0} -> ${left1})`);
await page.screenshot({ path: join(shots, "kindle_reader_p2.png") });
await page.mouse.click(vp.width * 0.1, vp.height / 2);
check((await flowLeft()) === left0, "tap left goes back");

// No line is cut at the page's bottom edge: every visible line box is inside the viewport.
const cut = await page.evaluate(() => {
  const v = document.getElementById("viewport").getBoundingClientRect();
  let bad = 0;
  for (const p of document.querySelectorAll("#flow p")) {
    for (const r of p.getClientRects()) {
      if (r.right <= v.left || r.left >= v.right) continue; // other pages
      if (r.bottom > v.bottom + 1 || r.top < v.top - 1) bad++;
    }
  }
  return bad;
});
check(cut === 0, `no text cut at page edges (${cut})`);

// Menu
await page.mouse.click(vp.width / 2, 20);
check(await page.locator("#menu:not(.hidden)").count() === 1, "top tap opens the menu");
check(await cancelsDrag(".menu-bottom"), "font banner cancels document panning while open");
await page.screenshot({ path: join(shots, "kindle_menu.png") });
const pagesBefore = await page.locator("#menu-pos").innerText();
await page.click("#bigger");
const pagesAfter = await page.locator("#menu-pos").innerText();
check(pagesBefore !== pagesAfter, `A+ re-paginates (${pagesBefore} -> ${pagesAfter})`);
check(await cancelsDrag(".menu-bottom"), "font adjustment keeps touch-drag protection");
check((await ctx.cookies()).some((c) => c.name === "kfs" && c.value === "4"), "font size remembered");
await page.click("#close");
check(await page.locator("#menu.hidden").count() === 1, "close hides the menu");
check(await cancelsDrag("#viewport"), "closing the font banners keeps touch-drag protection");

// Some legacy Kindle WebKit builds report window dimensions that include
// chrome/content overflow. The reading rectangle must still fit the CSS viewport.
await page.evaluate(() => {
  window.__kindleWindowDimensions = {
    innerWidth: Object.getOwnPropertyDescriptor(window, "innerWidth"),
    innerHeight: Object.getOwnPropertyDescriptor(window, "innerHeight"),
  };
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 9000 });
  Object.defineProperty(window, "innerHeight", { configurable: true, value: 4000 });
  window.dispatchEvent(new Event("resize"));
});
await page.waitForTimeout(300);
const fitsViewport = await page.evaluate(({ width, height }) => {
  const reading = document.getElementById("viewport").getBoundingClientRect();
  const footer = document.getElementById("foot").getBoundingClientRect();
  return reading.width > 0 && reading.height > 0 && reading.left >= 0 && reading.right <= width
    && reading.top >= 0 && reading.bottom <= footer.top + 1 && footer.bottom <= height + 1;
}, vp);
check(fitsViewport, "reader and footer fit even when window dimensions are misleading");
await page.evaluate(() => {
  Object.defineProperties(window, window.__kindleWindowDimensions);
  delete window.__kindleWindowDimensions;
  window.dispatchEvent(new Event("resize"));
});
await page.waitForTimeout(300);

// Paging past the last page opens the next chapter.
for (let i = 0; i < 200 && page.url().includes("ch=1&"); i++) {
  await page.mouse.click(vp.width * 0.8, vp.height / 2);
  await page.waitForTimeout(20);
}
await page.waitForLoadState("load");
check(/ch=2/.test(page.url()), `last page turns to chapter 2 (${page.url()})`);
check((await ctx.cookies()).some((c) => c.name === "kpos_" + "" || c.name.startsWith("kpos_")), "position saved");

// Back from chapter 2's first page lands on chapter 1's last page.
await page.mouse.click(vp.width * 0.1, vp.height / 2);
await page.waitForLoadState("load");
await page.waitForTimeout(100);
const atEnd = await page.locator("#left").innerText();
check(/ch=1/.test(page.url()) && /End of chapter/.test(atEnd), `back from chapter 2 opens end of chapter 1 (${atEnd})`);
await page.screenshot({ path: join(shots, "kindle_reader_end.png") });

// Switching to the original keeps the paragraph.
await page.mouse.click(vp.width / 2, 20);
const posCookie = async () => (await ctx.cookies()).find((c) => c.name.startsWith("kpos_"))?.value;
const plainPara = Number((await posCookie()).split(".")[1]);
await Promise.all([page.waitForNavigation(), page.click("a.keep:not(.on)")]);
await page.waitForTimeout(100);
check(/text=original/.test(page.url()), "switched to original");
const shown = await page.evaluate((i) => {
  const v = document.getElementById("viewport").getBoundingClientRect();
  const p = document.querySelector(`#flow p[data-i="${i}"]`);
  return !!p && [...p.getClientRects()].some((r) => r.left >= v.left - 1 && r.left < v.right);
}, plainPara);
check(shown, `original opens on the same paragraph (${plainPara})`);
await page.screenshot({ path: join(shots, "kindle_reader_original.png") });

// Signed in (local dev runs auth "off", which counts as signed in): a page
// turn is saved to the account, the web reader's API sees it, and reopening
// the book resumes there.
await page.goto(`${base}/books/${SLUG}/read?ch=3&text=plain`);
if (await page.locator("body[data-sync]").count()) {
  const bookId = await page.locator("body").getAttribute("data-book");
  const saved = page.waitForResponse((r) => r.url().includes("/api/kindle/progress") && r.request().method() === "POST");
  await page.mouse.click(vp.width * 0.8, vp.height / 2);
  const resp = await saved;
  check(resp.status() === 200, `page turn saved to account (HTTP ${resp.status()})`);
  const para = Number((await posCookie()).split(".")[1]);
  const projection = await page.evaluate(async (id) => (await (await fetch(`${location.pathname.split("/books/")[0]}/api/progress/v2/books/${id}`)).json()).projection, bookId);
  const plain = projection.modes.find((m) => m.mode === "plain");
  check(projection.book.last_mode === "plain" && plain.current_marker.paragraph_id.endsWith(`.${para}`),
    `web reader API has the Kindle position (${plain && plain.current_marker.paragraph_id}, paragraph ${para})`);
  await page.goto(`${base}/books/${SLUG}/read`);
  check((await page.locator("body").getAttribute("data-ch")) === "3", "reopening the book resumes at the synced chapter");
} else {
  console.log("SKIP sync checks (signed out)");
}

check(errors.length === 0, `no page errors (${errors.join(" | ")})`);

// Emulate the PW3's *reported* metrics (its visible area is smaller). Real
// native drag behavior needs the physical device; this guards profile selection.
const nativeContext = await browser.newContext({
  userAgent: KINDLE_UA, viewport: { width: 1072, height: 1268 },
  screen: { width: 1072, height: 1448 }, hasTouch: false,
});
const nativePage = await nativeContext.newPage();
await nativePage.goto(`${base}/books/${SLUG}/read?ch=1&text=plain`);
check(await nativePage.locator("html.native-pw3").count() === 1, "legacy PW3 selects native viewport workaround");
const nativeGeometry = await nativePage.evaluate(() => ({
  width: document.body.clientWidth, height: document.body.clientHeight,
  shell: document.getElementById("reader-shell").offsetHeight,
  overflow: getComputedStyle(document.getElementById("reader-shell")).overflow,
}));
check(nativeGeometry.width > 1072 && nativeGeometry.height === 1260
  && nativeGeometry.shell === 1279 && nativeGeometry.overflow === "scroll", "PW3 uses its measured nested viewport");
await nativeContext.close();

// Desktop is unaffected.
const desk = await browser.newPage();
await desk.goto(`${base}/`);
check(await desk.locator("html.kindle").count() === 0, "desktop browser keeps the normal site");

await browser.close();
console.log(failures.length ? `\n${failures.length} FAILED` : "\nall checks passed");
process.exit(failures.length ? 1 : 0);
