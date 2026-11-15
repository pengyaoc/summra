// Distill Listen: the reader highlights and follows the spoken sentence, not the whole paragraph.
//
//   DISTILL_USER_DB=$TMPDIR/distill_listen_e2e.db PORT=5003 venv/bin/python -m distill.app
//   cd tests/e2e && node distill_listen_sentence.mjs
//
// Recordings made from 2026-11-14 carry sentence timings. For an older book the test gives
// its units sentence timings in the page; a newly recorded book (DISTILL_LISTEN_SLUG) is
// tested on its real ones. Exits 1 on any FAIL or page error.

import { webkit } from 'playwright';
import { mkdirSync } from 'node:fs';
import { sentenceAt, locateSentences } from '../../shared/static/js/sentence_follow.js';

const BASE = process.env.BASE_URL || 'http://localhost:5003';
const SLUG = process.env.DISTILL_LISTEN_SLUG || 'abundance-klein-thompson';
const SHOTS = new URL('./screenshots/', import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.error(`FAIL: ${msg}`); } else console.log(`ok   ${msg}`); };

// Pure helpers.
const unit = { paragraph_id: '5.1', start_ms: 1000, end_ms: 4000, sentences: [[1000, 1800, 'One.', 4], [1950, 3000, 'Twoa', 9], [3150, 4000, 'Thre', 5]] };
check(sentenceAt(unit, 1000) === 0 && sentenceAt(unit, 1900) === 0, 'sentenceAt: a sentence keeps the gap after it');
check(sentenceAt(unit, 2000) === 1 && sentenceAt(unit, 99999) === 2, 'sentenceAt: later sentences, clamped at the end');
check(sentenceAt(unit, 0) === 0, 'sentenceAt: before the unit gives its first sentence');
check(sentenceAt({ paragraph_id: '5.2', start_ms: 0, end_ms: 1 }, 0) === -1, 'sentenceAt: an older recording has no sentences');
check(sentenceAt({ ...unit, sentences: [] }, 1500) === -1, 'sentenceAt: a unit with no sentences');
// The page shows "1." and "•" before list items, and a "Key points" label; heads skip past them.
check(JSON.stringify(locateSentences('1.One.2.Twoapples•Three', unit.sentences)) === '[[2,6],[8,17],[18,23]]',
  'locateSentences: sentences found in order, skipping list numbers and bullets');
check(locateSentences('One.Three', unit.sentences) === null, 'locateSentences: a missing sentence gives null (paragraph highlight)');
check(locateSentences('One.', [[0, 1, 'One.', 7]]) === null, 'locateSentences: a sentence running past the text gives null');
check(locateSentences('', []) === null, 'locateSentences: nothing to find gives null');

const browser = await webkit.launch({ headless: !process.env.HEADED });
const problems = [];
const context = await browser.newContext({ viewport: { width: 375, height: 667 } });
const page = await context.newPage();
page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));

await page.goto(`${BASE}/login`);
await page.waitForURL(`${BASE}/`);
await page.waitForFunction(() => !document.querySelector('[data-listen-book][disabled]'));
const book = await (await page.request.get(`${BASE}/api/books/${SLUG}/audio`)).json();
const first = book.chapters[0];
await page.goto(`${BASE}/books/${SLUG}/read?chapter=${first.chapter_id}`);
await page.waitForSelector('#listen-button', { state: 'visible', timeout: 15000 });
await page.locator('#listen-button').click();
await page.waitForFunction(() => window.distillAudio?.player?.audio?.currentTime > 0.3, null, { timeout: 15000 });
await page.evaluate(() => window.distillAudio.player.pause());

// An older recording gets sentence timings made from its own page text: split at ". ",
// times spread evenly. Either way, find a paragraph whose sentences span pages.
const candidates = await page.evaluate(() => {
  const { player, link } = window.distillAudio;
  const reader = link.reader;
  const textOf = (id) => reader.pagination.pages.map((html) => {
    const box = document.createElement('div');
    box.innerHTML = html;
    return [...box.querySelectorAll(`[data-reader-anchor="${id}"]`)].map((a) => a.textContent).join(' ');
  }).join(' ');
  const pagesOf = (id) => reader.pagination.pages.flatMap((html, i) => (html.includes(`data-reader-anchor="${id}"`) ? [i] : []));
  const recorded = player.timings.some((timing) => timing.sentences?.length);
  const spanning = [];
  for (const timing of player.timings) {
    if (!recorded) {
      const text = textOf(timing.paragraph_id).replace(/^\s*(\d+\.|•)\s*/, '');
      const sentences = text.split(/(?<=[.!?])\s+(?=[A-Z])/).map((s) => s.trim()).filter(Boolean);
      const step = (timing.end_ms - timing.start_ms) / sentences.length;
      timing.sentences = sentences.map((s, i) => [Math.round(timing.start_ms + i * step), Math.round(timing.start_ms + (i + 1) * step), s.replace(/\s/g, '').slice(0, 16), s.replace(/\s/g, '').length]);
    }
    if (timing.sentences?.length > 1 && pagesOf(timing.paragraph_id).length > 1) {
      spanning.push({ recorded, id: timing.paragraph_id, sentences: timing.sentences, pages: pagesOf(timing.paragraph_id) });
    }
  }
  return spanning;
});
const bare = (text) => (text || '').replace(/\s/g, '');
// The highlight follows the playing audio (a paused seek only moves the place).
await page.evaluate(() => window.distillAudio.player.resume());

const sentenceHighlight = () => page.evaluate(() => {
  const h = CSS.highlights.get('listen-sentence');
  const range = h && [...h][0];
  return { text: range ? range.toString().replace(/\s+/g, ' ').trim() : null,
    paragraphs: document.querySelectorAll('#continuous-reader-content .listen-current').length,
    page: window.distillAudio.link.reader.pagination.currentPage };
});
const seek = async (ms) => {
  await page.evaluate((m) => window.distillAudio.player.seekToMs(m), ms);
  await page.waitForTimeout(500);
};

// Where each sentence starts, worked out here from the page text: page fragments in order.
const startPagesOf = (candidate) => page.evaluate(({ id, sentences }) => {
  const reader = window.distillAudio.link.reader;
  let text = '';
  const starts = [];
  reader.pagination.pages.forEach((html, index) => {
    const box = document.createElement('template');
    box.innerHTML = html;
    const shown = [...box.content.querySelectorAll(`[data-reader-anchor="${id}"]`)].map((a) => a.textContent).join('').replace(/\s/g, '');
    if (shown) { starts.push([index, text.length]); text += shown; }
  });
  let from = 0;
  return sentences.map((s) => {
    const at = text.indexOf(s[2], from);
    from = at + s[3];
    return starts.filter(([, start]) => start <= at).pop()[0];
  });
}, candidate);
let split = null;
let startPage = [];
for (const candidate of candidates) {
  const pages = await startPagesOf(candidate);
  if (pages.some((p) => p > pages[0])) { split = candidate; startPage = pages; break; }
}
check(!!split, `a paragraph has sentences starting on two pages (${split?.id}, ${split?.recorded ? 'recorded' : 'injected'} sentence timings)`);
const s0 = split.sentences[0];
const later = split.sentences.findIndex((_, i) => startPage[i] > startPage[0]);
check(later > 0, `a sentence of ${split.id} starts on a later page (sentence ${later}, pages ${startPage.join(',')})`);
const s1 = split.sentences[later];

await seek(s0[0] + 20);
let shown = await sentenceHighlight();
check(bare(shown.text).startsWith(s0[2]) && bare(shown.text).length <= s0[3],
  `only the spoken sentence is highlighted ("${shown.text?.slice(0, 40)}…")`);
check(shown.paragraphs === 0, 'the paragraph is not highlighted as a whole');
check(shown.page === startPage[0], 'the page where the sentence starts is on screen');
await page.screenshot({ path: `${SHOTS}distill_listen_sentence.png` });

await seek(s1[0] + 20);
shown = await sentenceHighlight();
check(shown.page === startPage[later], `following turns the page when the next sentence starts there (page ${shown.page})`);
check(bare(shown.text).startsWith(s1[2]) && bare(shown.text).length <= s1[3], 'that sentence is highlighted there');

// A sentence that runs onto the next page: its start stays on screen, highlighted up to the page end.
const lastPage = split.pages[split.pages.length - 1];
const runs = split.sentences.findIndex((_, i) => startPage[i] < (i + 1 < startPage.length ? startPage[i + 1] : lastPage));
if (runs >= 0) {
  await seek(split.sentences[runs][0] + 20);
  shown = await sentenceHighlight();
  check(shown.page === startPage[runs] && bare(shown.text).startsWith(split.sentences[runs][2]) && bare(shown.text).length < split.sentences[runs][3],
    'a sentence running onto the next page stays on its first page, highlighted to the page end');
}

await seek(s0[0] + 20);
shown = await sentenceHighlight();
check(shown.page === startPage[0], 'seeking back turns back to the earlier page');

// Sentence heads that are not on the page fall back to the paragraph highlight.
await page.evaluate((id) => {
  const timing = window.distillAudio.player.timings.find((t) => t.paragraph_id === id);
  timing.sentences = timing.sentences.map((s) => [s[0], s[1], 'nothinglikethis', 15]);
}, split.id);
await seek(s1[0] + 40);
shown = await sentenceHighlight();
check(shown.text === null && shown.paragraphs > 0, 'unmatched sentences fall back to the paragraph highlight');
await page.evaluate(() => window.distillAudio.player.pause());

check(problems.length === 0, `no page errors${problems.length ? ': ' + problems.join('; ') : ''}`);
await browser.close();
console.log(failures ? `\n${failures} failure(s)` : '\nall checks passed');
process.exit(failures ? 1 : 0);
