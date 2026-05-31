// E2E test: chapter page defaults to "modern" (Plain English) when the user
// has no saved preference and the chapter has modern_english_text; honors a
// valid saved preference otherwise.
//
// Usage:
//   BASE_URL=http://localhost:5005 node tests/e2e/chapter_view_default.mjs
//   (or omit BASE_URL — defaults to http://localhost:5001)

import { chromium } from "playwright";

const baseUrl = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const headed = !!process.env.HEADED;
const chapterPath = "/books/alices-adventures-in-wonderland/chapters/1";

const browser = await chromium.launch({ headless: !headed });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();

const failures = [];

async function getActiveMode() {
    // Toggle may be hidden if only "Original" is available; check both states.
    return await page.evaluate(() => {
        const active = document.querySelector(".unified-view-btn.active");
        return active ? active.getAttribute("data-mode") : null;
    });
}

async function loadChapterFresh() {
    // Wipe localStorage by navigating to "about:blank" then to the page (the
    // origin's storage persists across page.goto, so we clear it explicitly).
    await page.goto(`${baseUrl}/`, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${baseUrl}${chapterPath}`, { waitUntil: "networkidle", timeout: 30_000 });
    // Wait for the chapter UI to settle — both setTimeout(50) and setTimeout(100) in app.js.
    await page.waitForTimeout(300);
}

async function loadChapterWithSavedMode(savedMode) {
    await page.goto(`${baseUrl}/`, { waitUntil: "domcontentloaded" });
    await page.evaluate((m) => {
        localStorage.clear();
        localStorage.setItem("reading_chapterViewMode", m);
    }, savedMode);
    await page.goto(`${baseUrl}${chapterPath}`, { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(300);
}

// --- Case 1: no saved preference → defaults to "modern" ---
await loadChapterFresh();
let active = await getActiveMode();
if (active !== "modern") {
    failures.push(`[no-saved-preference] expected active mode "modern", got ${JSON.stringify(active)}`);
} else {
    console.log("[PASS] no saved preference → modern");
}

// --- Case 2: saved 'original' → respected ---
await loadChapterWithSavedMode("original");
active = await getActiveMode();
if (active !== "original") {
    failures.push(`[saved=original] expected active mode "original", got ${JSON.stringify(active)}`);
} else {
    console.log("[PASS] saved 'original' is honored");
}

// --- Case 3: saved 'summary' → respected (chapter 1 has a summary) ---
await loadChapterWithSavedMode("summary");
active = await getActiveMode();
if (active !== "summary") {
    failures.push(`[saved=summary] expected active mode "summary", got ${JSON.stringify(active)}`);
} else {
    console.log("[PASS] saved 'summary' is honored");
}

await browser.close();

if (failures.length) {
    console.error("\nFAILURES:");
    for (const f of failures) console.error("  " + f);
    process.exit(1);
}
console.log("\nAll chapter-view-default checks passed.");
