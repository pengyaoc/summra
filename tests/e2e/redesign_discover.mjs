// Redesign phase 4: Discover is one filterable grid of book cards.
// Reading level (ATOS grade band), ages, Common Core and length chips filter
// (combinable), the sort select reorders, the URL keeps ?grade=&ages=&school=
// &length=&sort= for deep links, and the grid is
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
  .map((c) => ({ grade: c.dataset.grade, ages: c.dataset.ages, school: c.dataset.school, length: c.dataset.length,
    gradeValue: c.dataset.gradeValue === "" ? null : Number(c.dataset.gradeValue), minutes: Number(c.dataset.minutes) || null,
    title: c.querySelector(".book-card-title").textContent.trim() })));
const countText = (page) => page.textContent("#discover-count").then((t) => t.trim());

// 1. Server-rendered: cards present with JavaScript disabled.
const noJs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 1280, height: 900 } });
const nj = await noJs.newPage();
await nj.goto(`${BASE}/discover`);
const ssrCount = await nj.locator("#discover-grid .book-card").count();
expect("SSR: grid has cards without JS", ssrCount >= 80, `${ssrCount}`);
await nj.goto(`${BASE}/discover?grade=6-8`);
const ssrEasy = await visible(nj);
expect("SSR: ?grade=6-8 filters without JS", ssrEasy.length > 0 && ssrEasy.every((c) => c.grade === "6-8"),
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

await page.click('[data-filter="grade"][data-value="6-8"]');
let v = await visible(page);
expect("Grades 6–8 chip: only those books", v.length > 0 && v.every((c) => c.grade === "6-8"), `${v.length}`);
expect("Grades 6–8 chip: pressed state", (await page.getAttribute('[data-filter="grade"][data-value="6-8"]', "aria-pressed")) === "true");
expect("Grades 6–8 chip: URL updated", new URL(page.url()).searchParams.get("grade") === "6-8", page.url());
expect("Grades 6–8 chip: count updated", (await countText(page)) === `${v.length} book${v.length === 1 ? "" : "s"}`, await countText(page));

await page.click('[data-filter="ages"][data-value="ug"]');
v = await visible(page);
expect("Grades 6–8 + Ages 14+: both filters apply", v.every((c) => c.grade === "6-8" && c.ages === "ug"), `${v.length}`);

await page.click('[data-filter="grade"][data-value="all"]');
await page.click('[data-filter="ages"][data-value="all"]');
await page.click('[data-filter="school"][data-value="yes"]');
v = await visible(page);
expect("Common Core toggle: only school-list books", v.length > 0 && v.every((c) => c.school === "yes"), `${v.length}`);
await page.click('[data-filter="school"][data-value="yes"]');
expect("Common Core toggle: second press turns it off", (await visible(page)).length === all.length
  && (await page.getAttribute('[data-filter="school"][data-value="yes"]', "aria-pressed")) === "false");

// 3. Empty result shows a clear-filters message, which resets.
await page.click('[data-filter="grade"][data-value="11-12"]');
await page.click('[data-filter="length"][data-value="short"]');
v = await visible(page);
if (v.length === 0) {
  expect("empty: message shown", await page.isVisible(".discover-empty"));
  await page.click(".discover-empty button");
  expect("empty: clear resets filters", (await visible(page)).length === all.length);
} else {
  expect("Grades 11–12 + Short: both filters apply", v.every((c) => c.grade === "11-12" && c.length === "short"));
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
await page.selectOption("#discover-sort", "easiest");
const grades = (await visible(page)).map((c) => c.gradeValue);
const known = grades.filter((g) => g !== null);
expect("sort easiest: reading grade ascending, ungraded last", known.every((g, i) => i === 0 || known[i - 1] <= g)
  && grades.slice(known.length).every((g) => g === null), JSON.stringify(grades.slice(0, 8)));
await page.selectOption("#discover-sort", "title");
// Code-point order on lower-cased titles, matching the server's sort.
const lc = titles.map((t) => t.toLowerCase());
expect("sort A–Z: titles ascending", lc.every((t, i) => i === 0 || lc[i - 1] <= t));

// 5. Deep link.
await page.goto(`${BASE}/discover?grade=9-10&length=long`, { waitUntil: "networkidle" });
v = await visible(page);
expect("deep link: filters applied on load", v.length > 0 && v.every((c) => c.grade === "9-10" && c.length === "long"), `${v.length}`);

// 6. In-app navigation to Discover renders the grid client-side, and cards open books.
await page.goto(`${BASE}/categories`, { waitUntil: "networkidle" });
await page.click("#discover-nav-btn");
await page.waitForURL(/\/discover$/);
await page.waitForFunction(() => document.querySelectorAll("#discover-grid .book-card").length > 50);
await page.click('[data-filter="grade"][data-value="9-10"]');
v = await visible(page);
expect("SPA: chips work after in-app navigation", v.length > 0 && v.every((c) => c.grade === "9-10"));
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
