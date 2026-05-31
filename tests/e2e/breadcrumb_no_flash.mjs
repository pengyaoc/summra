// FAILING TEST for the breadcrumb snap-in regression on book detail pages.
//
// Symptom: load /books/<slug>, the SSR-rendered breadcrumb is visible
// immediately, then ~100ms later (after the JS hydration runs through
// showBookDetail → await loads → updateBreadcrumbs) it briefly disappears
// (hideAllBreadcrumbs adds .hidden → display:none → layout collapses) and
// the content below jumps up. A frame later the breadcrumb is rebuilt and
// the layout jumps back down.
//
// This test instruments the breadcrumb nav with a MutationObserver from the
// moment the page loads, records every transition of the .hidden class,
// then asserts that the breadcrumb never transitioned from "visible" to
// "hidden" during the hydration cycle.
//
// On the broken code, the observer logs: [hidden=false] (SSR) →
// [hidden=true] (hideAllBreadcrumbs) → [hidden=false] (renderBreadcrumbs).
// On the fixed code: [hidden=false] (SSR) only.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5003';
const BOOK_URL = `${BASE}/books/a-room-with-a-view`;

async function run() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const page = await ctx.newPage();

  // Inject the observer BEFORE any other script runs, so we catch the very
  // first hidden→visible transition (or, on the broken path, the
  // visible→hidden flash).
  await page.addInitScript(() => {
    window.__breadcrumbTransitions = [];
    const start = performance.now();
    const watch = () => {
      const nav = document.getElementById('breadcrumb-nav-book');
      if (!nav) {
        // Try again next frame; the element may not be parsed yet.
        requestAnimationFrame(watch);
        return;
      }
      const record = (event) => {
        window.__breadcrumbTransitions.push({
          t: Math.round(performance.now() - start),
          hidden: nav.classList.contains('hidden'),
          fullClass: nav.className,
          event,
        });
      };
      record('initial');
      const obs = new MutationObserver(() => record('classChange'));
      obs.observe(nav, { attributes: true, attributeFilter: ['class'] });
    };
    watch();
  });

  const resp = await page.goto(BOOK_URL, { waitUntil: 'networkidle', timeout: 30000 });
  if (!resp || resp.status() !== 200) {
    console.error(`unexpected status: ${resp?.status()}`);
    process.exit(1);
  }

  // Let the hydration cycle settle — we want to capture both the initial
  // paint and the post-await rebuild.
  await page.waitForTimeout(2500);

  const transitions = await page.evaluate(() => window.__breadcrumbTransitions);
  console.log('breadcrumb transitions:');
  for (const t of transitions) {
    console.log(`  +${t.t}ms  hidden=${t.hidden}  class="${t.fullClass}"  (${t.event})`);
  }

  await browser.close();

  // Pass criteria: after the first record, the breadcrumb must never
  // transition to hidden=true. The SSR paints it visible, and it must stay
  // visible through hydration.
  const flashed = transitions.some((t, i) => i > 0 && t.hidden === true);
  if (flashed) {
    console.error('FAIL: breadcrumb visibility flashed during hydration cycle');
    console.error('       (a transition to hidden=true occurred after the initial SSR paint)');
    process.exit(1);
  }
  // Also: initial state must be visible — the SSR did its job.
  if (transitions.length === 0 || transitions[0].hidden) {
    console.error('FAIL: breadcrumb was not visible from the initial paint');
    process.exit(1);
  }
  console.log('PASS: breadcrumb stayed visible throughout hydration.');
}

run().catch((e) => { console.error(e); process.exit(1); });
