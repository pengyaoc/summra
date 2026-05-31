// Measurement harness for the sticky-header overlap bug on Sherlock Ch. VI.
// Loads the chapter on a mobile viewport, captures bounding rects + computed
// styles for the sticky header, .chapter-detail-section, .pagination-wrapper,
// and the first visible block of body text. Prints everything to stdout and
// saves a screenshot so we can correlate measurements with what the eye sees.

import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5003';
const URL = `${BASE}/books/the-adventures-of-sherlock-holmes/chapters/6`;

const VIEWPORTS = [
  { name: 'iphone-12-portrait', width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 3, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1' },
  { name: 'iphone-se-portrait', width: 375, height: 667, isMobile: true, hasTouch: true, deviceScaleFactor: 2, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1' },
  { name: 'pixel-5-portrait', width: 393, height: 851, isMobile: true, hasTouch: true, deviceScaleFactor: 2.75, userAgent: 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36' },
  { name: 'desktop-1024', width: 1024, height: 768, isMobile: false, hasTouch: false, deviceScaleFactor: 1, userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
];

async function measure(page, viewport) {
  // Wait for pagination to settle.
  await page.waitForSelector('.pagination-wrapper', { timeout: 10000 });
  await page.waitForFunction(() => {
    const wrapper = document.querySelector('.pagination-wrapper');
    const text = document.querySelector('.pagination-page-container');
    return wrapper && text && wrapper.offsetHeight > 100 && text.children.length > 0;
  }, { timeout: 10000 });

  // Settle: one more frame.
  await page.waitForTimeout(500);

  const data = await page.evaluate(() => {
    const sticky = document.querySelector('.sticky-reading-header');
    const stickyContent = document.querySelector('.sticky-header-content');
    const section = document.getElementById('chapter-detail-section');
    const content = document.querySelector('.chapter-detail-content');
    const fulltextSection = document.querySelector('.chapter-fulltext-section');
    const fulltext = document.getElementById('chapter-fulltext');
    const wrapper = document.querySelector('.pagination-wrapper');
    const pageContainer = document.querySelector('.pagination-page-container');
    const firstBlock = pageContainer ? pageContainer.querySelector('p, h1, h2, h3, h4, h5, h6, blockquote') : null;
    const progressBar = document.querySelector('.reading-progress-bar');

    const rect = (el) => el ? el.getBoundingClientRect() : null;
    const cs = (el, ...props) => {
      if (!el) return null;
      const s = getComputedStyle(el);
      return Object.fromEntries(props.map(p => [p, s.getPropertyValue(p)]));
    };

    return {
      viewport: { innerWidth: window.innerWidth, innerHeight: window.innerHeight, devicePixelRatio: window.devicePixelRatio },
      sticky: {
        rect: rect(sticky),
        classes: sticky ? sticky.className : null,
        offsetHeight: sticky ? sticky.offsetHeight : null,
        computed: cs(sticky, 'height', 'padding-top', 'padding-bottom', 'border-top-width', 'border-bottom-width', 'position', 'top', 'transform', 'visibility', 'display'),
        contentRect: rect(stickyContent),
        contentComputed: cs(stickyContent, 'height', 'padding-top', 'padding-bottom', 'box-sizing'),
      },
      section: {
        rect: rect(section),
        computed: cs(section, 'padding-top', 'padding-bottom', 'margin-top', 'margin-bottom', 'position', 'top', 'transform'),
      },
      content: {
        rect: rect(content),
        computed: cs(content, 'padding-top', 'margin-top'),
      },
      fulltextSection: {
        rect: rect(fulltextSection),
        computed: cs(fulltextSection, 'padding-top', 'margin-top'),
      },
      fulltext: {
        rect: rect(fulltext),
        computed: cs(fulltext, 'padding-top', 'margin-top'),
      },
      wrapper: {
        rect: rect(wrapper),
        computed: cs(wrapper, 'height', 'max-height', 'padding-top', 'margin-top', 'position', 'top', 'overflow'),
      },
      pageContainer: {
        rect: rect(pageContainer),
        computed: cs(pageContainer, 'padding-top', 'margin-top', 'height', 'overflow'),
        firstChildTag: pageContainer && pageContainer.firstElementChild ? pageContainer.firstElementChild.tagName : null,
      },
      firstBlock: {
        rect: rect(firstBlock),
        tag: firstBlock ? firstBlock.tagName : null,
        text: firstBlock ? firstBlock.textContent.slice(0, 80) : null,
        computed: cs(firstBlock, 'margin-top', 'padding-top'),
      },
      progressBar: {
        rect: rect(progressBar),
        computed: cs(progressBar, 'height', 'position', 'bottom'),
      },
      bodyClasses: document.body.className,
      bodyOverflow: getComputedStyle(document.body).overflow,
    };
  });

  return data;
}

function fmt(rect) {
  if (!rect) return 'null';
  return `top=${rect.top.toFixed(1)} bottom=${rect.bottom.toFixed(1)} height=${rect.height.toFixed(1)}`;
}

async function run() {
  const browser = await chromium.launch();
  const consoleErrors = [];

  for (const vp of VIEWPORTS) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      isMobile: vp.isMobile,
      hasTouch: vp.hasTouch,
      deviceScaleFactor: vp.deviceScaleFactor,
      userAgent: vp.userAgent,
    });
    const page = await ctx.newPage();
    page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(`[${vp.name}] ${msg.text()}`); });
    page.on('pageerror', (err) => consoleErrors.push(`[${vp.name}] pageerror: ${err.message}`));

    console.log(`\n=== ${vp.name} (${vp.width}x${vp.height}) ===`);
    try {
      const resp = await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
      console.log(`HTTP ${resp.status()}`);
      const d = await measure(page, vp);

      console.log(`viewport: innerW=${d.viewport.innerWidth} innerH=${d.viewport.innerHeight} dpr=${d.viewport.devicePixelRatio}`);
      console.log(`body: classes="${d.bodyClasses}" overflow=${d.bodyOverflow}`);
      console.log(`sticky: classes="${d.sticky.classes}" offsetH=${d.sticky.offsetHeight}`);
      console.log(`  rect:           ${fmt(d.sticky.rect)}`);
      console.log(`  computed:       ${JSON.stringify(d.sticky.computed)}`);
      console.log(`  content rect:   ${fmt(d.sticky.contentRect)}`);
      console.log(`  content comp:   ${JSON.stringify(d.sticky.contentComputed)}`);
      console.log(`section:          ${fmt(d.section.rect)}  comp:${JSON.stringify(d.section.computed)}`);
      console.log(`content:          ${fmt(d.content.rect)}  comp:${JSON.stringify(d.content.computed)}`);
      console.log(`fulltextSection:  ${fmt(d.fulltextSection.rect)}  comp:${JSON.stringify(d.fulltextSection.computed)}`);
      console.log(`fulltext:         ${fmt(d.fulltext.rect)}  comp:${JSON.stringify(d.fulltext.computed)}`);
      console.log(`wrapper:          ${fmt(d.wrapper.rect)}  comp:${JSON.stringify(d.wrapper.computed)}`);
      console.log(`pageContainer:    ${fmt(d.pageContainer.rect)}  comp:${JSON.stringify(d.pageContainer.computed)}  firstChildTag=${d.pageContainer.firstChildTag}`);
      console.log(`firstBlock <${d.firstBlock.tag}>: ${fmt(d.firstBlock.rect)}  comp:${JSON.stringify(d.firstBlock.computed)}`);
      console.log(`  text: "${d.firstBlock.text}"`);
      console.log(`progressBar:      ${fmt(d.progressBar.rect)}  comp:${JSON.stringify(d.progressBar.computed)}`);

      const stickyBottom = d.sticky.rect ? d.sticky.rect.bottom : 0;
      const firstBlockTop = d.firstBlock.rect ? d.firstBlock.rect.top : 0;
      const gap = firstBlockTop - stickyBottom;
      console.log(`\n  ==> GAP between sticky bottom and first block top: ${gap.toFixed(1)}px  ${gap < 0 ? '*** OVERLAP ***' : '(ok)'}`);

      const screenshotPath = `tests/e2e/screenshots/sticky-overlap-${vp.name}.png`;
      await page.screenshot({ path: screenshotPath, fullPage: false });
      console.log(`  screenshot: ${screenshotPath}`);
    } catch (e) {
      console.error(`  error: ${e.message}`);
    } finally {
      await ctx.close();
    }
  }

  await browser.close();

  if (consoleErrors.length) {
    console.log('\n=== Console errors ===');
    consoleErrors.forEach(e => console.log(e));
  }
}

run().catch((e) => { console.error(e); process.exit(1); });
