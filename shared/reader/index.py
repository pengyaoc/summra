"""Continuous-reader index and query surface, shared by every content app.

Book text lives only in the host's own tables: a reader unit is a
paragraph's coordinates (chapter, ordinal) plus the counts the manifest
needs, and segment text is re-split from the host's chapters on read with
the same function that compiled the units. One version row per book; a
recompile replaces its units.
"""
import hashlib
import re
import sqlite3
from typing import Dict, List, Optional


def create_reader_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_version (
                book_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                source_checksum TEXT NOT NULL,
                manifest_etag TEXT NOT NULL,
                verse INTEGER NOT NULL DEFAULT 0,
                plain_coverage INTEGER NOT NULL DEFAULT 0
            )
        ''')
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_unit (
                book_id INTEGER NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('summary', 'original', 'plain', 'side_by_side')),
                ordinal INTEGER NOT NULL,
                chapter_id INTEGER NOT NULL,
                chapter_ordinal INTEGER NOT NULL,
                segment INTEGER NOT NULL,
                word_count INTEGER NOT NULL,
                word_start INTEGER NOT NULL,
                byte_count INTEGER NOT NULL,
                gap INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (book_id, mode, ordinal)
            ) WITHOUT ROWID
        ''')
    cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reader_unit_chapter
            ON reader_unit(book_id, mode, chapter_id, chapter_ordinal)
        ''')


class ReaderIndexMixin:
    """Reader index over a host's content. The host class implements:

    - get_connection() -> sqlite3.Connection (row_factory = sqlite3.Row)
    - get_book(book_id) -> Optional[dict]; the manifest's `book` block reads
      id, slug, title, author and cover_image_url from it
    - _reader_load_book(conn, book_id) -> Optional[dict] {'id', 'verse': bool}
    - _reader_load_chapters(conn, book_id, chapter_ids=None) -> list[dict],
      in reading order, each with at least id, chapter_number, chapter_title
    - _reader_chapter_units(chapter, verse, plain_coverage)
      -> {'summary'|'original'|'plain': list[Optional[str]]}; None is a gap
    - _reader_plain_coverage(chapters) -> bool; whether the book has any
      Plain English, decided before units are split
    - _reader_source_checksum(chapters) -> str
    - _reader_structure(conn, book_id) -> list[dict]; the manifest's
      `structure` entries (parts and chapters, in reading order)
    """

    _READER_MODES = ('summary', 'original', 'plain', 'side_by_side')
    _READER_SEGMENT_UNITS = 80
    _READER_SEGMENT_BYTES = 24 * 1024
    _READER_OVERSIZED_BYTES = 64 * 1024

    @staticmethod
    def _reader_normalize_quote(text: str) -> str:
        """A short, presentation-independent public-domain recovery excerpt."""
        return re.sub(r'\s+', ' ', (text or '').strip().lower())[:180]

    @staticmethod
    def _reader_split_paragraphs(text: str, verse: bool = False) -> List[str]:
        """Match the current chapter renderer: every nonempty source line is
        a logical paragraph. Empty source is represented by no rows; callers
        create an explicit Plain-English gap where needed.

        Verse: a blank-line block is one passage and keeps its line breaks,
        so a passage pairs with one Plain English paragraph."""
        if verse:
            return [
                '\n'.join(line.rstrip() for line in block.splitlines() if line.strip())
                for block in re.split(r'\n\s*\n', text or '') if block.strip()
            ]
        return [p.strip() for p in (text or '').splitlines() if p.strip()]

    @staticmethod
    def _reader_word_count(text: str) -> int:
        return len(re.findall(r"\b[\w’'-]+\b", text or ''))

    @staticmethod
    def _reader_unit_id(chapter_id: int, chapter_ordinal: int) -> str:
        return f'{chapter_id}.{chapter_ordinal}'

    @staticmethod
    def _reader_parse_unit_id(value) -> Optional[tuple]:
        match = re.fullmatch(r'(\d+)\.(\d+)', str(value or ''))
        return (int(match[1]), int(match[2])) if match else None

    @staticmethod
    def _reader_segment_etag(version: Dict, mode: str, segment: int) -> str:
        return hashlib.sha256(f"{version['source_checksum']}:{mode}:{segment}".encode('utf-8')).hexdigest()

    def ensure_reader_content(self, book_id: int) -> Dict:
        """Return the book's reader version, recompiling its unit index when
        the source content changed. The reader routes call this per request,
        so edited chapters are picked up without an operational step."""
        conn = self.get_connection()
        try:
            book = self._reader_load_book(conn, book_id)
            if not book:
                raise ValueError('Book not found')
            chapters = self._reader_load_chapters(conn, book_id)
            if not chapters:
                raise ValueError('Book has no chapters')
            verse = book['verse']
            for chapter in chapters:
                chapter['verse'] = verse

            checksum = self._reader_source_checksum(chapters)
            current = conn.execute('SELECT * FROM reader_version WHERE book_id = ?', (book_id,)).fetchone()
            if current and current['source_checksum'] == checksum:
                return dict(current)
            return self._compile_reader_content(
                conn, book_id, chapters, checksum, verse, current['version'] if current else 0)
        finally:
            conn.close()

    def _compile_reader_content(
        self,
        conn: sqlite3.Connection,
        book_id: int,
        chapters: List[Dict],
        checksum: str,
        verse: bool,
        previous_version: int,
    ) -> Dict:
        """Replace the book's unit index in one transaction. Units hold
        coordinates and counts only; no text and no earlier versions."""
        plain_coverage = self._reader_plain_coverage(chapters)
        rows: Dict[str, List[Dict]] = {mode: [] for mode in self._READER_MODES}
        for chapter in chapters:
            units = self._reader_chapter_units(chapter, verse, plain_coverage)
            for mode in ('summary', 'original', 'plain'):
                for chapter_ordinal, text in enumerate(units[mode]):
                    rows[mode].append({
                        'chapter_id': chapter['id'], 'chapter_ordinal': chapter_ordinal,
                        'word_count': self._reader_word_count(text) if text is not None else 0,
                        'byte_count': len((text or '').encode('utf-8')), 'gap': int(text is None),
                    })
            if plain_coverage:
                originals, plains = units['original'], units['plain']
                for chapter_ordinal in range(max(len(originals), len(plains))):
                    original = originals[chapter_ordinal] if chapter_ordinal < len(originals) else None
                    plain = plains[chapter_ordinal] if chapter_ordinal < len(plains) else None
                    rows['side_by_side'].append({
                        'chapter_id': chapter['id'], 'chapter_ordinal': chapter_ordinal,
                        'word_count': self._reader_word_count(original if original is not None else plain),
                        'byte_count': len(' '.join(t or '' for t in (original, plain)).encode('utf-8')), 'gap': 0,
                    })

        values = []
        for mode, mode_rows in rows.items():
            # Segments: at most 80 units / 24KB; a unit over 64KB stands alone.
            segment, count, size, word_start = 0, 0, 0, 0
            for ordinal, row in enumerate(mode_rows):
                if count and (count >= self._READER_SEGMENT_UNITS
                              or size + row['byte_count'] > self._READER_SEGMENT_BYTES):
                    segment, count, size = segment + 1, 0, 0
                values.append((
                    book_id, mode, ordinal, row['chapter_id'], row['chapter_ordinal'], segment,
                    row['word_count'], word_start, row['byte_count'], row['gap'],
                ))
                count, size, word_start = count + 1, size + row['byte_count'], word_start + row['word_count']
                if row['byte_count'] > self._READER_OVERSIZED_BYTES:
                    segment, count, size = segment + 1, 0, 0

        version = previous_version + 1
        etag = hashlib.sha256(f'{book_id}:{version}:{checksum}'.encode('utf-8')).hexdigest()
        with conn:
            conn.execute('DELETE FROM reader_unit WHERE book_id = ?', (book_id,))
            conn.executemany('''
                INSERT INTO reader_unit
                    (book_id, mode, ordinal, chapter_id, chapter_ordinal, segment,
                     word_count, word_start, byte_count, gap)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', values)
            conn.execute('''
                INSERT INTO reader_version (book_id, version, source_checksum, manifest_etag, verse, plain_coverage)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    version = excluded.version, source_checksum = excluded.source_checksum,
                    manifest_etag = excluded.manifest_etag, verse = excluded.verse,
                    plain_coverage = excluded.plain_coverage
            ''', (book_id, version, checksum, etag, int(verse), int(plain_coverage)))
        return dict(conn.execute('SELECT * FROM reader_version WHERE book_id = ?', (book_id,)).fetchone())

    def get_reader_manifest(self, book_id: int) -> Dict:
        version = self.ensure_reader_content(book_id)
        book = self.get_book(book_id)
        if not book:
            raise ValueError('Book not found')
        conn = self.get_connection()
        try:
            stats = {row['mode']: dict(row) for row in conn.execute('''
                SELECT mode, COUNT(*) AS unit_count, SUM(word_count) AS total_word_count,
                       MAX(gap) AS any_gap, MIN(segment) AS first_segment, MAX(segment) AS last_segment
                FROM reader_unit WHERE book_id = ? GROUP BY mode
            ''', (book_id,))}
            modes = []
            for mode in self._READER_MODES:
                stat = stats.get(mode)
                if not stat:
                    availability = 'unavailable'
                elif mode == 'plain' and stat['any_gap']:
                    availability = 'partial'
                else:
                    availability = 'available'
                terminal = conn.execute('''
                    SELECT chapter_id, chapter_ordinal FROM reader_unit
                    WHERE book_id = ? AND mode = ? ORDER BY ordinal DESC LIMIT 1
                ''', (book_id, mode)).fetchone()
                modes.append({
                    'mode': mode, 'availability': availability,
                    'total_word_count': stat['total_word_count'] if stat else 0,
                    'unit_count': stat['unit_count'] if stat else 0,
                    'first_segment_id': f"{mode}.{stat['first_segment']}" if stat else None,
                    'last_segment_id': f"{mode}.{stat['last_segment']}" if stat else None,
                    'terminal_paragraph_id': self._reader_unit_id(*terminal) if terminal else None,
                })

            # Chapters per segment (in reading order), so the client can open
            # a chapter's segment directly instead of scanning segments.
            chapter_ids: Dict[tuple, List[int]] = {}
            for row in conn.execute('''
                SELECT mode, segment, chapter_id, MIN(ordinal) AS first_ordinal
                FROM reader_unit WHERE book_id = ?
                GROUP BY mode, segment, chapter_id ORDER BY mode, segment, first_ordinal
            ''', (book_id,)):
                chapter_ids.setdefault((row['mode'], row['segment']), []).append(row['chapter_id'])
            segments = []
            for row in conn.execute('''
                SELECT mode, segment, MIN(ordinal) AS first_unit_ordinal, MAX(ordinal) AS last_unit_ordinal,
                       MIN(word_start) AS first_word_offset, MAX(word_start + word_count) AS last_word_offset,
                       SUM(byte_count) AS byte_count, COUNT(*) AS unit_count
                FROM reader_unit WHERE book_id = ? GROUP BY mode, segment ORDER BY mode, segment
            ''', (book_id,)):
                segment = dict(row)
                key = (segment.pop('mode'), segment.pop('segment'))
                segments.append({
                    'id': f'{key[0]}.{key[1]}', 'mode': key[0], 'ordinal': key[1], **segment,
                    'oversized_unit': int(segment['unit_count'] == 1
                                          and segment['byte_count'] > self._READER_OVERSIZED_BYTES),
                    'etag': self._reader_segment_etag(version, key[0], key[1]),
                    'chapter_ids': chapter_ids.get(key, []),
                })

            return {
                'book': {
                    'id': book['id'], 'slug': book.get('slug'), 'title': book.get('title'),
                    'author': book.get('author'), 'cover_image_url': book.get('cover_image_url'),
                },
                'content_version': version['version'],
                'etag': version['manifest_etag'],
                'modes': modes,
                'structure': self._reader_structure(conn, book_id),
                'segments': segments,
            }
        finally:
            conn.close()

    def _reader_member(self, texts: List[Optional[str]], chapter_ordinal: int, unit_id: str, member_mode: str) -> Dict:
        text = texts[chapter_ordinal] if chapter_ordinal < len(texts) else None
        return {
            'member_mode': member_mode, 'available': int(text is not None),
            'id': unit_id if text is not None else None, 'content': text,
            'normalized_quote': self._reader_normalize_quote(text) if text is not None else None,
            'word_count': self._reader_word_count(text) if text is not None else None,
        }

    def get_reader_segment(self, book_id: int, segment_id: str, mode: str) -> Optional[Dict]:
        match = re.fullmatch(r'([a-z_]+)\.(\d+)', str(segment_id or ''))
        if mode not in self._READER_MODES or not match or match[1] != mode:
            return None
        segment = int(match[2])
        version = self.ensure_reader_content(book_id)
        conn = self.get_connection()
        try:
            rows = [dict(row) for row in conn.execute('''
                SELECT * FROM reader_unit WHERE book_id = ? AND mode = ? AND segment = ? ORDER BY ordinal
            ''', (book_id, mode, segment)).fetchall()]
            if not rows:
                return None
            last_segment = conn.execute(
                'SELECT MAX(segment) FROM reader_unit WHERE book_id = ? AND mode = ?', (book_id, mode)
            ).fetchone()[0]
            chapter_ids = list(dict.fromkeys(row['chapter_id'] for row in rows))
            chapters = {chapter['id']: chapter for chapter in self._reader_load_chapters(conn, book_id, chapter_ids)}
        finally:
            conn.close()

        split = {
            chapter_id: self._reader_chapter_units(chapters[chapter_id], bool(version['verse']),
                                                   bool(version['plain_coverage']))
            for chapter_id in chapter_ids
        }
        units = []
        for row in rows:
            chapter = chapters[row['chapter_id']]
            texts = split[row['chapter_id']]
            unit_id = self._reader_unit_id(row['chapter_id'], row['chapter_ordinal'])
            unit = {
                'id': unit_id, 'chapter_id': row['chapter_id'], 'ordinal': row['ordinal'],
                'chapter_ordinal': row['chapter_ordinal'], 'word_start': row['word_start'],
                'chapter_number': chapter['chapter_number'], 'chapter_title': chapter['chapter_title'],
            }
            if mode == 'side_by_side':
                unit['canonical_word_count'] = row['word_count']
                unit['members'] = {
                    member_mode: self._reader_member(texts[member_mode], row['chapter_ordinal'], unit_id, member_mode)
                    for member_mode in ('original', 'plain')
                }
            else:
                text = texts[mode][row['chapter_ordinal']]
                unit.update({
                    'content': text, 'availability': 'gap' if row['gap'] else 'available',
                    'normalized_quote': self._reader_normalize_quote(text) if text is not None else None,
                    'word_count': row['word_count'],
                    'fallback_paragraph_id': unit_id if row['gap'] else None,
                })
            units.append(unit)
        return {
            'id': segment_id, 'mode': mode, 'content_version': version['version'],
            'etag': self._reader_segment_etag(version, mode, segment),
            'previous_segment_id': f'{mode}.{segment - 1}' if segment > 0 else None,
            'next_segment_id': f'{mode}.{segment + 1}' if segment < last_segment else None,
            'units': units,
            'word_range': [rows[0]['word_start'], rows[-1]['word_start'] + rows[-1]['word_count']],
        }

    def resolve_reader_marker(self, book_id: int, marker: Dict) -> Optional[Dict]:
        """Validate and enrich a marker with authoritative ordering values."""
        if not marker or marker.get('mode') not in self._READER_MODES:
            return None
        version = self.ensure_reader_content(book_id)
        if marker.get('content_version') not in (None, version['version']):
            # Content changed; recovery is handled by the reader on
            # retrieval. New writes always target the current version.
            return None
        try:
            offset = max(0.0, min(1.0, float(marker.get('offset', 0))))
        except (TypeError, ValueError):
            return None
        coords = self._reader_parse_unit_id(marker.get('paragraph_id'))
        if not coords or marker.get('chapter_id') not in (None, coords[0]):
            return None
        conn = self.get_connection()
        try:
            row = conn.execute('''
                SELECT ordinal, word_start, word_count FROM reader_unit
                WHERE book_id = ? AND mode = ? AND chapter_id = ? AND chapter_ordinal = ?
            ''', (book_id, marker['mode'], *coords)).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return {
            'book_id': book_id, 'mode': marker['mode'], 'content_version': version['version'],
            'chapter_id': coords[0], 'paragraph_id': self._reader_unit_id(*coords), 'offset': offset,
            'quote': marker.get('quote') or '', 'ordinal': row['ordinal'],
            'word_position': row['word_start'] + int(row['word_count'] * offset),
        }

    def recover_reader_marker(self, book_id: int, marker: Dict) -> Optional[Dict]:
        """Recover a marker saved against an earlier content version.

        No earlier versions are kept: within the marker's chapter, the
        paragraph containing the marker's quote wins ('quote'); otherwise the
        same position, clamped to the chapter ('ordinal'). Read-only — the
        caller persists only after a real reader action."""
        if not marker or marker.get('mode') not in self._READER_MODES:
            return None
        version = self.ensure_reader_content(book_id)
        if marker.get('content_version') in (None, version['version']):
            resolved = self.resolve_reader_marker(book_id, marker)
            if resolved:
                resolved['recovery_level'] = 'same_id'
                return resolved
            # Same version number, unknown ID (e.g. saved before the storage
            # migration restarted version numbers): recover like a stale one.

        mode = marker['mode']
        coords = self._reader_parse_unit_id(marker.get('paragraph_id'))
        chapter_id = marker.get('chapter_id') or (coords[0] if coords else None)
        if chapter_id is None:
            return None
        conn = self.get_connection()
        try:
            chapters = self._reader_load_chapters(conn, book_id, [int(chapter_id)])
        finally:
            conn.close()
        if not chapters:
            return None
        units = self._reader_chapter_units(chapters[0], bool(version['verse']), bool(version['plain_coverage']))
        if mode == 'side_by_side':
            count = max(len(units['original']), len(units['plain']))
            texts = [
                next((t[i] for t in (units['original'], units['plain']) if i < len(t) and t[i] is not None), None)
                for i in range(count)
            ]
        else:
            texts = units[mode]
        if not texts:
            return None

        target, level = None, None
        probe = self._reader_normalize_quote(marker.get('quote') or '')[:60]
        if probe:
            target = next((i for i, text in enumerate(texts)
                           if text is not None and probe in self._reader_normalize_quote(text)), None)
            level = 'quote' if target is not None else None
        if target is None:
            old_ordinal = coords[1] if coords and coords[0] == int(chapter_id) else 0
            target, level = min(old_ordinal, len(texts) - 1), 'ordinal'
        resolved = self.resolve_reader_marker(book_id, {
            'mode': mode, 'content_version': version['version'], 'chapter_id': int(chapter_id),
            'paragraph_id': self._reader_unit_id(int(chapter_id), target),
            'offset': marker.get('offset', 0) if level == 'quote' else 0, 'quote': marker.get('quote'),
        })
        if resolved:
            resolved['recovery_level'] = level
        return resolved

    def map_reader_marker(self, book_id: int, marker: Dict, target_mode: str) -> Optional[Dict]:
        """Map a current marker into another reader mode.

        Original, Plain English and Side-by-Side pair by position within a
        chapter. Summary mappings are chapter-scoped because summaries are
        not sentence-aligned with source text."""
        if target_mode not in self._READER_MODES:
            return None
        source = self.resolve_reader_marker(book_id, marker)
        if not source:
            return None
        if source['mode'] == target_mode:
            return source
        chapter_id, chapter_ordinal = self._reader_parse_unit_id(source['paragraph_id'])
        conn = self.get_connection()
        try:
            if 'summary' in (source['mode'], target_mode):
                target = conn.execute('''
                    SELECT chapter_ordinal FROM reader_unit
                    WHERE book_id = ? AND mode = ? AND chapter_id = ? AND gap = 0
                    ORDER BY chapter_ordinal LIMIT 1
                ''', (book_id, target_mode, chapter_id)).fetchone()
            else:
                target = conn.execute('''
                    SELECT chapter_ordinal FROM reader_unit
                    WHERE book_id = ? AND mode = ? AND chapter_id = ? AND chapter_ordinal = ? AND gap = 0
                ''', (book_id, target_mode, chapter_id, chapter_ordinal)).fetchone()
        finally:
            conn.close()
        if not target:
            return None
        return self.resolve_reader_marker(book_id, {
            'mode': target_mode, 'content_version': source['content_version'],
            'chapter_id': chapter_id, 'paragraph_id': self._reader_unit_id(chapter_id, target['chapter_ordinal']),
            'offset': 0,
        })
