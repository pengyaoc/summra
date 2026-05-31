// Reproduce the user's repro:
//   1. Open book page of A Room with a View
//   2. Scroll to chapter 1, click it
//   3. Measure: is the first line cut off?
//   4. Click "Summary" view toggle
//   5. Measure again: any change? Are the back/gear buttons still pointer-events-active?
//   6. Repeat in reverse (click Original)
//
// Logs computed styles and bounding rects at each step so we can pin down
// exactly where the layout breaks and where the click-eating overlay (if any)
// comes from.

import { chromium, webkit } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5003';
const BOOK_URL = `${BASE}/books/a-room-with-a-view`;
const CHAPTER_URL = `${BASE}/books/a-room-with-a-view/chapters/1`;

const MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1';

async function measure(page, label) {
  const data = await page.evaluate(() => {
    const sticky = document.querySelector('#sticky-reading-header');
    const stickyMedium = document.querySelector('#sticky-reading-header-medium');
    const backBtn = document.querySelector('#sticky-back-btn');
    const gearBtn = document.querySelector('#sticky-settings-btn');
    const summaryBtn = document.querySelector('.unified-view-btn[data-mode="summary"]');
    const originalBtn = document.querySelector('.unified-view-btn[data-mode="original"]');
    const section = document.getElementById('chapter-detail-section');
    const wrapper = document.querySelector('.pagination-wrapper');
    const pc = document.querySelector('.pagination-page-container');
    const firstChild = pc?.firstElementChild;
    const settingsPanel = document.getElementById('reading-settings-panel');
    const lightbox = document.querySelector('.lightbox-overlay');
    const adminModal = document.querySelector('.admin-modal');

    const summaryContent = document.getElementById('chapter-summary-content');
    const fulltextSection = document.getElementById('chapter-fulltext-section');
    const fulltext = document.getElementById('chapter-fulltext');
    const summaryText = document.getElementById('chapter-summary-text');

    const rect = (el) => el ? el.getBoundingClientRect() : null;
    const cls = (el) => el ? el.className : null;
    const elAt = (x, y) => {
      const e = document.elementFromPoint(x, y);
      return e ? `${e.tagName}.${e.className || '(no class)'}` : null;
    };
    const pointerEvents = (el) => el ? getComputedStyle(el).pointerEvents : null;

    return {
      sticky: { rect: rect(sticky), classes: cls(sticky), pointerEvents: pointerEvents(sticky) },
      stickyMedium: { rect: rect(stickyMedium), classes: cls(stickyMedium), pointerEvents: pointerEvents(stickyMedium) },
      summaryContent: { rect: rect(summaryContent), classes: cls(summaryContent), display: summaryContent ? getComputedStyle(summaryContent).display : null },
      fulltextSection: { rect: rect(fulltextSection), classes: cls(fulltextSection), display: fulltextSection ? getComputedStyle(fulltextSection).display : null },
      fulltext: { rect: rect(fulltext), classes: cls(fulltext), display: fulltext ? getComputedStyle(fulltext).display : null, childCount: fulltext?.children.length, firstChildClass: fulltext?.firstElementChild?.className },
      summaryText: { rect: rect(summaryText), classes: cls(summaryText), display: summaryText ? getComputedStyle(summaryText).display : null, childCount: summaryText?.children.length, firstChildClass: summaryText?.firstElementChild?.className },
      backBtn: { rect: rect(backBtn), classes: cls(backBtn), pointerEvents: pointerEvents(backBtn) },
      gearBtn: { rect: rect(gearBtn), classes: cls(gearBtn), pointerEvents: pointerEvents(gearBtn) },
      summaryBtn: { rect: rect(summaryBtn), classes: cls(summaryBtn) },
      originalBtn: { rect: rect(originalBtn), classes: cls(originalBtn) },
      section: { rect: rect(section), classes: cls(section) },
      wrapper: { rect: rect(wrapper) },
      pageContainer: { rect: rect(pc) },
      firstChild: { rect: rect(firstChild), tag: firstChild?.tagName, text: firstChild?.textContent.slice(0, 60) },
      settingsPanel: { rect: rect(settingsPanel), classes: cls(settingsPanel), pointerEvents: pointerEvents(settingsPanel) },
      lightbox: { rect: rect(lightbox), classes: cls(lightbox), pointerEvents: pointerEvents(lightbox) },
      adminModal: { rect: rect(adminModal), classes: cls(adminModal), pointerEvents: pointerEvents(adminModal) },
      // What's at the screen position of the back button right now?
      elementAtBackBtn: backBtn ? elAt(backBtn.getBoundingClientRect().left + 10, backBtn.getBoundingClientRect().top + 10) : null,
      elementAtGearBtn: gearBtn ? elAt(gearBtn.getBoundingClientRect().right - 10, gearBtn.getBoundingClientRect().top + 10) : null,
      // What sits on top of the first paragraph?
      elementAtFirstParaTop: firstChild ? elAt(firstChild.getBoundingClientRect().left + 10, firstChild.getBoundingClientRect().top + 2) : null,
    };
  });

  console.log(`\n=== ${label} ===`);
  console.log(`sticky:        classes="${data.sticky.classes}" rect=${JSON.stringify(data.sticky.rect)} pe=${data.sticky.pointerEvents}`);
  console.log(`stickyMedium:  classes="${data.stickyMedium.classes}" rect=${JSON.stringify(data.stickyMedium.rect)} pe=${data.stickyMedium.pointerEvents}`);
  console.log(`summaryContent: classes="${data.summaryContent.classes}" display=${data.summaryContent.display} rect=${JSON.stringify(data.summaryContent.rect)}`);
  console.log(`fulltextSection: classes="${data.fulltextSection.classes}" display=${data.fulltextSection.display} rect=${JSON.stringify(data.fulltextSection.rect)}`);
  console.log(`fulltext:      classes="${data.fulltext.classes}" display=${data.fulltext.display} rect=${JSON.stringify(data.fulltext.rect)} children=${data.fulltext.childCount} firstChild=${data.fulltext.firstChildClass}`);
  console.log(`summaryText:   classes="${data.summaryText.classes}" display=${data.summaryText.display} rect=${JSON.stringify(data.summaryText.rect)} children=${data.summaryText.childCount} firstChild=${data.summaryText.firstChildClass}`);
  console.log(`back btn:      classes="${data.backBtn.classes}" rect=${JSON.stringify(data.backBtn.rect)} pe=${data.backBtn.pointerEvents}`);
  console.log(`gear btn:      classes="${data.gearBtn.classes}" rect=${JSON.stringify(data.gearBtn.rect)} pe=${data.gearBtn.pointerEvents}`);
  console.log(`summary btn:   classes="${data.summaryBtn.classes}" rect=${JSON.stringify(data.summaryBtn.rect)}`);
  console.log(`original btn:  classes="${data.originalBtn.classes}" rect=${JSON.stringify(data.originalBtn.rect)}`);
  console.log(`section:       classes="${data.section.classes}" rect=${JSON.stringify(data.section.rect)}`);
  console.log(`wrapper:       rect=${JSON.stringify(data.wrapper.rect)}`);
  console.log(`pageContainer: rect=${JSON.stringify(data.pageContainer.rect)}`);
  console.log(`firstChild <${data.firstChild.tag}>: rect=${JSON.stringify(data.firstChild.rect)}`);
  console.log(`  text: "${data.firstChild.text}"`);
  console.log(`settingsPanel: classes="${data.settingsPanel.classes}" rect=${JSON.stringify(data.settingsPanel.rect)} pe=${data.settingsPanel.pointerEvents}`);
  console.log(`lightbox:      classes="${data.lightbox.classes}" rect=${JSON.stringify(data.lightbox.rect)} pe=${data.lightbox.pointerEvents}`);
  console.log(`adminModal:    classes="${data.adminModal.classes}" rect=${JSON.stringify(data.adminModal.rect)} pe=${data.adminModal.pointerEvents}`);
  console.log(`elementAtBackBtn:       ${data.elementAtBackBtn}`);
  console.log(`elementAtGearBtn:       ${data.elementAtGearBtn}`);
  console.log(`elementAtFirstParaTop:  ${data.elementAtFirstParaTop}`);

  // Compute overlap.
  if (data.sticky.rect && data.firstChild.rect) {
    const overlap = data.sticky.rect.bottom - data.firstChild.rect.top;
    console.log(`*** sticky bottom (${data.sticky.rect.bottom}) - first paragraph top (${data.firstChild.rect.top}) = ${overlap}px ${overlap > 0 ? '(OVERLAP)' : '(ok)'}`);
  }
  return data;
}

async function run() {
  const engine = process.env.ENGINE === 'webkit' ? webkit : chromium;
  console.log(`Using engine: ${process.env.ENGINE || 'chromium'}`);
  const browser = await engine.launch();
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 3,
    userAgent: MOBILE_UA,
  });
  const page = await ctx.newPage();
  page.on('console', (m) => { console.log(`[browser:${m.type()}] ${m.text()}`); });
  page.on('pageerror', (e) => console.error(`[browser-pageerror] ${e.message}`));

  // Step 1: book page
  console.log(`\n>>> Step 1: navigate to ${BOOK_URL}`);
  const r1 = await page.goto(BOOK_URL, { waitUntil: 'networkidle' });
  console.log(`HTTP ${r1.status()}`);
  await page.waitForTimeout(500);

  // Step 2: scroll to find chapter 1 link and click it
  console.log(`\n>>> Step 2: scroll and click chapter 1`);
  const chapter1Link = await page.waitForSelector('a[href*="/chapters/1"], .chapter-box a[href$="/1"]', { timeout: 10000 }).catch(() => null);
  if (!chapter1Link) {
    // Fallback: just navigate directly to chapter URL to continue the test
    console.log('Could not find chapter 1 link; navigating directly');
    await page.goto(CHAPTER_URL, { waitUntil: 'networkidle' });
  } else {
    await chapter1Link.scrollIntoViewIfNeeded();
    await chapter1Link.click();
    await page.waitForLoadState('networkidle');
  }

  // Step 3: wait for pagination
  await page.waitForFunction(() => {
    const w = document.querySelector('.pagination-wrapper');
    return w && w.offsetHeight > 100;
  }, { timeout: 15000 });
  await page.waitForTimeout(300);
  await measure(page, 'AFTER chapter load (Original view default)');

  // Step 4: click Summary view button
  const summaryBtn = await page.$('.unified-view-btn[data-mode="summary"]');
  if (summaryBtn) {
    const visible = await summaryBtn.evaluate((b) => !b.classList.contains('hidden') && getComputedStyle(b).display !== 'none');
    if (visible) {
      console.log('\n>>> Step 4: click Summary view button');
      await summaryBtn.click();
      await page.waitForTimeout(800);
      await measure(page, 'AFTER click Summary');
    } else {
      console.log('\n>>> Summary button hidden (chapter has no summary?); skipping');
    }
  }

  // Step 5: click Original view button
  const originalBtn = await page.$('.unified-view-btn[data-mode="original"]');
  if (originalBtn) {
    console.log('\n>>> Step 5: click Original view button');
    await originalBtn.click();
    await page.waitForTimeout(800);
    await measure(page, 'AFTER click Original (back to original)');
  }

  // Step 6: try clicking the back button - does it work?
  console.log('\n>>> Step 6: click back button');
  const backBtnRect = await page.$eval('#sticky-back-btn', (b) => {
    const r = b.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  console.log(`Clicking at (${backBtnRect.x}, ${backBtnRect.y})`);
  await page.mouse.click(backBtnRect.x, backBtnRect.y);
  await page.waitForTimeout(800);
  const urlAfter = page.url();
  console.log(`URL after back click: ${urlAfter}`);
  if (urlAfter === BOOK_URL || urlAfter === BOOK_URL + '/') {
    console.log('Back button WORKED');
  } else {
    console.log(`Back button DID NOT navigate (still at ${urlAfter})`);
  }

  await page.screenshot({ path: 'tests/e2e/screenshots/repro-final-state.png', fullPage: false });

  await browser.close();
}

run().catch((e) => { console.error(e); process.exit(1); });
