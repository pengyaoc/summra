"""Reader manifest segment descriptors list the chapters each segment holds.

Bug this guards against: opening the reader at a chapter (legacy
/books/<slug>/chapters/<n> links, chapter jumps) had to download segments
one at a time from the start of the book until it found one containing that
chapter — N sequential round trips for chapter N. With chapter_ids on each
descriptor the client picks the right segment straight from the manifest.
"""
import pytest


@pytest.fixture
def book(test_db_path):
    from plainly import models
    db = models.Database(db_path=test_db_path)
    book_id = db.add_book(title='Segmented', author='A', filename='seg.txt', full_text='x')

    def paras(prefix, n):
        return '\n\n'.join(f'{prefix} paragraph {i}.' for i in range(n))

    # Segments hold <= 80 units, so chapter 1 spans two segments, chapter 2
    # shares one, and chapter 3 spans the rest.
    for number, count in ((1, 100), (2, 10), (3, 120)):
        db.add_chapter(book_id, number, f'Ch {number}', 'Summary.',
                       paras(f'Original {number}', count),
                       modern_english_text=paras(f'Plain {number}', count))
    return db, book_id


def test_every_descriptor_lists_its_units_chapters(book):
    db, book_id = book
    manifest = db.get_reader_manifest(book_id)
    checked_modes = set()
    for descriptor in manifest['segments']:
        segment = db.get_reader_segment(book_id, descriptor['id'], descriptor['mode'])
        expected = list(dict.fromkeys(unit['chapter_id'] for unit in segment['units']))
        assert descriptor['chapter_ids'] == expected, descriptor['mode']
        checked_modes.add(descriptor['mode'])
    assert {'original', 'plain', 'side_by_side'} <= checked_modes


def test_chapter_lookup_needs_only_the_manifest(book):
    db, book_id = book
    manifest = db.get_reader_manifest(book_id)
    chapter_3 = next(e['chapter_id'] for e in manifest['structure'] if e.get('chapter_number') == 3)
    original = [d for d in manifest['segments'] if d['mode'] == 'original']
    first = next(d for d in original if chapter_3 in d['chapter_ids'])
    assert first['ordinal'] > 0  # not in the first segment: a scan would need >1 fetch
    units = db.get_reader_segment(book_id, first['id'], 'original')['units']
    assert any(u['chapter_id'] == chapter_3 for u in units)


def test_section_title_change_rebuilds_reader_structure(book):
    db, book_id = book
    conn = db.get_connection()
    with conn:
        conn.execute(
            "INSERT INTO book_sections (book_id, section_type, section_number, section_title) "
            "VALUES (?, 'PART', 1, 'Part One')", (book_id,)
        )
        section_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.execute('UPDATE chapters SET section_id = ? WHERE book_id = ?', (section_id, book_id))
    first = db.get_reader_manifest(book_id)
    with conn:
        conn.execute('UPDATE book_sections SET section_title = ? WHERE id = ?', ('Part I', section_id))
    conn.close()
    second = db.get_reader_manifest(book_id)
    assert second['content_version'] > first['content_version']
    assert any(entry['title'] == 'Part I' for entry in second['structure'])


def test_continuation_segments_do_not_repeat_chapter_heading():
    """A chunk starting mid-poem is a continuation, not a new book."""
    import subprocess
    from pathlib import Path

    script = r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source = fs.readFileSync('frontend/static/js/reader.js', 'utf8');
const {readerMixin} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const container = {};
globalThis.document = {getElementById: () => container};
const stop = new Error('captured');
const app = {
    ...readerMixin,
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
