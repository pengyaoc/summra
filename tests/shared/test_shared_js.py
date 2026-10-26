"""Shared reader JS (shared/static/js), run under node with stubbed browser
globals. Mixin files are imported from a data: URL, so they must not import."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _node(script):
    subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, check=True)


def test_reader_state_cache_db_from_config():
    """Two apps on one origin must not share an IndexedDB segment cache."""
    _node(r"""
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source = fs.readFileSync('shared/static/js/reader_state.js', 'utf8');
const opened = [];
const sandbox = {
    window: {READER_CONFIG: {cache_db_name: 'distill-reader-v1'}},
    indexedDB: {open: (name, version) => { opened.push([name, version]); return {}; }},
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
sandbox.window.readerState.readerDb();
assert.deepEqual(opened, [['distill-reader-v1', 2]]);
assert.equal(sandbox.window.readerState.currentUser(), null);
assert.equal(sandbox.window.readerState.wrongAccountEmail(), null);
""")


def test_extra_page_blocks_appended_only_when_configured():
    _node(r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const load = path => import('data:text/javascript;base64,' + Buffer.from(fs.readFileSync(path, 'utf8')).toString('base64'));
const {paginationMixin} = await load('shared/static/js/pagination.js');
const {readerUtilsMixin} = await load('shared/static/js/reader_utils.js');
console.log = () => {};
globalThis.document = {querySelector: () => null};
const selectorFor = extra => {
    globalThis.window = {innerHeight: 800, READER_CONFIG: {extra_page_blocks: extra}};
    let selector = null;
    const container = {
        innerHTML: '', classList: {contains: () => false}, closest: () => null,
        querySelectorAll: value => { selector = value; return []; },
    };
    const app = {...readerUtilsMixin, ...paginationMixin, pagination: {}};
    app.calculatePages(container);
    return selector;
};
const fixed = 'p, h1, h2, h3, h4, h5, h6, blockquote, pre, ul, ol, figure.reader-illustration';
assert.equal(selectorFor(''), fixed);
assert.equal(selectorFor('table.distill-table, div.distill-callout'), fixed + ', table.distill-table, div.distill-callout');
""")


def test_continuation_segments_do_not_repeat_chapter_heading():
    """A chunk starting mid-poem is a continuation, not a new book."""
    import subprocess
    from pathlib import Path

    script = r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source = fs.readFileSync('shared/static/js/continuous_reader.js', 'utf8');
const {continuousReaderMixin} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const utils = fs.readFileSync('shared/static/js/reader_utils.js', 'utf8');
const {readerUtilsMixin} = await import('data:text/javascript;base64,' + Buffer.from(utils).toString('base64'));
globalThis.window = {READER_CONFIG: {modes: [{id: 'original', label: 'Original', layout: 'single', members: []}]}};
const container = {};
globalThis.document = {getElementById: () => container};
const stop = new Error('captured');
const app = {
    ...readerUtilsMixin,
    ...continuousReaderMixin,
    continuousReader: {active: true, mode: 'original'},
    pagination: {},
    escapeHtml: value => value,
    continuousReaderBlock: content => ({tag: 'p', content}),
    continuousIllustrationHtml: () => '<figure>illustration</figure>',
    initializePagination: () => {throw stop;},
};
for (const ordinal of [0, 80, 160]) {
    try {
        app.renderContinuousSegments([{units: [{id: 'p', chapter_id: 1,
            chapter_title: 'Book I', chapter_ordinal: ordinal,
            content: 'A verse line', word_count: 3}]}]);
    } catch (error) {if (error !== stop) throw error;}
    assert.equal(container.innerHTML.includes('reader-chapter-heading'), ordinal === 0);
    assert.equal(container.innerHTML.includes('<figure>'), ordinal === 0);
    assert.ok(container.innerHTML.includes('A verse line'));
}
"""
    subprocess.run(['node', '--input-type=module', '-e', script],
                   cwd=Path(__file__).resolve().parents[2], check=True)


def test_pagination_text_units_break_chinese_without_splitting_english_words():
    _node(r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source = fs.readFileSync('shared/static/js/pagination.js', 'utf8');
const {paginationMixin: app} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
globalThis.NodeFilter = {SHOW_TEXT: 4};
globalThis.document = {createTreeWalker(el) {
    let index = 0;
    return {nextNode: () => el.nodes[index++] || null};
}};
const units = text => app.textUnits({classList: {contains: () => false}, nodes: [{data: text}]}).texts;
assert.deepEqual(units('An ordinary English paragraph.'), ['An', 'ordinary', 'English', 'paragraph.']);
const chinese = '细胞是生命的基本单位。1821年，研究DNA与细胞。';
assert.ok(units(chinese).length > 15, 'Chinese paragraphs must offer breakpoints without spaces');
assert.equal(units(chinese).join(''), chinese, 'No Chinese text or punctuation lost');
assert.ok(units(chinese).includes('DNA'), 'Latin words in Chinese remain whole');
assert.ok(units('𠮷野家').includes('𠮷'), 'Never split a supplementary Han character in half');
""")


def test_chinese_split_paragraph_marker_round_trip():
    _node(r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source = fs.readFileSync('shared/static/js/continuous_reader.js', 'utf8');
const {continuousReaderMixin} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const fragments = ['细'.repeat(100), '胞'.repeat(200), '传'.repeat(200)];
const anchor = text => ({dataset: {readerAnchor: '1.0', readerWordCount: '1'}, textContent: text});
globalThis.document = {createElement() {
    return {set innerHTML(value) {this.index = Number(value);},
        querySelectorAll() {return [anchor(fragments[this.index])];}};
}};
const app = {...continuousReaderMixin,
    readerLayout: () => 'single',
    continuousReader: {mode: 'summary', unitsById: new Map([['1.0', {word_count: 1}]])},
    pagination: {pages: ['0','1','2'], currentPage: 1},
};
assert.equal(app.continuousMarkerOffset(anchor(fragments[1])), .2);
app.pagination.currentPage = 2;
assert.equal(app.continuousMarkerOffset(anchor(fragments[2])), .6);
assert.equal(app.findContinuousPageForMarker({paragraph_id: '1.0', offset: .2}), 1);
assert.equal(app.findContinuousPageForMarker({paragraph_id: '1.0', offset: .6}), 2);
""")


def test_leaving_reader_unlocks_before_slow_save_and_cancels_timers():
    _node(r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const load = async path => import('data:text/javascript;base64,' + Buffer.from(fs.readFileSync(path, 'utf8')).toString('base64'));
const {continuousReaderMixin} = await load('shared/static/js/continuous_reader.js');
const {paginationMixin} = await load('shared/static/js/pagination.js');
const classes = values => ({values: new Set(values), remove(...names) {names.forEach(name => this.values.delete(name));}, add(...names) {names.forEach(name => this.values.add(name));}});
const html = {style: {overflow:'hidden'}, classList: classes(['pagination-active'])};
const body = {style: {overflow:'hidden'}, classList: classes(['pagination-active','on-reader-page','on-chapter-page'])};
const panels = new Map(['reading-settings-panel','reader-toc-panel'].map(id => [id,{classList:classes([])}]));
globalThis.document = {documentElement: html, body, getElementById: id => panels.get(id)};
let finishSave, fired = false;
const saving = new Promise(resolve => {finishSave=resolve;});
const app = {...paginationMixin, ...continuousReaderMixin,
    pagination: {pages:['page'], totalPages:1, wheelTimeout: setTimeout(() => {fired=true;}, 5)},
    continuousReader: {active:true, settleTimer:setTimeout(() => {fired=true;},5), terminalTimer:setTimeout(() => {fired=true;},5)},
    saveContinuousReader(cause) {assert.equal(cause,'navigation'); assert.equal(this.continuousReader.active,true); return saving;},
};
const pending = app.leaveContinuousReader();
assert.equal(app.continuousReader.active,false);
assert.equal(html.style.overflow,''); assert.equal(body.style.overflow,'');
assert.equal(body.classList.values.has('on-reader-page'),false);
assert.equal(html.classList.values.has('pagination-active'),false);
assert.equal(app.pagination.totalPages,0);
for (const panel of panels.values()) assert.ok(panel.classList.values.has('hidden'));
await new Promise(resolve => setTimeout(resolve,15));
assert.equal(fired,false,'Late wheel/save/completion work must be cancelled');
finishSave(); await pending;
""")


def test_reader_load_finishing_after_exit_does_not_render():
    _node(r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source=fs.readFileSync('shared/static/js/continuous_reader.js','utf8');
const {continuousReaderMixin}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
let release; const loaded=new Promise(resolve => {release=resolve;});
const reader={active:true, mode:'summary', manifest:{segments:[{id:'s',mode:'summary',ordinal:0}]}};
let renders=0;
globalThis.document={getElementById:()=>null};
const app={...continuousReaderMixin, continuousReader:reader,
    fetchContinuousSegment:()=>loaded, renderContinuousSegments:()=>{renders++;}};
const pending=app.loadContinuousReaderAt();
reader.active=false;
release({id:'s'}); await pending;
assert.equal(renders,0,'An exited reader must not paginate after a delayed fetch');
""")


def test_reader_bfcache_restores_pagination_only_for_reader_document():
    _node(r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source=fs.readFileSync('shared/static/js/continuous_reader.js','utf8');
const {continuousReaderMixin}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const listeners={};
globalThis.document={addEventListener(){},body:{classList:{add(){}}}};
globalThis.window={addEventListener(name,fn){listeners[name]=fn;},setInterval(){}};
const reader={active:true,currentMarker:{chapter_id:42}};
let saves=0,loads=0;
const app={...continuousReaderMixin, currentView:'reader',continuousReader:reader,
    readerConfig:()=>({modes:[]}), leaveContinuousReader(cause){assert.equal(cause,'pagehide');saves++;reader.active=false;},
    loadContinuousReaderAt(marker,chapter){assert.equal(chapter,42);loads++;}};
app.setupContinuousReaderLifecycle();
listeners.pagehide({persisted:true});
assert.equal(reader.active,false);
listeners.pageshow({persisted:true});
assert.equal(reader.active,true); assert.equal(loads,1); assert.equal(saves,1);
app.currentView='book';
listeners.pagehide({persisted:true});
listeners.pageshow({persisted:true});
assert.equal(loads,1,'Restoring a book document must not reactivate the reader');
""")
