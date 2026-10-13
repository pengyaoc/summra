// Redesign phase 6: home page and header search.
//  - Paper hero (no cover wall) with an original → plain-English sentence
//    pair; "Another example" cycles through the pairs
//  - "Start here" shelf uses the book card (title, level, time) with a small
//    rank badge instead of big numerals
//  - "Choose by level" cards open a filtered Discover
//  - "Continue reading" row only for signed-in readers with progress
//  - Header search: available on every page, shows covers, opens a book
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const browser = await chromium.launch({ headless: true });
let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};

const anon = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await anon.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
const page = await anon.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(`${page.url()}: ${m.text()}`); });

await page.goto(`${BASE}/`, { waitUntil: "networkidle" });

// Hero
const hero = await page.evaluate(() => {
  const h = document.querySelector(".hero-main");
  const cs = getComputedStyle(h);
  return { bg: cs.backgroundColor, img: cs.backgroundImage,
    title: document.querySelector(".hero-banner-title").textContent.trim(),
    titleFont: getComputedStyle(document.querySelector(".hero-banner-title")).fontFamily };
});
expect("hero: paper, no cover-wall image", hero.img === "none", hero.img);
const layout = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth - innerWidth,
  titleLeft: document.querySelector(".hero-banner-title").getBoundingClientRect().left,
  logoLeft: document.querySelector(".logo").getBoundingClientRect().left }));
expect("desktop: no horizontal scroll", layout.overflow <= 0, `${layout.overflow}px`);
expect("desktop: home content lines up with the header", Math.abs(layout.titleLeft - layout.logoLeft) < 60, JSON.stringify(layout));
expect("hero: serif title", /serif/.test(hero.titleFont) && !/sans-serif$/.test(hero.titleFont), hero.titleFont);
const visiblePair = () => page.evaluate(() => {
  const f = [...document.querySelectorAll(".hero-sentence")].find((x) => !x.hidden);
  return f && { original: f.querySelector(".hero-sentence-original").textContent.trim(),
    plain: f.querySelector(".hero-sentence-plain").textContent.trim() };
});
const first = await visiblePair();
expect("hero: shows an original and plain-English sentence", first && first.original && first.plain
  && first.original !== first.plain, JSON.stringify(first));
await page.click("#hero-sentence-next");
const second = await visiblePair();
expect("hero: Another example shows a different pair", second && second.original !== first.original, JSON.stringify(second));

// Start here shelf
const shelf = await page.evaluate(() => [...document.querySelectorAll("#top-10-scroll a.top-10-book-card")].map((c) => ({
  title: c.querySelector(".book-card-title")?.textContent.trim(),
  level: c.querySelector(".level-tag")?.textContent.trim(),
  time: c.querySelector(".book-card-time")?.textContent.trim(),
  rankSize: parseFloat(getComputedStyle(c.querySelector(".top-10-rank-number")).fontSize),
})));
expect("start here: cards have titles and reading times", shelf.length >= 5 && shelf.every((c) => c.title && c.time),
  JSON.stringify(shelf[0]));
expect("start here: rank is a small badge, not a big numeral", shelf.every((c) => c.rankSize <= 16), `${shelf[0]?.rankSize}px`);

// Continue reading is hidden for anonymous visitors
expect("continue reading hidden when signed out", !(await page.isVisible("#home-continue")));

// Choose by level
await page.click(".level-card--easy");
await page.waitForURL(/\/discover\?level=easy$/);
await page.waitForFunction(() => document.querySelectorAll("#discover-grid .book-card").length > 0);
const easy = await page.evaluate(() => [...document.querySelectorAll("#discover-grid .book-card")]
  .filter((c) => c.offsetParent !== null).map((c) => c.dataset.level));
expect("level card: opens Discover filtered to Easy", easy.length > 0 && easy.every((l) => l === "easy"), `${easy.length}`);
const hrefs = await page.evaluate(() => [...document.querySelectorAll("#discover-grid .book-card")].map((c) => c.getAttribute("href")));
expect("level card: Discover grid has no duplicate cards", new Set(hrefs).size === hrefs.length, `${hrefs.length} cards, ${new Set(hrefs).size} unique`);

// Cmd/Ctrl-click on a card opens a new tab and leaves this page alone.
const before = page.url();
const [popup] = await Promise.all([
  anon.waitForEvent("page", { timeout: 5000 }).catch(() => null),
  page.locator("#discover-grid .book-card").filter({ visible: true }).first().click({ modifiers: [process.platform === "darwin" ? "Meta" : "Control"] }),
]);
await page.waitForTimeout(500);
expect("modifier-click: opens a new tab", !!popup);
expect("modifier-click: current page stays put", page.url() === before, page.url());
if (popup) await popup.close();

// Header search from a non-home page (an always-visible field on desktop)
await page.goto(`${BASE}/books`, { waitUntil: "networkidle" });
await page.fill("#header-search-input", "franken");
await page.waitForSelector("#header-search-results .hero-search-result-item");
const result = await page.evaluate(() => {
  const img = document.querySelector("#header-search-results .hero-search-result-cover");
  return { text: document.querySelector("#header-search-results .hero-search-result-item").textContent, img: img && img.getAttribute("src") };
});
expect("header search: finds Frankenstein", /Frankenstein/.test(result.text), result.text);
await page.waitForFunction(() => {
  const img = document.querySelector("#header-search-results .hero-search-result-cover");
  return img && img.complete && img.naturalWidth > 0;
}, null, { timeout: 5000 }).then(() => expect("header search: result cover loads", true))
  .catch(() => expect("header search: result cover loads", false, result.img));
await page.keyboard.press("Enter");
await page.waitForURL(/\/books\/frankenstein$/);
expect("header search: Enter opens the book", true);

// Search escapes what you type
await page.goto(`${BASE}/books`, { waitUntil: "networkidle" });
await page.fill("#header-search-input", "<img src=x onerror=window.__xss=1>zz");
await page.waitForSelector("#header-search-results .hero-search-no-results");
expect("search: query is escaped", (await page.evaluate(() => window.__xss)) === undefined
  && (await page.locator("#header-search-results img").count()) === 0);

// Mobile
const mobile = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
await mobile.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
const mp = await mobile.newPage();
await mp.goto(`${BASE}/`, { waitUntil: "networkidle" });
expect("mobile: no horizontal scroll", (await mp.evaluate(() => document.documentElement.scrollWidth - innerWidth)) <= 0);
await mobile.close();

// Signed-in reader with a book in progress sees Continue reading
const signed = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await signed.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: true, user: { email: "t@example.test" } } }));
await signed.route(/\/library$/, (r) => r.request().resourceType() === "fetch"
  ? r.fulfill({ json: { success: true, finished: [], continue_reading: [{
    id: 30, slug: "frankenstein", title: "Frankenstein", author: "Mary Shelley", cover_image_url: "/static/covers/30.png",
    status: "in_progress", last_mode: "plain", furthest_percentage: 40,
    current_chapter: { chapter_number: 4, chapter_title: "Chapter 4" } }] } })
  : r.continue());
const sp = await signed.newPage();
await sp.goto(`${BASE}/`, { waitUntil: "networkidle" });
await sp.waitForSelector("#home-continue:not(.hidden) .library-card", { timeout: 5000 }).catch(() => {});
expect("signed in: Continue reading shows the book in progress",
  /Frankenstein/.test(await sp.textContent("#home-continue").catch(() => "")) && await sp.isVisible("#home-continue"));
for (const width of [1280, 375]) {
  await sp.setViewportSize({ width, height: 900 });
  await sp.waitForFunction(() => document.querySelector("#home-continue .library-card img")?.complete);
  const cover = await sp.evaluate(() => {
    const box = document.querySelector("#home-continue .library-card .book-card-cover").getBoundingClientRect();
    const img = document.querySelector("#home-continue .library-card img").getBoundingClientRect();
    return { ratio: +(box.height / box.width).toFixed(2), boxH: document.querySelector("#home-continue .library-card .book-card-cover").clientHeight, imgH: Math.round(img.height) };
  });
  expect(`continue card (${width}px): whole cover at 2:3, not cropped to the card height`,
    Math.abs(cover.ratio - 1.5) < 0.03 && Math.abs(cover.imgH - cover.boxH) <= 1, JSON.stringify(cover));
}
await signed.close();

expect("no console errors", errors.length === 0, errors.join(" | "));
await browser.close();
process.exit(failed ? 1 : 0);
