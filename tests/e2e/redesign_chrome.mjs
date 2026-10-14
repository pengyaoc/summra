// Redesign phase 1: design tokens + global chrome (header, footer, buttons).
// Asserts the "quiet library" palette is applied site-wide: paper page
// background, light header with ink nav links, serif wordmark, oxblood
// primary button, and a footer that links to the main sections.
import { chromium } from "playwright";

const BASE = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const PAPER = "rgb(246, 241, 231)";
const INK = "rgb(43, 38, 34)";
const ACCENT = "rgb(138, 46, 46)";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};

const consoleErrors = [];
page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(`${page.url()}: ${msg.text()}`); });

for (const path of ["/", "/discover", "/books/frankenstein"]) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  const s = await page.evaluate(() => {
    const cs = (sel, prop) => {
      const el = document.querySelector(sel);
      return el ? getComputedStyle(el)[prop] : null;
    };
    return {
      bodyBg: cs("body", "backgroundColor"),
      headerBg: cs("header.header", "backgroundColor"),
      navColor: cs("#discover-nav-btn", "color"),
      booksNav: !!document.getElementById("books-nav-btn"),
      logoFont: cs(".logo", "fontFamily"),
      footerLinks: [...document.querySelectorAll("footer.footer a")].map((a) => a.getAttribute("href")),
    };
  });
  expect(`${path}: page background is paper`, s.bodyBg === PAPER, s.bodyBg);
  expect(`${path}: header background is paper`, s.headerBg === PAPER, s.headerBg);
  expect(`${path}: nav links are ink`, s.navColor === INK, s.navColor);
  expect(`${path}: wordmark is serif`, /serif/i.test(s.logoFont || "") && !/sans-serif$/i.test(s.logoFont || ""), s.logoFont);
  expect(`${path}: Discover only — no separate Books link (header or footer)`,
    !s.booksNav && s.footerLinks.some((h) => h && h.endsWith("/discover")) && !s.footerLinks.some((h) => h && h.endsWith("/books")),
    JSON.stringify(s.footerLinks));
}

// One UI type system: nav and footer in the sans at a confident weight, no
// serif lines in the footer, no repeated tagline, and every "… →" text link
// styled alike (accent, semibold, no underline) — never a raw browser link.
await page.goto(`${BASE}/books/alices-adventures-in-wonderland`, { waitUntil: "networkidle" });
await page.waitForSelector("#about-author-section:not(.hidden)");
const ui = await page.evaluate(() => {
  const st = (el) => el && getComputedStyle(el);
  const footer = document.querySelector("footer.footer");
  const footerTexts = [...footer.querySelectorAll("p, a")].filter((e) => e.offsetParent);
  return {
    navWeight: +st(document.querySelector(".header-nav-btn")).fontWeight,
    footerSerif: footerTexts.filter((e) => !/sans-serif$/.test(st(e).fontFamily)).map((e) => e.textContent.trim()),
    footerPlainMentions: (footer.textContent.match(/plain English/gi) || []).length,
    learnMore: ["color", "fontWeight", "textDecorationLine"].map((k) => st(document.getElementById("author-learn-more-btn"))[k]),
  };
});
expect("nav links are medium weight or heavier", ui.navWeight >= 500, String(ui.navWeight));
expect("footer is all sans (no stray serif line)", ui.footerSerif.length === 0, JSON.stringify(ui.footerSerif));
expect("footer says 'plain English' once", ui.footerPlainMentions <= 1, String(ui.footerPlainMentions));
expect("'Learn more →' is a styled accent link, not a raw browser link",
  ui.learnMore[0] === "rgb(138, 46, 46)" && +ui.learnMore[1] >= 600 && ui.learnMore[2] === "none", JSON.stringify(ui.learnMore));
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
const sectionLink = await page.evaluate(() => { const c = getComputedStyle(document.querySelector(".home-section-link")); return [c.color, c.fontWeight, c.textDecorationLine]; });
expect("home '… →' links match the same link style", sectionLink[0] === "rgb(138, 46, 46)" && +sectionLink[1] >= 600 && sectionLink[2] === "none", JSON.stringify(sectionLink));

// Old /books links land on Discover.
await page.goto(`${BASE}/books`, { waitUntil: "networkidle" });
expect("/books redirects to /discover", new URL(page.url()).pathname.endsWith("/discover"), page.url());

// Primary call to action on the book page uses the accent colour.
await page.goto(`${BASE}/books/frankenstein`, { waitUntil: "networkidle" });
const readBtnBg = await page.evaluate(() => {
  const el = document.querySelector(".book-read-btn");
  return el ? getComputedStyle(el).backgroundColor : null;
});
expect("book page: Read button is oxblood", readBtnBg === ACCENT, readBtnBg);

// Non-reader pages sit on one paper background: no full-width white or
// surface-coloured bands (reader pages use --surface on purpose; the home
// hero is a deliberate dark ink band).
for (const path of ["/", "/books/frankenstein", "/library"]) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  const bands = await page.evaluate((paper) => [...document.querySelectorAll("main *")]
    .filter((el) => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      if (r.width < 900 || r.height < 300) return false;
      if (cs.backgroundImage.includes("url(")) return false; // image heroes
      if (el.classList.contains("hero-main")) return false; // the home hero is a deliberate ink band (2026-10-13)
      return cs.backgroundColor !== "rgba(0, 0, 0, 0)" && cs.backgroundColor !== paper
        || /gradient/.test(cs.backgroundImage) && /255, 255, 255/.test(cs.backgroundImage);
    })
    .map((el) => `${el.tagName}.${[...el.classList].join(".")} ${getComputedStyle(el).backgroundColor}`), PAPER);
  expect(`${path}: no off-paper page bands`, bands.length === 0, bands.join(", "));
}

expect("no console errors", consoleErrors.length === 0, consoleErrors.join(" | "));

await browser.close();
process.exit(failed ? 1 : 0);
