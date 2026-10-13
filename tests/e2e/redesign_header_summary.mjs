// Header search + account, book-page summary (Short/Full, read more), the
// Listen button and audio player, and shared button styling.
// The TTS endpoint is mocked to an existing audio file, so no TTS is generated.
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const SLUG = "alices-adventures-in-wonderland";
const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
const browser = await chromium.launch({ headless: true });
let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};

const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: true, user: { email: "reader@example.test" } } }));
await ctx.route(/\/api\/tts\/generate$/, (r) => r.fulfill({ json: {
  success: true, audio_url: "/static/audio/book_1_concise_gemini.opus", audio_id: "book_1_concise" } }));
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(e.message));
page.on("dialog", (d) => { errors.push(`dialog: ${d.message()}`); d.dismiss(); });

await page.goto(`${BASE}/books/${SLUG}`, { waitUntil: "networkidle" });

// --- Header search (desktop: always-visible field) ---
const search = await page.evaluate(() => {
  const input = document.getElementById("header-search-input");
  const r = input.getBoundingClientRect();
  return { visible: !!input.offsetParent && r.width > 0, width: Math.round(r.width),
    toggleVisible: !!document.getElementById("header-search-toggle").offsetParent };
});
expect("desktop: header search field visible without clicking", search.visible && search.width >= 200, JSON.stringify(search));
expect("desktop: no separate toggle button", !search.toggleVisible);
await page.fill("#header-search-input", "alice");
await page.waitForSelector("#header-search-results .hero-search-result-item");
const results = await page.evaluate(() => {
  const r = document.getElementById("header-search-results").getBoundingClientRect();
  return { left: Math.round(r.left), right: Math.round(r.right), vw: innerWidth };
});
expect("desktop: results stay inside the window", results.left >= 0 && results.right <= results.vw, JSON.stringify(results));
await page.fill("#header-search-input", "");
await page.keyboard.press("Escape");

// --- Account ---
const account = await page.evaluate(() => {
  const b = document.getElementById("user-account-btn");
  const r = b.getBoundingClientRect();
  return { text: b.textContent.trim(), label: b.getAttribute("aria-label"), h: Math.round(r.height), w: Math.round(r.width),
    avatar: b.querySelector(".account-avatar")?.textContent.trim() };
});
expect("account: avatar with the reader's initial, no emoji", account.avatar === "R" && !EMOJI.test(account.text), JSON.stringify(account));
expect("account: compact circular button with an accessible name", account.h === account.w && account.h <= 40 && /account/i.test(account.label || ""), JSON.stringify(account));
await page.click("#user-account-btn");
await page.waitForSelector("#user-modal:not(.hidden)");
const modal = await page.evaluate(() => {
  const c = document.querySelector(".user-modal-content");
  return { bg: getComputedStyle(c).backgroundColor, title: document.querySelector("#account-view .user-modal-title").textContent.trim(),
    titleFont: getComputedStyle(document.querySelector("#account-view .user-modal-title")).fontFamily,
    library: !!document.querySelector('#account-view a[href$="/library"]') };
});
expect("account modal: surface background, serif title", modal.bg !== "rgb(255, 255, 255)" && /serif/.test(modal.titleFont)
  && !/sans-serif$/.test(modal.titleFont) && modal.title === "Your account", JSON.stringify(modal));
expect("account modal: links to the library", modal.library);
await page.click("#user-modal-close");

// --- Summary ---
const summary = await page.evaluate(() => {
  const tabs = [...document.querySelectorAll(".summary-tab")];
  return {
    tabs: tabs.map((t) => t.textContent.replace(/\s+/g, " ").trim()),
    selected: tabs.map((t) => t.getAttribute("aria-selected")),
    inSwitch: tabs.every((t) => t.closest(".summary-switch")),
    textFont: getComputedStyle(document.getElementById("concise-summary-text")).fontFamily,
    heading: document.querySelector(".book-summary-title")?.textContent.trim(),
  };
});
expect("summary: heading and Short/Full switch", summary.heading === "Summary" && summary.inSwitch
  && /^Short/.test(summary.tabs[0]) && /^Full/.test(summary.tabs[1]), JSON.stringify(summary));
expect("summary: switch shows reading times", summary.tabs.every((t) => /\d+ min/.test(t)), JSON.stringify(summary.tabs));
expect("summary: tabs expose selection", summary.selected[0] === "true" && summary.selected[1] === "false");
expect("summary: text set in the reading serif", /serif/.test(summary.textFont) && !/sans-serif$/.test(summary.textFont), summary.textFont);

const more = page.locator("#concise-expand-button");
expect("short: Read more with a chevron", /Read more/.test(await more.textContent()) && (await more.locator("svg").count()) === 1);
const collapsedH = await page.evaluate(() => document.getElementById("concise-preview-container").getBoundingClientRect().height);
await more.click();
await page.waitForTimeout(400);
const expanded = await page.evaluate(() => ({
  h: document.getElementById("concise-preview-container").getBoundingClientRect().height,
  label: document.getElementById("concise-expand-button").textContent.trim() }));
expect("short: Read more expands in place", expanded.h > collapsedH && /Show less/.test(expanded.label), JSON.stringify({ collapsedH, ...expanded }));
await more.click();
await page.waitForTimeout(600);
expect("short: Show less collapses without errors", /Read more/.test(await more.textContent()) && errors.length === 0, errors.join(" | "));

await page.click('.summary-tab[data-tab="2000-word"]');
const full = await page.evaluate(() => ({
  selected: document.querySelector('.summary-tab[data-tab="2000-word"]').getAttribute("aria-selected"),
  label: document.getElementById("medium-expand-button").textContent.trim() }));
expect("full: selected, with a clear link to the whole summary", full.selected === "true" && /Read the full summary/.test(full.label), JSON.stringify(full));
await page.click('.summary-tab[data-tab="500-word"]');

// --- Listen + player ---
const listen = page.locator("#active-summary-tts-button");
const listenIdle = (await listen.textContent()).trim();
expect("listen: icon button, no emoji", /Listen/.test(listenIdle) && !EMOJI.test(listenIdle) && (await listen.locator("svg").count()) >= 1, listenIdle);
await listen.click();
await page.waitForFunction(() => /Pause/.test(document.getElementById("active-summary-tts-button").textContent), null, { timeout: 8000 })
  .then(() => expect("listen: shows Pause while this summary plays", true))
  .catch(async () => expect("listen: shows Pause while this summary plays", false, (await listen.textContent()).trim()));
const player = await page.evaluate(() => {
  const p = document.getElementById("persistent-player");
  const cs = getComputedStyle(p);
  return { visible: !p.classList.contains("hidden"), bgImage: cs.backgroundImage, text: p.textContent,
    titleFont: getComputedStyle(document.getElementById("player-title")).fontFamily };
});
expect("player: visible, flat surface (no gradient), no emoji", player.visible && player.bgImage === "none" && !EMOJI.test(player.text), JSON.stringify({ ...player, text: undefined }));
await listen.click();
await page.waitForTimeout(400);
expect("listen: second click pauses instead of regenerating",
  await page.evaluate(() => document.getElementById("persistent-audio-element").paused) && /Resume/.test(await listen.textContent()),
  (await listen.textContent()).trim());
await page.click("#player-stop");
await page.waitForTimeout(300);
expect("listen: back to Listen after stopping", /Listen/.test(await listen.textContent()));

// --- One button shape ---
const radii = await page.evaluate(() => ["#book-read-btn", "#book-sxs-link", "#active-summary-tts-button", "#medium-expand-button"]
  .map((sel) => document.querySelector(sel)).filter(Boolean).map((el) => getComputedStyle(el).borderTopLeftRadius));
expect("buttons share one corner radius (8px)", radii.length >= 3 && radii.every((r) => r === "8px"), JSON.stringify(radii));

// --- Mobile header search ---
const mobile = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
await mobile.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
const mp = await mobile.newPage();
await mp.goto(`${BASE}/books/${SLUG}`, { waitUntil: "networkidle" });
expect("mobile: search field hidden until the icon is tapped", !(await mp.isVisible("#header-search-input")) && await mp.isVisible("#header-search-toggle"));
await mp.click("#header-search-toggle");
const mobileField = await mp.evaluate(() => Math.round(document.getElementById("header-search-input").getBoundingClientRect().width));
expect("mobile: search opens full width", mobileField >= 320, `${mobileField}px`);
expect("mobile: no horizontal scroll", (await mp.evaluate(() => document.documentElement.scrollWidth - innerWidth)) <= 0);
await mobile.close();

expect("no console errors", errors.length === 0, errors.join(" | "));
await browser.close();
process.exit(failed ? 1 : 0);
