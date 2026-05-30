// Frontend smoke test: launches Chromium, hits the homepage, captures
// screenshot + console errors + network failures, and exits non-zero on failure.
//
// Usage:
//   BASE_URL=http://localhost:5001 node smoke.mjs
//   node smoke.mjs                            # defaults to http://localhost:5001
//   HEADED=1 node smoke.mjs                   # show the browser window
//   PATHS=/,/book/104 node smoke.mjs          # comma-separated paths to visit
//
// Exit code: 0 if every page loaded without console errors / failed requests,
// non-zero otherwise. Screenshots land in ./screenshots/<slug>.png.
//
// Third-party analytics/tracking requests are ignored — we only care about
// failures on first-party assets.

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const screenshotsDir = join(here, "screenshots");
await mkdir(screenshotsDir, { recursive: true });

const baseUrl = (process.env.BASE_URL || "http://localhost:5001").replace(/\/$/, "");
const headed = !!process.env.HEADED;
const paths = (process.env.PATHS || "/").split(",").map((p) => p.trim()).filter(Boolean);

// Hosts whose failures we don't care about (analytics, ads, fonts, etc.)
const THIRD_PARTY_NOISE = [
  "google-analytics.com",
  "googletagmanager.com",
  "doubleclick.net",
  "googlesyndication.com",
  "google.com/pagead",
  "facebook.com",
  "facebook.net",
];
const isNoise = (url) => THIRD_PARTY_NOISE.some((h) => url.includes(h));

const slug = (p) => (p === "/" ? "home" : p.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "root");

const browser = await chromium.launch({ headless: !headed });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();

let hadFailure = false;
const summary = [];

for (const path of paths) {
  const url = `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const consoleErrors = [];
  const failedRequests = [];

  page.removeAllListeners("console");
  page.removeAllListeners("requestfailed");
  page.on("console", (msg) => {
    if (msg.type() === "error" && !isNoise(msg.location()?.url || "")) {
      consoleErrors.push(msg.text());
    }
  });
  page.on("requestfailed", (req) => {
    if (isNoise(req.url())) return;
    failedRequests.push(`${req.method()} ${req.url()} — ${req.failure()?.errorText}`);
  });

  let status = "n/a";
  let error = null;
  try {
    const response = await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
    status = response ? response.status() : "no-response";
    if (!response || !response.ok()) {
      error = `HTTP ${status}`;
    }
  } catch (e) {
    error = e.message;
  }

  const shotPath = join(screenshotsDir, `${slug(path)}.png`);
  try {
    await page.screenshot({ path: shotPath, fullPage: true });
  } catch (e) {
    // Screenshot might fail if the page never loaded; ignore.
  }

  const ok = !error && consoleErrors.length === 0 && failedRequests.length === 0;
  if (!ok) hadFailure = true;

  summary.push({ path, url, status, ok, error, consoleErrors, failedRequests, screenshot: shotPath });
}

await browser.close();

for (const r of summary) {
  const tag = r.ok ? "PASS" : "FAIL";
  console.log(`[${tag}] ${r.path}  →  ${r.url}  (status ${r.status})`);
  if (r.error) console.log(`       error: ${r.error}`);
  if (r.consoleErrors.length) {
    console.log(`       console errors (${r.consoleErrors.length}):`);
    for (const m of r.consoleErrors) console.log(`         - ${m}`);
  }
  if (r.failedRequests.length) {
    console.log(`       failed requests (${r.failedRequests.length}):`);
    for (const m of r.failedRequests) console.log(`         - ${m}`);
  }
  console.log(`       screenshot: ${r.screenshot}`);
}

process.exit(hadFailure ? 1 : 0);
