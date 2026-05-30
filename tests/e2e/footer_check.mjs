// Verify footer behavior: present on home, hidden on server-rendered chapter,
// hidden after SPA navigation from home → chapter.
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const shotsDir = join(here, "screenshots");
await mkdir(shotsDir, { recursive: true });

const BASE = process.env.BASE_URL || "http://localhost:5001";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

let failed = false;
const expect = (label, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failed = true;
};

// 1. Home: footer must exist and be visible.
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
const homeFooterVisible = await page.evaluate(() => {
  const f = document.querySelector("footer.footer");
  if (!f) return { exists: false };
  const cs = getComputedStyle(f);
  return { exists: true, hidden: f.classList.contains("hidden"), display: cs.display };
});
expect("home: footer exists",        homeFooterVisible.exists);
expect("home: footer visible",       homeFooterVisible.exists && !homeFooterVisible.hidden && homeFooterVisible.display !== "none",
       JSON.stringify(homeFooterVisible));

// 2. Server-rendered chapter page: footer must be absent from the DOM entirely (Jinja gate).
await page.goto(`${BASE}/books/a-christmas-carol-in-prose/chapters/1`, { waitUntil: "networkidle" });
const ssrFooter = await page.evaluate(() => document.querySelector("footer.footer") !== null);
expect("chapter (server render): footer absent from DOM", !ssrFooter);

// 3. SPA navigation: go back home, then click into a chapter link and verify the footer hides.
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
const beforeSpaNav = await page.evaluate(() => {
  const f = document.querySelector("footer.footer");
  return f ? { exists: true, hidden: f.classList.contains("hidden") } : { exists: false };
});
expect("spa: footer present after returning home", beforeSpaNav.exists && !beforeSpaNav.hidden);

// Navigate via SPA: pushState to a chapter URL and let the app respond.
// (Routing in app.js listens for popstate/click — easiest is to push + dispatch popstate.)
await page.evaluate(() => {
  history.pushState({}, "", "/books/a-christmas-carol-in-prose/chapters/1");
  window.dispatchEvent(new PopStateEvent("popstate"));
});
// Give the SPA a beat to render.
await page.waitForFunction(() => {
  const sec = document.getElementById("chapter-detail-section");
  return sec && !sec.classList.contains("hidden");
}, { timeout: 5000 }).catch(() => {});

const afterSpaNav = await page.evaluate(() => {
  const f = document.querySelector("footer.footer");
  if (!f) return { exists: false };
  const cs = getComputedStyle(f);
  return {
    exists: true,
    hiddenClass: f.classList.contains("hidden"),
    display: cs.display,
    visible: cs.display !== "none" && cs.visibility !== "hidden",
  };
});
expect("spa: footer hidden after navigating to chapter",
       afterSpaNav.exists && (afterSpaNav.hiddenClass || !afterSpaNav.visible),
       JSON.stringify(afterSpaNav));

await page.screenshot({ path: join(shotsDir, "footer_check_spa_chapter.png"), fullPage: true });

await browser.close();
process.exit(failed ? 1 : 0);
