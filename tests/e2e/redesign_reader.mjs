// Redesign phase 7: the continuous reader keeps its structure (back · title ·
// contents · reading settings; modes live in the settings panel) and takes
// the new look: paper chrome in the light theme, a thin oxblood progress bar,
// serif chapter headings, token-styled panels, and a hairline between
// side-by-side rows. The dark theme keeps matching chrome.
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const PAPER = "rgb(246, 241, 231)";
const INK = "rgb(43, 38, 34)";
const ACCENT = "rgb(138, 46, 46)";
const RULE = "rgb(232, 223, 207)";
const browser = await chromium.launch({ headless: true });
let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};

const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await ctx.route(/\/auth\/check$/, (r) => r.fulfill({ json: { authenticated: false } }));
await ctx.addInitScript(() => { try { localStorage.removeItem("readingSettings"); } catch (_) {} });
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(`${page.url()}: ${m.text()}`); });

await page.goto(`${BASE}/books/frankenstein/chapters/1`, { waitUntil: "networkidle" });
await page.waitForFunction(() => window.summraApp?.continuousReader?.active);

const chrome = await page.evaluate(() => {
  const c = document.getElementById("continuous-reader-chrome");
  const cs = getComputedStyle(c);
  return { bg: cs.backgroundColor, color: getComputedStyle(document.getElementById("reader-chapter-title")).color,
    headerToggles: c.querySelectorAll("[data-mode], [data-reader-settings-mode]").length,
    buttons: [...c.querySelectorAll("button")].map((b) => b.id) };
});
expect("light theme: paper chrome", chrome.bg === PAPER, chrome.bg);
expect("light theme: ink chapter title", chrome.color === INK, chrome.color);
expect("chrome keeps back · contents · settings", ["reader-back-button", "reader-toc-button", "reader-settings-button"]
  .every((id) => chrome.buttons.includes(id)), JSON.stringify(chrome.buttons));
expect("no mode toggle in the header (modes live in settings)", chrome.headerToggles === 0);

// Reading settings uses the "Aa" text icon (as e-readers do), not a gear:
// the old hand-traced gear blurred into a blob at 20px.
const settingsIcon = await page.evaluate(() => {
  const b = document.getElementById("reader-settings-button");
  return { label: b.getAttribute("aria-label"), paths: [...b.querySelectorAll("svg path")].map((p) => p.getAttribute("d")) };
});
expect("settings button: Aa icon with an accessible label",
  settingsIcon.label === "Reading settings" && settingsIcon.paths.length === 4
  && settingsIcon.paths.includes("m3 16 4.5-9 4.5 9"), JSON.stringify(settingsIcon.paths.map((d) => d.slice(0, 20))));

const heading = await page.evaluate(() => {
  const h = document.querySelector("#continuous-reader-content .reader-chapter-heading, #continuous-reader-content h2, #continuous-reader-content h1");
  return h && getComputedStyle(h).fontFamily;
});
expect("chapter heading is serif", heading && /serif/.test(heading) && !/sans-serif$/.test(heading), heading);

// Progress bar mirrors the percentage.
const bar = await page.evaluate(() => {
  const f = document.getElementById("reader-progress-fill");
  return f && { bg: getComputedStyle(f).backgroundColor, width: f.style.width,
    text: document.getElementById("continuous-reader-progress").textContent.trim() };
});
expect("progress bar: oxblood fill", bar && bar.bg === ACCENT, JSON.stringify(bar));
expect("progress bar: width matches the percentage", bar && bar.width === bar.text, JSON.stringify(bar));

// Settings panel: modes are there, active one marked in oxblood, sentence-case labels.
await page.click("#reader-settings-button");
await page.waitForSelector("#reading-settings-panel:not(.hidden)");
const settings = await page.evaluate(() => {
  const panel = document.getElementById("reading-settings-panel");
  const active = panel.querySelector("[data-reader-settings-mode].active");
  return { bg: getComputedStyle(panel).backgroundColor, modes: panel.querySelectorAll("[data-reader-settings-mode]").length,
    activeBorder: active && getComputedStyle(active).borderColor,
    title: panel.querySelector(".reading-settings-header h3").textContent.trim(),
    headings: [...panel.querySelectorAll("h4")].map((h) => h.textContent.trim()) };
});
expect("settings: four reading modes", settings.modes === 4);
expect("settings: active mode marked in oxblood", settings.activeBorder === ACCENT, settings.activeBorder);
expect("settings: surface background (not white)", settings.bg !== "rgb(255, 255, 255)", settings.bg);
expect("settings: sentence-case labels", settings.title === "Reading settings"
  && settings.headings.every((h) => h === h[0] + h.slice(1).toLowerCase() || /Plain English/.test(h)), JSON.stringify(settings));

// Side by side: hairline between aligned rows.
await page.click('[data-reader-settings-mode="side_by_side"]');
await page.waitForFunction(() => window.summraApp.continuousReader.mode === "side_by_side"
  && document.querySelector("#continuous-reader-content .side-by-side-row"));
const row = await page.evaluate(() => {
  const r = document.querySelector("#continuous-reader-content .side-by-side-row");
  const cs = getComputedStyle(r);
  return { width: cs.borderBottomWidth, color: cs.borderBottomColor };
});
expect("side by side: rows separated by a hairline", row.width === "1px" && row.color === RULE, JSON.stringify(row));

// Dark theme keeps dark chrome.
await page.click('.theme-choice[data-theme="dark"]');
const dark = await page.evaluate(() => getComputedStyle(document.getElementById("continuous-reader-chrome")).backgroundColor);
expect("dark theme: dark chrome", dark === "rgb(26, 26, 26)", dark);
await page.click('.theme-choice[data-theme="light"]');

// Mobile: no horizontal scroll.
const mobile = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
const mp = await mobile.newPage();
await mp.goto(`${BASE}/books/frankenstein/chapters/1`, { waitUntil: "networkidle" });
await mp.waitForFunction(() => window.summraApp?.continuousReader?.active);
expect("mobile: no horizontal scroll", (await mp.evaluate(() => document.documentElement.scrollWidth - innerWidth)) <= 0);
await mobile.close();

expect("no console errors", errors.length === 0, errors.join(" | "));
await browser.close();
process.exit(failed ? 1 : 0);
