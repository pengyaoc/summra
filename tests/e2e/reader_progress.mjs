// Reading progress moves as you read.
//
// Bug this guards against: the reader's progress (footer % and bar, Library
// %, book-page checkmarks) came from the "furthest" marker, which only
// advanced on a page turn whose first paragraph was exactly the next
// paragraph number. A page holds several paragraphs (and long ones span
// pages), so ordinary page turns almost never qualified and progress sat at
// 0%. Now the footer shows the current position, and a forward page turn
// is what counts as sequential reading.
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const browser = await chromium.launch({ headless: true });
let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};
const progress = (page) => page.evaluate(() => ({
  text: document.getElementById("continuous-reader-progress").textContent.trim(),
  width: document.getElementById("reader-progress-fill").style.width,
}));
// Pause past the 600 ms save debounce so each turn is saved.
const turnPages = async (page, n) => {
  for (let i = 0; i < n; i += 1) {
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(750);
  }
};

// Signed-in reader (auth + progress API mocked) reading Frankenstein from the start.
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await ctx.addInitScript(() => { try { localStorage.clear(); } catch (_) {} });
await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: true, user: { email: "t@example.test" } } }));
await ctx.route(/\/progress\/v2\/books\/\d+$/, (r) => r.fulfill({ json: { success: true, projection: { book: null, modes: [] } } }));
const mutations = [];
await ctx.route(/\/progress\/v2\/mutations$/, (r) => {
  mutations.push(JSON.parse(r.request().postData() || "{}"));
  r.fulfill({ json: { success: true, result: "accepted" } });
});
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

await page.goto(`${BASE}/books/frankenstein/read`, { waitUntil: "networkidle" });
await page.waitForFunction(() => window.summraApp?.continuousReader?.active);
const start = await progress(page);
await turnPages(page, 8);
await page.waitForTimeout(900); // saves are debounced (600 ms)
const after = await progress(page);
expect("footer percentage moves forward as pages turn", parseInt(after.text, 10) > parseInt(start.text, 10),
  `${start.text} → ${after.text}`);
expect("bar width matches the percentage", after.width === after.text, JSON.stringify(after));

const qualified = mutations.filter((m) => m.qualified_furthest_marker);
expect("forward page turns are saved as sequential reading", qualified.length > 0
  && qualified.every((m) => m.sequential_boundaries_delta === 1), `${qualified.length}/${mutations.length} saves`);
const ordinals = qualified.map((m) => m.qualified_furthest_marker.word_position);
expect("furthest position advances", ordinals.length > 1 && ordinals[ordinals.length - 1] > ordinals[0], JSON.stringify(ordinals));

// Going back a page is not sequential reading, and doesn't advance furthest.
mutations.length = 0;
await page.keyboard.press("ArrowLeft");
await page.waitForTimeout(900);
expect("a backward page turn does not count as sequential",
  mutations.length > 0 && mutations.every((m) => !m.qualified_furthest_marker && m.sequential_boundaries_delta === 0),
  JSON.stringify(mutations.map((m) => [m.sequential_boundaries_delta, !!m.qualified_furthest_marker])));
const back = await progress(page);
expect("footer follows the current position backwards too", parseInt(back.text, 10) <= parseInt(after.text, 10),
  `${after.text} → ${back.text}`);

expect("no console errors", errors.length === 0, errors.join(" | "));
await browser.close();
process.exit(failed ? 1 : 0);
