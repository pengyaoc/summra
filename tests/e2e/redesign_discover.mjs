// Redesign phase 4: Discover is one filterable grid of book cards.
// Level and length chips filter (combinable), the sort select reorders, the
// URL keeps ?level=&length=&sort= for deep links, and the grid is
// server-rendered so it shows without JavaScript.
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const browser = await chromium.launch({ headless: true });

let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};

const visible = (page) => page.evaluate(() => [...document.querySelectorAll("#discover-grid .book-card")]
  .filter((c) => c.offsetParent !== null)
  .map((c) => ({ level: c.dataset.level, length: c.dataset.length, minutes: Number(c.dataset.minutes) || null,
    title: c.querySelector(".book-card-title").textContent.trim() })));
const countText = (page) => page.textContent("#discover-count").then((t) => t.trim());

// 1. Server-rendered: cards present with JavaScript disabled.
const noJs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 1280, height: 900 } });
const nj = await noJs.newPage();
await nj.goto(`${BASE}/discover`);
const ssrCount = await nj.locator("#discover-grid .book-card").count();
expect("SSR: grid has cards without JS", ssrCount >= 80, `${ssrCount}`);
await nj.goto(`${BASE}/discover?level=easy`);
const ssrEasy = await visible(nj);
expect("SSR: ?level=easy filters without JS", ssrEasy.length > 0 && ssrEasy.every((c) => c.level === "easy"),
  `${ssrEasy.length}`);
await noJs.close();

const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(`${page.url()}: ${m.text()}`); });

// 2. Chips filter and combine; count and URL follow.
await page.goto(`${BASE}/discover`, { waitUntil: "networkidle" });
const all = await visible(page);
expect("all: count matches visible cards", (await countText(page)) === `${all.length} books`, await countText(page));
expect("no legacy carousels on Discover", (await page.locator("#discover-section .carousel-container").count()) === 0);

await page.click('[data-filter="level"][data-value="easy"]');
let v = await visible(page);
expect("Easy chip: only easy books", v.length > 0 && v.every((c) => c.level === "easy"), `${v.length}`);
expect("Easy chip: pressed state", (await page.getAttribute('[data-filter="level"][data-value="easy"]', "aria-pressed")) === "true");
expect("Easy chip: URL updated", new URL(page.url()).searchParams.get("level") === "easy", page.url());
expect("Easy chip: count updated", (await countText(page)) === `${v.length} book${v.length === 1 ? "" : "s"}`, await countText(page));

await page.click('[data-filter="length"][data-value="short"]');
v = await visible(page);
expect("Easy + Short: both filters apply", v.every((c) => c.level === "easy" && c.length === "short"), `${v.length}`);

// 3. Empty result shows a clear-filters message, which resets.
await page.click('[data-filter="level"][data-value="challenging"]');
await page.click('[data-filter="length"][data-value="short"]');
v = await visible(page);
if (v.length === 0) {
  expect("empty: message shown", await page.isVisible(".discover-empty"));
  await page.click(".discover-empty button");
  expect("empty: clear resets filters", (await visible(page)).length === all.length);
} else {
  expect("Challenging + Short: both filters apply", v.every((c) => c.level === "challenging" && c.length === "short"));
}

// 4. Sort.
await page.goto(`${BASE}/discover`, { waitUntil: "networkidle" });
await page.selectOption("#discover-sort", "shortest");
v = await visible(page);
const mins = v.map((c) => c.minutes).filter((m) => m !== null);
expect("sort shortest: minutes ascending", mins.every((m, i) => i === 0 || mins[i - 1] <= m));
expect("sort: URL updated", new URL(page.url()).searchParams.get("sort") === "shortest");
await page.selectOption("#discover-sort", "title");
v = await visible(page);
const titles = v.map((c) => c.title);
// Code-point order on lower-cased titles, matching the server's sort.
const lc = titles.map((t) => t.toLowerCase());
expect("sort A–Z: titles ascending", lc.every((t, i) => i === 0 || lc[i - 1] <= t));

// 5. Deep link.
await page.goto(`${BASE}/discover?level=challenging&length=long`, { waitUntil: "networkidle" });
v = await visible(page);
expect("deep link: filters applied on load", v.length > 0 && v.every((c) => c.level === "challenging" && c.length === "long"), `${v.length}`);

// 6. In-app navigation to Discover renders the grid client-side, and cards open books.
await page.goto(`${BASE}/books`, { waitUntil: "networkidle" });
await page.click("#discover-nav-btn");
await page.waitForURL(/\/discover$/);
await page.waitForFunction(() => document.querySelectorAll("#discover-grid .book-card").length > 50);
await page.click('[data-filter="level"][data-value="moderate"]');
v = await visible(page);
expect("SPA: chips work after in-app navigation", v.length > 0 && v.every((c) => c.level === "moderate"));
await page.locator("#discover-grid .book-card").filter({ visible: true }).first().click();
await page.waitForURL(/\/books\/[^/]+$/);
expect("SPA: card opens a book page", /\/books\/[^/]+$/.test(page.url()), page.url());

// 7. Mobile: no horizontal page scroll.
const mobile = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
const mp = await mobile.newPage();
await mp.goto(`${BASE}/discover`, { waitUntil: "networkidle" });
const overflow = await mp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
expect("mobile: no horizontal scroll", overflow <= 0, `${overflow}px`);
await mobile.close();

expect("no console errors", consoleErrors.length === 0, consoleErrors.join(" | "));
await browser.close();
process.exit(failed ? 1 : 0);
