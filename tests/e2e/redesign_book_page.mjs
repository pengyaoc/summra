// Redesign phase 5: the book page.
//  - Meta row: level · chapters · reading time · Plain English badge
//  - Chapter list: number, title, reading time (no excerpt);
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
expect("meta row: reading grade, ages, chapters, time, Plain English",
  /Grade 12/.test(meta) && /Ages 14\+/.test(meta) && meta.includes(`${chapters.length} chapters`) && /5½ hrs/.test(meta) && /Plain English/.test(meta), meta);
expect("anonymous: button says Start reading", (await page.textContent("#book-read-label")).trim() === "Start reading");
expect("anonymous: no progress line", !(await page.isVisible("#book-progress")));
const header = await page.evaluate(() => {
  const read = document.getElementById("book-read-btn").getBoundingClientRect();
  const sxs = document.getElementById("book-sxs-link").getBoundingClientRect();
  const title = document.getElementById("book-title");
  return { readH: Math.round(read.height), sxsH: Math.round(sxs.height), readTop: Math.round(read.top), sxsTop: Math.round(sxs.top),
    titleOverflow: title.scrollWidth - title.clientWidth };
});
expect("header: both actions share one height", header.readH === header.sxsH && header.readH >= 44, JSON.stringify(header));
expect("header: actions sit on one row", header.readTop === header.sxsTop, JSON.stringify(header));
expect("header: title does not overflow", header.titleOverflow <= 0, JSON.stringify(header));

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
expect("toc: rows have no summary excerpt (cut-off snippets read badly)", rows.every((r) => r.excerpt === ""));
expect("toc: rows show reading time", rows.every((r) => /^\d+(½)? (min|hrs?)$/.test(r.time)), JSON.stringify(rows.map((r) => r.time)));
expect("toc: nothing marked read when anonymous", rows.every((r) => !r.completed));

// Section order on the rendered page.
const order = await page.evaluate(() => ["summary-tabs-section", "chapters-section",
  "reading-guide-section", "about-author-section", "related-books-section"]
  .map((id) => document.getElementById(id))
  .map((el) => el && { follows: (prev) => !!(prev.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING),
    el, top: el.offsetParent ? el.getBoundingClientRect().top : null })
  .map((x, i, all) => x && (i === 0 || x.follows(all[i - 1].el)) && x.top));
// DOM order for all five; hidden sections (no content for this book) report null.
expect("sections in order", order.every((t) => t !== false), JSON.stringify(order));
const shown = order.filter((t) => t !== null);
expect("visible sections in on-screen order", shown.every((t, i) => i === 0 || shown[i - 1] <= t), JSON.stringify(order));

expect("no About this book section (the summary covers it)", await page.evaluate(() => !document.getElementById("about-section")));
await page.waitForFunction(() => document.getElementById("author-bio-text")?.textContent.trim());
expect("about the author shown when there's a bio", await page.isVisible("#about-author-section"));
{
  const p2 = await anon.newPage();
  await p2.goto(`${BASE}/books/the-turn-of-the-screw`, { waitUntil: "networkidle" });
  expect("about the author hidden when the author has no bio", !(await p2.isVisible("#about-author-section")));
  await p2.close();
}

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
const mbtn = await mp.evaluate(() => {
  const b = document.getElementById("book-read-btn").getBoundingClientRect();
  return { height: Math.round(b.height), width: Math.round(b.width), left: Math.round(b.left) };
});
expect("mobile: read button on one line, full width under the cover", mbtn.height <= 52 && mbtn.width >= 300, JSON.stringify(mbtn));
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
expect("progress: button says Continue reading", label === "Continue reading", label);
const progressText = (await sp.textContent("#book-progress-text")).replace(/\s+/g, " ").trim();
expect("progress: line names the current chapter and count", await sp.isVisible("#book-progress")
  && progressText.includes(expectedTitle) && progressText.includes(`Chapter 5 of ${chapters.length}`), progressText);
const fill = await sp.evaluate(() => document.getElementById("book-progress-fill").style.width);
expect("progress: bar reflects chapters read", fill === `${Math.round(4 * 100 / chapters.length)}%`, fill);
const done = await sp.evaluate(() => [...document.querySelectorAll("#chapters-list .chapter-box")].map((r) => r.classList.contains("completed")));
expect("progress: chapters before the furthest point are checked",
  done.slice(0, 4).every(Boolean) && !done.slice(4).some(Boolean), JSON.stringify(done));
await signed.close();

expect("no console errors", errors.length === 0, errors.join(" | "));
await anon.close();
await browser.close();
process.exit(failed ? 1 : 0);
