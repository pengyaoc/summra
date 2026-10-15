// Redesign phase 6: home page and header search.
//  - Paper hero (no cover wall) with an original → plain-English sentence
//    pair; "Show me another" cycles through the pairs
//  - "Start here" shelf uses the book card (title, level, time) with a small
//    rank badge instead of big numerals
//  - "Find a book at the right level" grade cards open a filtered Discover
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
// Option B "open book": a dark, full-width band with the sentence pair as a book spread.
const lum = (rgb) => { const [r, g, b] = rgb.match(/\d+/g).slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const band = await page.evaluate(() => {
  const h = document.querySelector(".hero-main"), r = h.getBoundingClientRect();
  const sub = document.querySelector(".hero-banner-subtitle");
  return { bg: getComputedStyle(h).backgroundColor, title: getComputedStyle(document.querySelector(".hero-banner-title")).color,
    width: Math.round(r.width), vw: document.documentElement.clientWidth, subFont: getComputedStyle(sub).fontFamily,
    heroSearch: !!document.getElementById("hero-search-input"),
    searchFields: [...document.querySelectorAll('input[id$="search-input"]')].filter((i) => i.offsetParent).length };
});
const ratio = (lum(band.title) + 0.05) / (lum(band.bg) + 0.05);
expect("hero: dark band with high-contrast title", lum(band.bg) < 0.05 && ratio >= 7, `${band.bg} / ${band.title} → ${ratio.toFixed(1)}:1`);
expect("hero: band spans the full window width", Math.abs(band.width - band.vw) <= 1, JSON.stringify(band));
expect("hero: tagline in the serif", /serif/.test(band.subFont) && !/sans-serif$/.test(band.subFont), band.subFont);
expect("hero: one search field on screen (header only)", !band.heroSearch && band.searchFields === 1, JSON.stringify(band));
// Option 2 "text thread": the original arrives as a message from the author,
// the plain-English version replies from the right.
const thread = (pg) => pg.evaluate(() => {
  const f = [...document.querySelectorAll(".hero-sentence")].find((x) => !x.hidden);
  const t = f.getBoundingClientRect();
  const o = f.querySelector(".hero-bubble--original").getBoundingClientRect(), p = f.querySelector(".hero-bubble--plain").getBoundingClientRect();
  return { tL: Math.round(t.left), tR: Math.round(t.right), tW: Math.round(t.width),
    oL: Math.round(o.left), oR: Math.round(o.right), oB: Math.round(o.bottom), oW: Math.round(o.width),
    pL: Math.round(p.left), pR: Math.round(p.right), pT: Math.round(p.top), pW: Math.round(p.width),
    sender: f.querySelector(".hero-sentence-source")?.textContent.replace(/\s+/g, " ").trim(),
    replyLabel: f.querySelector(".hero-bubble--plain .hero-sentence-label")?.textContent.trim() };
});
const isThread = (t) => Math.abs(t.oL - t.tL) <= 1 && Math.abs(t.pR - t.tR) <= 1 && t.pT >= t.oB
  && t.oW < t.tW * 0.92 && t.pW < t.tW * 0.92;
const desk = await thread(page);
expect("hero: original arrives left, plain English replies right, below it", isThread(desk), JSON.stringify(desk));
expect("hero: the message is from the author; the reply is labelled Plain English",
  /Austen|Dickens|Shelley|Carroll|Brontë|Doyle|Twain|Wilde|Stevenson|·/.test(desk.sender || "") && desk.replyLabel === "Plain English", JSON.stringify(desk));
const copy = await page.evaluate(() => document.querySelector(".hero-main").textContent);
expect("hero: tagline points to side by side for the original", /side by side/i.test(copy) && !/Stuck on a sentence/.test(copy), copy.replace(/\s+/g, " ").slice(0, 200));
// Sections read as distinct bands: each spans the window, and no two
// neighbouring sections share a background.
const bands = await page.evaluate(() => [...document.querySelectorAll("#hero-section > section")]
  .filter((el) => el.offsetParent)
  .map((el) => ({ id: el.id || el.className.split(" ").slice(-1)[0], bg: getComputedStyle(el).backgroundColor,
    full: Math.abs(el.getBoundingClientRect().width - document.documentElement.clientWidth) <= 1 })));
expect("home: every section is a full-width band", bands.length >= 3 && bands.every((b) => b.full), JSON.stringify(bands));
expect("home: neighbouring sections differ in background", bands.every((b, i) => i === 0 || b.bg !== bands[i - 1].bg), JSON.stringify(bands));
expect("hero: friendly copy (no 'summarised' / 'prose')", !/summari[sz]ed|prose/i.test(copy), copy.replace(/\s+/g, " ").slice(0, 160));
const replyAnim = () => page.evaluate(() => getComputedStyle([...document.querySelectorAll(".hero-sentence")]
  .find((x) => !x.hidden).querySelector(".hero-bubble--plain")).animationName);
expect("hero: no reply animation on first load", (await replyAnim()) === "none", await replyAnim());
await page.click("#hero-sentence-next");
expect("hero: the reply animates in after Show me another", (await replyAnim()) === "hero-reply-in", await replyAnim());
const heights = [];
const exampleCount = await page.locator(".hero-sentence").count();
for (let i = 0; i <= exampleCount; i += 1) {
  heights.push(await page.evaluate(() => Math.round(document.querySelector(".hero-main").getBoundingClientRect().height)));
  await page.click("#hero-sentence-next");
}
expect("hero: height stays put while turning through examples", new Set(heights).size === 1, JSON.stringify(heights));
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
  rank: !!c.querySelector(".book-card-rank, .top-10-rank-number"),
})));
expect("start here: cards have titles and reading times", shelf.length >= 5 && shelf.every((c) => c.title && c.time),
  JSON.stringify(shelf[0]));
expect("start here: no 'No. N' rank badge on covers", shelf.every((c) => !c.rank));

// Continue reading is hidden for anonymous visitors
expect("continue reading hidden when signed out", !(await page.isVisible("#home-continue")));

// Find a book at the right level: grade cards open a filtered Discover
await page.click(".grade-card--6-8");
await page.waitForURL(/\/discover\?grade=6-8$/);
await page.waitForFunction(() => document.querySelectorAll("#discover-grid .book-card").length > 0);
const bandCards = await page.evaluate(() => [...document.querySelectorAll("#discover-grid .book-card")]
  .filter((c) => c.offsetParent !== null).map((c) => c.dataset.grade));
expect("grade card: opens Discover filtered to grades 6–8", bandCards.length > 0 && bandCards.every((g) => g === "6-8"), `${bandCards.length}`);
const hrefs = await page.evaluate(() => [...document.querySelectorAll("#discover-grid .book-card")].map((c) => c.getAttribute("href")));
expect("grade card: Discover grid has no duplicate cards", new Set(hrefs).size === hrefs.length, `${hrefs.length} cards, ${new Set(hrefs).size} unique`);

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
const mHeights = await mp.evaluate(() => [...document.querySelectorAll(".hero-sentence")]
  .map((f) => Math.round([...f.children].reduce((h, c) => h + c.getBoundingClientRect().height, 0))));
expect("mobile: examples are similar in length (≤100px of spare space)", Math.max(...mHeights) - Math.min(...mHeights) <= 100, JSON.stringify(mHeights));
const mThread = await thread(mp);
const mOrder = await mp.evaluate(() => {
  const r = (sel) => document.querySelector(sel).getBoundingClientRect();
  const thread = r("#hero-examples"), cta = r(".hero-main .hero-cta-primary"), band = r(".hero-main");
  return { threadBottom: Math.round(thread.bottom), ctaTop: Math.round(cta.top), ctaW: Math.round(cta.width), bandW: Math.round(band.width) };
});
expect("mobile: the example comes before the button, which runs full width", mOrder.ctaTop >= mOrder.threadBottom && mOrder.ctaW >= mOrder.bandW - 48, JSON.stringify(mOrder));
expect("mobile: same thread layout on a phone", isThread(mThread), JSON.stringify(mThread));
await mobile.close();

// No pop-in: whatever Continue reading shows is in the first HTML, so the
// sections below don't jump once scripts and /api/library finish.
{
  const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p2 = await ctx2.newPage();
  await p2.goto(`${BASE}/`, { waitUntil: "commit" });
  await p2.waitForSelector(".hero-discover");
  const top = () => p2.evaluate(() => Math.round(document.querySelector(".hero-discover").getBoundingClientRect().top + scrollY));
  const early = await top();
  await p2.waitForLoadState("networkidle");
  await p2.waitForTimeout(500);
  const late = await top();
  expect("home: Start here doesn't move after load (no Continue reading pop-in)", early === late, `${early} → ${late}`);
  await ctx2.close();
}

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
