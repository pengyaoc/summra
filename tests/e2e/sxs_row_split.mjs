// Side-by-side rows split across pages without losing text.
//
// Bugs this guards against:
//  1. A row taller than a page was force-placed whole and clipped by the
//     page's overflow:hidden. The split searched one column while keeping the
//     other column whole, which already overflowed, so it never found a fit
//     (Tess's preface lost the end of its long paragraphs).
//  2. A row was split only when it started a page; otherwise it moved to the
//     next page, so every page began at a paragraph and left a blank tail.
//  3. Splits lost <em>. Each column must fill the page on its own and continue
//     on the next one; cutting both at the same point (word count or fraction)
//     left the shorter column stopped mid-sentence above blank space.
//  4. Verse passages (Paradise Lost) must split between lines, never mid-line.
//
// Run: node sxs_row_split.mjs   (Flask on :5001)

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5001';
const failures = [];
const check = (ok, msg) => { if (!ok) failures.push(msg); else console.log(`ok - ${msg}`); };

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.summraApp, null, { timeout: 10000 });

  const run = (rowsHtml) => page.evaluate((html) => {
    const app = window.summraApp;
    const container = document.createElement('div');
    container.className = 'continuous-reader-content chapter-side-by-side';
    container.style.width = '1100px';
    container.innerHTML = `<div class="side-by-side-headers"><div class="side-by-side-header">Original</div><div class="side-by-side-header">Plain English</div></div>${html}`;
    document.body.appendChild(container);
    // Re-measure pages in a box shaped like the paginator's (same width and
    // padding as the container), not the nominal 1100px.
    const cs = getComputedStyle(container);
    const box = `width:${container.offsetWidth}px;padding:${cs.padding};box-sizing:${cs.boxSizing};font-size:${cs.fontSize};line-height:${cs.lineHeight}`;
    app.calculatePages(container);
    container.remove();
    // Re-measure every page at the real page height to detect clipping.
    const height = app.pagination.containerHeight;
    const overflow = app.pagination.pages.map((pageHtml) => {
      const div = document.createElement('div');
      div.className = 'pagination-page-container chapter-side-by-side';
      div.style.cssText = `position:absolute;left:-9999px;${box};height:${height}px;overflow:hidden`;
      div.innerHTML = pageHtml; // measured as shown, header band included
      document.body.appendChild(div);
      const over = div.scrollHeight > height + 1;
      div.remove();
      return over;
    });
    const slack = app.pagination.pages.map((pageHtml) => {
      const div = document.createElement('div');
      div.className = 'pagination-page-container chapter-side-by-side';
      div.style.cssText = `position:absolute;left:-9999px;${box};height:${height}px;overflow:hidden`;
      div.innerHTML = pageHtml; // measured as shown, header band included
      document.body.appendChild(div);
      const bottom = div.getBoundingClientRect().top + height;
      const rows = div.querySelectorAll('.side-by-side-row');
      const last = rows[rows.length - 1];
      const gap = (sel) => {
        const el = last?.querySelector(`${sel} > *`);
        return el ? Math.round(bottom - el.getBoundingClientRect().bottom) : null;
      };
      const out = { left: gap('.side-by-side-cell.original'), right: gap('.side-by-side-cell.modern'), lineHeight: parseFloat(getComputedStyle(div).lineHeight) || 28 };
      div.remove();
      return out;
    });
    const cols = app.pagination.pages.map((pageHtml) => {
      const div = document.createElement('div');
      div.innerHTML = pageHtml;
      const text = (sel) => [...div.querySelectorAll(sel)].map((el) => el.textContent).join(' ');
      return {
        left: text('.side-by-side-cell.original'),
        right: text('.side-by-side-cell.modern'),
        leftHtml: [...div.querySelectorAll('.side-by-side-cell.original')].map((el) => el.innerHTML).join(''),
      };
    });
    return { overflow, cols, slack };
  }, rowsHtml);

  const words = (n, tag) => Array.from({ length: n }, (_, i) => `${tag}${i}${i % 12 === 11 ? '.' : ''}`).join(' ');
  const tokens = (s, tag) => (s.match(new RegExp(`\\b${tag}\\d+`, 'g')) || []);
  const row = (left, right) => `<div class="side-by-side-row reader-alignment-row" data-reader-anchor="a"><div class="side-by-side-cell original"><p>${left}</p></div><div class="side-by-side-cell modern"><p>${right}</p></div></div>`;

  // 1. Huge row: nothing clipped, every word kept exactly once, <em> kept.
  {
    const { overflow, cols, slack } = await run(row(`<em>first</em> ${words(1500, 'L')}`, words(500, 'R')));
    const left = cols.flatMap((c) => tokens(c.left, 'L'));
    const right = cols.flatMap((c) => tokens(c.right, 'R'));
    check(!overflow.some(Boolean), `huge row: no page overflows (${overflow.filter(Boolean).length}/${overflow.length} overflow)`);
    check(left.length === 1500 && new Set(left).size === 1500, `huge row: all 1500 original words once (got ${left.length})`);
    check(right.length === 500 && new Set(right).size === 500, `huge row: all 500 plain words once (got ${right.length})`);
    check(cols[0].leftHtml.includes('<em>first</em>'), 'huge row: emphasis survives the split');

    // 3. Each column fills the page until its text runs out: the shorter
    // Plain English column must not stop early above blank space.
    const rightPages = cols.filter((c) => tokens(c.right, 'R').length).length;
    const underfilled = slack.slice(0, rightPages - 1).map((g, i) => [i + 1, g.right, g.lineHeight])
      .filter(([, gap, lh]) => gap > lh * 1.5);
    check(!underfilled.length, `huge row: plain column fills every page it continues from (${underfilled.map(([p, g]) => `page ${p} gap ${g}px`).join(', ') || 'all full'})`);
    check(rightPages < cols.length, `huge row: shorter plain column finishes before the original (${rightPages} of ${cols.length} pages)`);
  }

  // 2. A long row after a short one starts on the same page.
  {
    const { cols } = await run(row(words(40, 'S'), words(35, 'T')) + row(words(600, 'L'), words(500, 'R')));
    check(tokens(cols[0].left, 'L').length > 0, `long row begins on page 1 under a short row (${tokens(cols[0].left, 'L').length} words there)`);
  }

  // 4. Verse passage splits between lines; each line stays whole.
  {
    const lines = Array.from({ length: 120 }, (_, i) => `verse V${i} line with several words${i % 6 === 5 ? '.' : ','}`);
    const verse = `<p class="reader-verse">${lines.join('<br>\n')}</p>`;
    const { overflow, cols } = await run(`<div class="side-by-side-row reader-alignment-row" data-reader-anchor="v"><div class="side-by-side-cell original">${verse}</div><div class="side-by-side-cell modern"><p>${words(900, 'R')}</p></div></div>`);
    const seen = cols.flatMap((c) => tokens(c.left, 'V'));
    const whole = cols.every((c) => c.leftHtml.split(/<br>/).every((frag) => {
      const t = frag.replace(/<[^>]+>/g, '').trim();
      return !t || /^verse V\d+ line with several words[.,]$/.test(t);
    }));
    check(!overflow.some(Boolean), 'verse row: no page overflows');
    check(cols.length > 1 && seen.length === 120 && new Set(seen).size === 120, `verse row: all 120 lines once over ${cols.length} pages (got ${seen.length})`);
    check(whole, 'verse row: every page breaks between lines');
  }

  // 5. Verse paragraph in a single-column mode also splits between lines.
  {
    const result = await page.evaluate(() => {
      const app = window.summraApp;
      const lines = Array.from({ length: 150 }, (_, i) => `verse W${i} line with several words,`);
      const container = document.createElement('div');
      container.style.width = '700px';
      container.innerHTML = `<p class="reader-verse">${lines.join('<br>\n')}</p>`;
      document.body.appendChild(container);
      app.calculatePages(container);
      container.remove();
      return app.pagination.pages;
    });
    const ok = result.length > 1 && result.every((html) => html.split(/<br>/).every((frag) => {
      const t = frag.replace(/<[^>]+>/g, '').trim();
      return !t || /^verse W\d+ line with several words,$/.test(t);
    }));
    check(ok, `verse paragraph: ${result.length} pages, split between lines`);
  }

  // 6. Real reader: pages measured off-page must fit when shown. Reader CSS
  // scoped to .continuous-reader-section (row padding, borders) used to be
  // missing from the body-level measuring box, so live pages overflowed.
  {
    const reader = await browser.newPage({ viewport: { width: 1400, height: 860 } });
    await reader.route(/\/api\/auth\/check/, (r) => r.fulfill({ json: { authenticated: false } }));
    await reader.route(/\/api\/progress/, (r) => r.fulfill({ json: { success: true } }));
    await reader.goto(`${BASE}/books/tess-of-the-durbervilles/read?mode=side_by_side`, { waitUntil: 'domcontentloaded' });
    await reader.waitForFunction(() => window.summraApp?.pagination?.pages?.length > 1, null, { timeout: 20000 });
    const overflowing = [];
    for (let i = 0; i < 8; i += 1) {
      const over = await reader.evaluate(() => {
        const live = document.querySelector('.pagination-page-container');
        return live.scrollHeight > live.clientHeight + 1 ? `${live.scrollHeight}>${live.clientHeight}` : null;
      });
      if (over) overflowing.push(`page ${i + 1}: ${over}`);
      await reader.evaluate(() => window.summraApp.navigateToNextPage());
      await reader.waitForTimeout(100);
    }
    check(!overflowing.length, `Tess side-by-side: first 8 live pages fit (${overflowing.join(', ') || 'none overflow'})`);
    await reader.close();
  }

  // Verse units from the reader render as lines.
  {
    const block = await page.evaluate(() => window.summraApp.continuousReaderBlock('Of Man’s first *disobedience*\nOf that forbidden tree'));
    check(block.className.includes('reader-verse') && /disobedience<\/em><br>\nOf that/.test(block.content), `verse unit renders with line breaks (${JSON.stringify(block)})`);
  }
} finally {
  await browser.close();
}

if (failures.length) {
  failures.forEach((f) => console.error(`FAIL: ${f}`));
  process.exit(1);
}
console.log('PASS');
