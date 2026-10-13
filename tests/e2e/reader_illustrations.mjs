// Chapter illustrations appear in the continuous reader.
//
// Bug this guards against: illustrations (chapters.illustration_url — Alice,
// Peter Pan, Oz, A Christmas Carol) were drawn only by the old chapter view.
// Once the book page's chapter list opened the continuous reader, they were
// never shown anywhere. Each illustrated chapter now shows its picture under
// its heading (below it), in plain/original and side-by-side modes.
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const SLUG = "alices-adventures-in-wonderland";
const browser = await chromium.launch({ headless: true });
let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};

const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

const illustrationOnPage = () => page.evaluate(() => {
  const img = document.querySelector(".pagination-page-container .reader-illustration img, #continuous-reader-content .reader-illustration img");
  if (!img) return null;
  const r = img.getBoundingClientRect();
  return { src: img.currentSrc || img.src, loaded: img.complete && img.naturalWidth > 0, visible: r.width > 0 && r.height > 0 };
});

// Open chapter 2 from the book page, as a reader would.
await page.goto(`${BASE}/books/${SLUG}`, { waitUntil: "networkidle" });
await page.locator("#chapters-list .chapter-box").nth(1).click();
await page.waitForFunction(() => window.summraApp?.continuousReader?.active);
await page.waitForFunction(() => document.querySelector(".reader-illustration img")?.complete, null, { timeout: 8000 }).catch(() => {});
let ill = await illustrationOnPage();
expect("plain: chapter illustration is on the opening page", ill && ill.visible && ill.loaded, JSON.stringify(ill));
expect("plain: uses the chapter's own image", ill && /\/static\/illustrations\/1\/2\.(webp|jpg)/.test(ill.src), ill?.src);
const order = await page.evaluate(() => {
  const pg = [...document.querySelectorAll(".pagination-page-container")].find((p) => p.offsetParent !== null) || document;
  const h = pg.querySelector(".reader-chapter-heading");
  const f = pg.querySelector(".reader-illustration");
  return { heading: h?.textContent.trim(), headingFirst: !!(h && f && (h.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING)) };
});
expect("plain: illustration sits below the chapter title on the same page", order.headingFirst, JSON.stringify(order));

// No page ends on a chapter heading (it would be cut off from its picture/text).
const orphan = await page.evaluate(() => window.summraApp.pagination.pages.filter((html) => {
  const d = document.createElement("div"); d.innerHTML = html;
  const blocks = [...d.querySelectorAll("p, h2, figure")];
  return blocks.length > 1 && blocks[blocks.length - 1].matches("h2.reader-chapter-heading");
}).length);
expect("no page ends with a chapter heading", orphan === 0, `${orphan} pages`);

// Side by side keeps it too.
await page.click("#reader-settings-button");
await page.click('[data-reader-settings-mode="side_by_side"]');
await page.waitForFunction(() => window.summraApp.continuousReader.mode === "side_by_side");
await page.waitForFunction(() => document.querySelector(".reader-illustration img")?.complete, null, { timeout: 8000 }).catch(() => {});
ill = await illustrationOnPage();
expect("side by side: illustration still shown", ill && ill.visible && ill.loaded, JSON.stringify(ill));
await page.click('[data-reader-settings-mode="plain"]').catch(() => {});

// A book without illustrations shows none.
await page.goto(`${BASE}/books/frankenstein/chapters/1`, { waitUntil: "networkidle" });
await page.waitForFunction(() => window.summraApp?.continuousReader?.active);
expect("no illustration for chapters without one", (await page.locator(".reader-illustration").count()) === 0);

expect("no console errors", errors.length === 0, errors.join(" | "));
await browser.close();
process.exit(failed ? 1 : 0);
