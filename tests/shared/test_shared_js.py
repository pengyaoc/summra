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
