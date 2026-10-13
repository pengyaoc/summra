// Redesign phase 5: the book page.
//  - Meta row: level · chapters · reading time · Plain English badge
//  - Chapter list: number, title, one-line summary excerpt, reading time;
//    rows are links that open the continuous reader at that chapter
//    (the same reader a direct /books/<slug>/chapters/<n> load opens)
//  - "Read side by side" opens the reader in side-by-side mode
//  - Signed-in progress (v2 reader state): button reads "Continue · …" and
//    chapters before the furthest point carry a checkmark
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const SLUG = "frankenstein";
const browser = await chromium.launch({ headless: true });

let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};

const api = await (await fetch(`${BASE}/api/books/${30}/chapters`)).json();
const chapters = api.sections.flatMap((s) => s.chapters);

// Anonymous visitor (auth check mocked so the result doesn't depend on who runs it).
const anon = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await anon.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
const page = await anon.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(`${page.url()}: ${m.text()}`); });

await page.goto(`${BASE}/books/${SLUG}`, { waitUntil: "networkidle" });
const meta = (await page.textContent("#book-meta")).replace(/\s+/g, " ").trim();
expect("meta row: level, chapters, time, Plain English",
  /Challenging/.test(meta) && meta.includes(`${chapters.length} chapters`) && /5½ hrs/.test(meta) && /Plain English/.test(meta), meta);
expect("anonymous: button says Start reading", (await page.textContent("#book-read-label")).trim() === "Start reading");

const rows = await page.evaluate(() => [...document.querySelectorAll("#chapters-list .chapter-box")].map((r) => ({
  tag: r.tagName, href: r.getAttribute("href"),
  title: r.querySelector(".chapter-box-title")?.textContent.trim(),
  excerpt: r.querySelector(".chapter-box-excerpt")?.textContent.trim() || "",
  time: r.querySelector(".chapter-box-time")?.textContent.trim() || "",
  completed: r.classList.contains("completed"),
})));
expect("toc: one row per chapter", rows.length === chapters.length, `${rows.length}/${chapters.length}`);
expect("toc: rows link to chapter URLs",
  rows.every((r, i) => r.tag === "A" && r.href.endsWith(`/books/${SLUG}/chapters/${chapters[i].chapter_number}`)),
  JSON.stringify(rows[0]));
expect("toc: rows show summary excerpts", rows.filter((r) => r.excerpt.length > 20).length >= rows.length - 1);
expect("toc: rows show reading time", rows.every((r) => /^\d+(½)? (min|hrs?)$/.test(r.time)), JSON.stringify(rows.map((r) => r.time)));
expect("toc: nothing marked read when anonymous", rows.every((r) => !r.completed));

// Section order on the rendered page.
const order = await page.evaluate(() => ["about-section", "summary-tabs-section", "chapters-section",
  "reading-guide-section", "about-author-section", "related-books-section"]
  .map((id) => document.getElementById(id))
  .map((el) => el && { follows: (prev) => !!(prev.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING),
    el, top: el.offsetParent ? el.getBoundingClientRect().top : null })
  .map((x, i, all) => x && (i === 0 || x.follows(all[i - 1].el)) && x.top));
// DOM order for all six; hidden sections (no content for this book) report null.
expect("sections in order", order.every((t) => t !== false), JSON.stringify(order));
const shown = order.filter((t) => t !== null);
expect("visible sections in on-screen order", shown.every((t, i) => i === 0 || shown[i - 1] <= t), JSON.stringify(order));

// Clicking a chapter opens the continuous reader at that chapter.
await page.locator("#chapters-list .chapter-box").nth(3).click();
await page.waitForURL(new RegExp(`/books/${SLUG}/chapters/${chapters[3].chapter_number}$`));
await page.waitForFunction(() => !document.getElementById("continuous-reader-section").classList.contains("hidden"));
const legacyShown = await page.evaluate(() => !document.getElementById("chapter-detail-section").classList.contains("hidden"));
expect("toc click: opens the continuous reader, not the old chapter view", !legacyShown);
await page.waitForFunction(() => window.summraApp?.continuousReader?.active);
const chapterId = await page.evaluate(() => window.summraApp.continuousReader.chapterId
  ?? window.summraApp.currentContinuousChapterId?.());
expect("toc click: reader is at that chapter", chapterId == null || Number(chapterId) === chapters[3].id, `${chapterId}`);

// "Read side by side".
await page.goto(`${BASE}/books/${SLUG}`, { waitUntil: "networkidle" });
await page.click("#book-sxs-link");
await page.waitForURL(/\/read\?mode=side_by_side$/);
await page.waitForFunction(() => window.summraApp?.continuousReader?.active);
expect("side by side: reader opens in side-by-side mode",
  (await page.evaluate(() => window.summraApp.continuousReader.mode)) === "side_by_side");

// Mobile: no side-by-side link (the reader only allows it on wide screens).
const mobile = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
const mp = await mobile.newPage();
await mp.goto(`${BASE}/books/${SLUG}`, { waitUntil: "networkidle" });
expect("mobile: side-by-side link hidden", !(await mp.isVisible("#book-sxs-link")));
expect("mobile: no horizontal scroll", (await mp.evaluate(() => document.documentElement.scrollWidth - innerWidth)) <= 0);
await mobile.close();

// Signed-in reader with progress: furthest point in chapter index 4, last at index 4.
const signed = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await signed.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: true, user: { email: "t@example.test" } } }));
const marker = { chapter_id: chapters[4].id, paragraph_id: "p0", offset: 0, word_position: 1, content_version: 1 };
await signed.route(/\/progress\/v2\/books\/30$/, (r) => r.fulfill({ json: { success: true, projection: {
  book: { status: "in_progress", last_mode: "plain" },
  modes: [{ mode: "plain", current_marker: marker, furthest_marker: marker }],
} } }));
const sp = await signed.newPage();
await sp.goto(`${BASE}/books/${SLUG}`, { waitUntil: "networkidle" });
await sp.waitForFunction(() => /Continue/.test(document.getElementById("book-read-label").textContent));
const label = (await sp.textContent("#book-read-label")).trim();
const expectedTitle = chapters[4].chapter_title || `Chapter ${chapters[4].chapter_number}`;
expect("progress: button continues at the current chapter", label === `Continue · ${expectedTitle}`, label);
const done = await sp.evaluate(() => [...document.querySelectorAll("#chapters-list .chapter-box")].map((r) => r.classList.contains("completed")));
expect("progress: chapters before the furthest point are checked",
  done.slice(0, 4).every(Boolean) && !done.slice(4).some(Boolean), JSON.stringify(done));
await signed.close();

expect("no console errors", errors.length === 0, errors.join(" | "));
await anon.close();
await browser.close();
process.exit(failed ? 1 : 0);
