// Redesign phase 3: one shared book card on Books, Categories, Discover,
// Author and "You may also like".
//
// Card contract: a real link to /books/<slug>; a 2:3 cover box that shows the
// title in serif while the image is loading (or missing); title, author, a
// level tag and a reading time; uniform heights within a grid row.
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();

let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};
const consoleErrors = [];
page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(`${page.url()}: ${msg.text()}`); });

const cardInfo = () => page.evaluate(() => [...document.querySelectorAll(".book-card")]
  .filter((c) => c.offsetParent !== null)
  .map((c) => {
    const cover = c.querySelector(".book-card-cover");
    const r = cover ? cover.getBoundingClientRect() : null;
    return {
      tag: c.tagName,
      href: c.getAttribute("href"),
      title: c.querySelector(".book-card-title")?.textContent.trim(),
      author: c.querySelector(".book-card-author")?.textContent.trim(),
      level: c.querySelector(".grade-tag, .level-tag")?.textContent.trim() || null,
      time: c.querySelector(".book-card-time")?.textContent.trim() || null,
      ratio: r && r.width ? r.height / r.width : null,
      top: Math.round(c.getBoundingClientRect().top),
      height: Math.round(c.getBoundingClientRect().height),
    };
  }));

// 1. Books grid
await page.goto(`${BASE}/books`, { waitUntil: "networkidle" });
let cards = await cardInfo();
expect("/books: renders book cards", cards.length >= 50, `${cards.length}`);
expect("/books: every card is a link to /books/<slug>",
  cards.every((c) => c.tag === "A" && /\/books\/[^/]+$/.test(c.href || "")),
  JSON.stringify(cards.find((c) => c.tag !== "A" || !/\/books\//.test(c.href || ""))));
expect("/books: every card has title and author", cards.every((c) => c.title && c.author));
expect("/books: every cover box is 2:3", cards.every((c) => c.ratio && Math.abs(c.ratio - 1.5) < 0.02),
  JSON.stringify(cards.find((c) => !c.ratio || Math.abs(c.ratio - 1.5) >= 0.02)));
const frank = cards.find((c) => c.title === "Frankenstein");
expect("/books: Frankenstein shows its reading grade and reading time",
  frank && frank.level === "Grade 12" && frank.time === "5½ hrs", JSON.stringify(frank));
expect("/books: difficulty tags are a grade (or the older level label), never empty",
  cards.every((c) => c.level === null || /^(Grade \d+|College|Easy|Moderate|Challenging)$/.test(c.level)));
const rows = {};
for (const c of cards) (rows[c.top] ||= []).push(c.height);
const ragged = Object.entries(rows).filter(([, hs]) => new Set(hs).size > 1);
expect("/books: cards in a row share one height", ragged.length === 0, JSON.stringify(ragged.slice(0, 2)));

// 2. Placeholder: with images blocked, the cover box still shows the title.
const blocked = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await blocked.route(/\/static\/covers\//, (route) => route.abort());
const bp = await blocked.newPage();
await bp.goto(`${BASE}/books`, { waitUntil: "networkidle" });
const ph = await bp.evaluate(() => {
  const c = document.querySelector(".book-card");
  const t = c?.querySelector(".book-card-cover-title");
  return t ? { text: t.textContent.trim(), visible: t.getBoundingClientRect().height > 0,
    font: getComputedStyle(t).fontFamily } : null;
});
expect("placeholder: cover shows the title in serif when the image fails",
  ph && ph.text && ph.visible && /serif/i.test(ph.font) && !/sans-serif$/.test(ph.font), JSON.stringify(ph));
await blocked.close();

// 3. Other surfaces use the same card.
for (const [path, label] of [
  ["/categories", "category shelves"],
  ["/discover", "discover shelves"],
  ["/authors/mary-shelley", "author page"],
  ["/books/frankenstein", "You may also like"],
]) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  cards = await cardInfo();
  expect(`${path}: ${label} use the shared card`, cards.length > 0 && cards.every((c) => c.tag === "A" && c.title),
    `${cards.length} cards`);
  const legacy = await page.evaluate(() =>
    document.querySelectorAll(".carousel-book-card, .related-book-card").length);
  expect(`${path}: no legacy card markup`, legacy === 0, `${legacy}`);
}

// 4. Clicking a card navigates in-app to the book page.
await page.goto(`${BASE}/books`, { waitUntil: "networkidle" });
await page.locator('.book-card[href$="/books/frankenstein"]').click();
await page.waitForURL(/\/books\/frankenstein$/);
await page.waitForSelector("#book-title");
expect("click: opens the book page", (await page.textContent("#book-title")).trim() === "Frankenstein");

// Accented slugs (louise-de-la-vallière) must route too.
await page.goto(`${BASE}/books`, { waitUntil: "networkidle" });
await page.locator(".book-card", { hasText: "Louise De La Vallière" }).click();
await page.waitForFunction(() => document.querySelector("#book-title")?.textContent.includes("Louise"));
expect("click: accented slug opens its book page",
  decodeURIComponent(new URL(page.url()).pathname).endsWith("/books/louise-de-la-vallière"), page.url());

// Direct load of an accented slug hydrates too (chapters list renders).
await page.goto(`${BASE}/books/louise-de-la-valli%C3%A8re`, { waitUntil: "networkidle" });
const louiseRows = await page.waitForFunction(() => document.querySelectorAll("#chapters-list .chapter-box").length, null, { timeout: 8000 })
  .then((h) => h.jsonValue()).catch(() => 0);
expect("direct load: accented slug renders its chapters", louiseRows > 0, `${louiseRows} rows`);

expect("no console errors", consoleErrors.length === 0, consoleErrors.join(" | "));
await browser.close();
process.exit(failed ? 1 : 0);
