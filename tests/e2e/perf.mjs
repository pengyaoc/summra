// Perf audit: load homepage, measure timings, list every request with size + duration.
import { chromium } from "playwright";

const url = process.env.URL || "http://localhost:5001/";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

const requests = new Map(); // url -> { method, type, start, end, status, size }

page.on("request", (req) => {
  requests.set(req.url(), {
    method: req.method(),
    type: req.resourceType(),
    start: Date.now(),
  });
});
page.on("response", async (res) => {
  const r = requests.get(res.url());
  if (!r) return;
  r.end = Date.now();
  r.status = res.status();
  try {
    const buf = await res.body();
    r.size = buf.length;
  } catch {
    r.size = 0;
  }
});

const t0 = Date.now();
await page.goto(url, { waitUntil: "load" });
const tLoad = Date.now() - t0;

const nav = await page.evaluate(() => {
  const n = performance.getEntriesByType("navigation")[0];
  const paints = Object.fromEntries(
    performance.getEntriesByType("paint").map((p) => [p.name, Math.round(p.startTime)])
  );
  return {
    domContentLoaded: Math.round(n.domContentLoadedEventEnd),
    loadEvent: Math.round(n.loadEventEnd),
    transferSize: n.transferSize,
    paints,
  };
});

await browser.close();

const rows = [...requests.entries()].map(([u, r]) => ({
  url: u,
  type: r.type,
  status: r.status ?? "?",
  ms: r.end ? r.end - r.start : "?",
  kb: r.size != null ? (r.size / 1024).toFixed(1) : "?",
}));

const byType = {};
for (const r of rows) {
  byType[r.type] = byType[r.type] || { count: 0, kb: 0 };
  byType[r.type].count += 1;
  byType[r.type].kb += parseFloat(r.kb) || 0;
}

console.log(`URL:                ${url}`);
console.log(`Total wall time:    ${tLoad} ms`);
console.log(`DOMContentLoaded:   ${nav.domContentLoaded} ms`);
console.log(`load event:         ${nav.loadEvent} ms`);
console.log(`first-paint:        ${nav.paints["first-paint"] ?? "?"} ms`);
console.log(`first-contentful:   ${nav.paints["first-contentful-paint"] ?? "?"} ms`);
console.log(`Requests:           ${rows.length}`);
console.log(`Total bytes:        ${(rows.reduce((s, r) => s + (parseFloat(r.kb) || 0), 0)).toFixed(1)} KB`);
console.log("");
console.log("By type:");
for (const [t, v] of Object.entries(byType).sort((a, b) => b[1].kb - a[1].kb)) {
  console.log(`  ${t.padEnd(12)} ${String(v.count).padStart(3)} req   ${v.kb.toFixed(1).padStart(8)} KB`);
}
console.log("");
console.log("Top 20 requests by size:");
rows.sort((a, b) => (parseFloat(b.kb) || 0) - (parseFloat(a.kb) || 0));
for (const r of rows.slice(0, 20)) {
  const short = r.url.replace(/^https?:\/\/[^/]+/, "").slice(0, 80);
  console.log(`  ${r.kb.padStart(8)} KB  ${String(r.ms).padStart(5)} ms  [${r.type}] ${short}`);
}
console.log("");
console.log("Top 10 requests by duration:");
rows.sort((a, b) => (b.ms || 0) - (a.ms || 0));
for (const r of rows.slice(0, 10)) {
  const short = r.url.replace(/^https?:\/\/[^/]+/, "").slice(0, 80);
  console.log(`  ${String(r.ms).padStart(5)} ms  ${r.kb.padStart(8)} KB  [${r.type}] ${short}`);
}
