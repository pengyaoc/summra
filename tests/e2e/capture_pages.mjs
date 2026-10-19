// Before/after screenshot capture for the site redesign.
//
// Takes full-page screenshots of every main page at desktop and mobile
// widths, after covers and catalog data have loaded, so the redesign can be
// compared screen by screen.
//
// Usage:
//   OUT_DIR=../../docs/redesign/before/local node capture_pages.mjs
//   BASE_URL=https://pengyaochen.com/plainly OUT_DIR=... node capture_pages.mjs
//
// Exit code is non-zero if any page fails to load (non-2xx).

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const baseUrl = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const outDir = resolve(here, process.env.OUT_DIR || "screenshots/capture");

const PAGES = [
  { name: "home", path: "/" },
  { name: "discover", path: "/discover" },
  { name: "books", path: "/books" },
  { name: "categories", path: "/categories" },
  { name: "library", path: "/library" },
  { name: "book", path: "/books/frankenstein" },
  { name: "author", path: "/authors/mary-shelley" },
  { name: "reader-plain", path: "/books/frankenstein/chapters/1" },
  { name: "reader-side-by-side", path: "/books/frankenstein/chapters/1", sideBySide: true },
];

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 375, height: 812, isMobile: true },
];

// Scroll through the page so lazy-loaded covers start, then wait until every
// visible <img> has finished (loaded or errored).
async function settle(page) {
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 150));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForFunction(
    () => [...document.images].every((img) => img.complete),
    null,
    { timeout: 15000 },
  ).catch(() => {});
  await page.waitForTimeout(500);
}

const browser = await chromium.launch();
let failed = false;

for (const vp of VIEWPORTS) {
  const dir = join(outDir, vp.name);
  await mkdir(dir, { recursive: true });
  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    isMobile: !!vp.isMobile,
    hasTouch: !!vp.isMobile,
  });
  const page = await context.newPage();

  for (const p of PAGES) {
    // Side-by-side is desktop-only by design (view_mode.js).
    if (p.sideBySide && vp.isMobile) continue;
    const res = await page.goto(`${baseUrl}${p.path}`, { waitUntil: "domcontentloaded" });
    const status = res ? res.status() : 0;
    if (status < 200 || status >= 300) {
      console.error(`FAIL ${vp.name} ${p.path} → HTTP ${status}`);
      failed = true;
      continue;
    }
    await settle(page);
    if (p.sideBySide) {
      // Older chapter view has a visible header toggle; the continuous
      // reader keeps modes inside its settings panel.
      const headerToggle = page.locator('.unified-view-btn[data-mode="side-by-side"]:visible');
      if (await headerToggle.count()) {
        await headerToggle.first().click();
      } else {
        await page.locator("#reader-settings-button").click();
        await page.locator('[data-reader-settings-mode="side_by_side"]').click();
        await page.locator("#reading-settings-close").click().catch(() => {});
      }
      await settle(page);
    }
    const file = join(dir, `${p.name}.jpg`);
    await page.screenshot({ path: file, fullPage: true, type: "jpeg", quality: 70 });
    console.log(`ok   ${vp.name} ${p.path} → ${file}`);
  }
  await context.close();
}

await browser.close();
process.exit(failed ? 1 : 0);
