"""Distill content database: imported books and the shared reader index hooks.

A book is a validated folder (see book_format.py). Each chapter's blocks are
stored as JSON; the reader's only mode is 'summary', one unit per block.
"""
import hashlib
import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageOps

from distill import config
from distill.book_format import block_text, iter_chapters, list_images, load_book, normalize_toc_titles, validate_book, word_count
from shared.reader.index import ReaderIndexMixin, create_reader_tables

_IMAGE_MIMES = {'.jpg': 'image/jpeg', '.png': 'image/png'}
_COVER_RECIPE = b'cover-v1-320x480-avif60-speed6-webp80-jpeg82'


def _cover_variants(data: bytes) -> list:
    """Encode once during import/backfill, never during an HTTP request."""
    variants = []
    with Image.open(io.BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert('RGBA')
        image.thumbnail((320, 480), Image.Resampling.LANCZOS)
        # Covers share an opaque white backing across all fallback formats.
        background = Image.new('RGB', image.size, 'white')
        background.paste(image, mask=image.getchannel('A'))
        for fmt, mime, options in (
            ('avif', 'image/avif', {'quality': 60, 'speed': 6}),
            ('webp', 'image/webp', {'quality': 80}),
            ('jpg', 'image/jpeg', {'quality': 82, 'optimize': True})):
            output = io.BytesIO()
            background.save(output, 'JPEG' if fmt == 'jpg' else fmt.upper(), **options)
            variants.append((fmt, mime, output.getvalue()))
    return variants


class DistillDatabase(ReaderIndexMixin):

    def __init__(self, db_path: Path = config.DATABASE_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self.get_connection()
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    lang TEXT NOT NULL,
                    cover_image_id INTEGER,
                    sources TEXT,
                    imported_at TIMESTAMP,
                    content_checksum TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    part_title TEXT,
                    title TEXT NOT NULL,
                    blocks TEXT NOT NULL,
                    UNIQUE(book_id, ordinal)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    mime TEXT NOT NULL,
                    data BLOB NOT NULL,
                    UNIQUE(book_id, name)
                )
            ''')
            conn.execute('''CREATE TABLE IF NOT EXISTS cover_thumbnails (
                image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
                format TEXT NOT NULL,
                token TEXT NOT NULL,
                source_checksum TEXT NOT NULL,
                mime TEXT NOT NULL,
                data BLOB NOT NULL,
                PRIMARY KEY (image_id, format)
            )''')
            # Backward-compatible metadata migration; chapter IDs and progress stay intact.
            if 'categories' not in {row['name'] for row in conn.execute('PRAGMA table_info(books)')}:
                conn.execute("ALTER TABLE books ADD COLUMN categories TEXT NOT NULL DEFAULT '[]'")
            create_reader_tables(conn.cursor())
            # Persist index freshness across requests/workers. SQLite triggers
            # also catch content edits made by import tools or another process.
            conn.execute('''CREATE TABLE IF NOT EXISTS distill_reader_revision (
                book_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
                revision INTEGER NOT NULL DEFAULT 0,
                indexed_revision INTEGER
            )''')
            conn.execute('INSERT OR IGNORE INTO distill_reader_revision (book_id) SELECT id FROM books')
            conn.execute('''CREATE TRIGGER IF NOT EXISTS distill_book_revision_insert AFTER INSERT ON books
                BEGIN INSERT INTO distill_reader_revision (book_id) VALUES (NEW.id); END''')
            for event, reference in (('INSERT', 'NEW'), ('DELETE', 'OLD')):
                conn.execute(f'''CREATE TRIGGER IF NOT EXISTS distill_chapter_revision_{event.lower()}
                    AFTER {event} ON chapters BEGIN
                    UPDATE distill_reader_revision SET revision = revision + 1
                    WHERE book_id = {reference}.book_id; END''')
            conn.execute('''CREATE TRIGGER IF NOT EXISTS distill_chapter_revision_update
                AFTER UPDATE ON chapters BEGIN
                UPDATE distill_reader_revision SET revision = revision + 1
                WHERE book_id IN (OLD.book_id, NEW.book_id); END''')
        conn.close()

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_book(self, folder: Path) -> int:
        """Validate and import a book folder. Re-importing a slug keeps its
        book id and chapter ids (reading progress is keyed by them)."""
        folder = Path(folder)
        book = load_book(folder)
        errors = validate_book(book, folder)
        if errors:
            raise ValueError('Invalid book:\n' + '\n'.join(errors))

        chapters = iter_chapters(book)
        checksum = hashlib.sha256(json.dumps(
            [book['title'], book.get('author'), chapters], ensure_ascii=False, sort_keys=True,
        ).encode('utf-8')).hexdigest()
        images = [(p.name, _IMAGE_MIMES[p.suffix.lower()], p.read_bytes()) for p in list_images(folder)]
        cover = Path(book['cover']).name if book.get('cover') else None
        cover_data = next((data for name, _, data in images if name == cover), None)
        variants = _cover_variants(cover_data) if cover_data else []

        conn = self.get_connection()
        try:
            with conn:
                conn.execute('''
                    INSERT INTO books (slug, title, author, lang, sources, imported_at, content_checksum, categories)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(slug) DO UPDATE SET
                        title = excluded.title, author = excluded.author, lang = excluded.lang,
                        sources = excluded.sources, imported_at = excluded.imported_at,
                        content_checksum = excluded.content_checksum, categories = excluded.categories
                ''', (book['slug'], book['title'], book.get('author'), book['lang'],
                      json.dumps(book.get('sources', []), ensure_ascii=False),
                      datetime.now().isoformat(sep=' ', timespec='seconds'), checksum,
                      json.dumps([c.strip() for c in book.get('categories', [])], ensure_ascii=False)))
                book_id = conn.execute('SELECT id FROM books WHERE slug = ?', (book['slug'],)).fetchone()['id']

                for ordinal, (part_title, title, blocks) in enumerate(chapters):
                    conn.execute('''
                        INSERT INTO chapters (book_id, ordinal, part_title, title, blocks)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(book_id, ordinal) DO UPDATE SET
                            part_title = excluded.part_title, title = excluded.title, blocks = excluded.blocks
                    ''', (book_id, ordinal, part_title, title, json.dumps(blocks, ensure_ascii=False)))
                conn.execute('DELETE FROM chapters WHERE book_id = ? AND ordinal >= ?', (book_id, len(chapters)))

                conn.execute('DELETE FROM images WHERE book_id = ?', (book_id,))
                conn.executemany('INSERT INTO images (book_id, name, mime, data) VALUES (?, ?, ?, ?)',
                                 [(book_id, *image) for image in images])
                cover_row = conn.execute('SELECT id FROM images WHERE book_id = ? AND name = ?',
                                         (book_id, cover)).fetchone() if cover else None
                conn.execute('UPDATE books SET cover_image_id = ? WHERE id = ?',
                             (cover_row['id'] if cover_row else None, book_id))
                if cover_row and variants:
                    self._store_cover_variants(conn, cover_row['id'], cover_data, variants)
            return book_id
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @staticmethod
    def _store_cover_variants(conn, image_id, data, variants):
        token = hashlib.sha256(b''.join(v[2] for v in variants)).hexdigest()[:24]
        checksum = hashlib.sha256(_COVER_RECIPE + data).hexdigest()
        conn.executemany('''INSERT OR REPLACE INTO cover_thumbnails
            (image_id, format, token, source_checksum, mime, data) VALUES (?, ?, ?, ?, ?, ?)''',
            [(image_id, fmt, token, checksum, mime, encoded) for fmt, mime, encoded in variants])

    def generate_cover_thumbnails(self) -> int:
        """Idempotent backfill; originals and reader/progress data are untouched."""
        conn = self.get_connection()
        try:
            covers = conn.execute('''SELECT i.id, i.data FROM books b
                JOIN images i ON i.id = b.cover_image_id''').fetchall()
            generated = 0
            for cover in covers:
                checksum = hashlib.sha256(_COVER_RECIPE + cover['data']).hexdigest()
                existing = conn.execute('''SELECT format FROM cover_thumbnails
                    WHERE image_id = ? AND source_checksum = ?''', (cover['id'], checksum)).fetchall()
                if {r['format'] for r in existing} == {'avif', 'webp', 'jpg'}:
                    continue
                variants = _cover_variants(cover['data'])
                with conn:
                    # An import may replace the cover while encoding is running.
                    current = conn.execute('SELECT data FROM images WHERE id = ?', (cover['id'],)).fetchone()
                    if current and current['data'] == cover['data']:
                        self._store_cover_variants(conn, cover['id'], cover['data'], variants)
                        generated += 1
            return generated
        finally:
            conn.close()

    def get_cover_thumbnail(self, slug: str, token: str, fmt: str) -> Optional[Tuple[str, bytes]]:
        conn = self.get_connection()
        try:
            row = conn.execute('''SELECT t.mime, t.data FROM cover_thumbnails t
                JOIN books b ON b.cover_image_id = t.image_id
                WHERE b.slug = ? AND t.token = ? AND t.format = ?''', (slug, token, fmt)).fetchone()
            return (row['mime'], bytes(row['data'])) if row else None
        finally:
            conn.close()

    def append_source_chapters(self, dry_run: bool = True) -> List[int]:
        """Append existing source blocks without renumbering content chapters.

        Retain books.sources as the import metadata, but render it only through
        the final chapter. Re-running this migration does not duplicate it.
        """
        changed = []
        conn = self.get_connection()
        try:
            with conn:
                for book in conn.execute('SELECT id, sources FROM books').fetchall():
                    blocks = json.loads(book['sources'] or '[]')
                    if not blocks:
                        continue
                    last = conn.execute(
                        'SELECT ordinal, part_title, title, blocks FROM chapters '
                        'WHERE book_id = ? ORDER BY ordinal DESC LIMIT 1', (book['id'],)).fetchone()
                    is_source = last and last['part_title'] is None and last['title'] == 'Source'
                    if is_source and json.loads(last['blocks']) == blocks:
                        continue
                    changed.append(book['id'])
                    if not dry_run:
                        if is_source:
                            conn.execute('UPDATE chapters SET blocks = ? WHERE book_id = ? AND ordinal = ?',
                                         (json.dumps(blocks, ensure_ascii=False), book['id'], last['ordinal']))
                        else:
                            conn.execute(
                                'INSERT INTO chapters (book_id, ordinal, part_title, title, blocks) '
                                'VALUES (?, ?, NULL, ?, ?)',
                                (book['id'], last['ordinal'] + 1 if last else 0, 'Source',
                                 json.dumps(blocks, ensure_ascii=False)))
            return changed
        finally:
            conn.close()

    def repair_toc(self, dry_run: bool = True) -> List[Dict]:
        """Repair imported titles in place, preserving IDs and reader coordinates.

        Reader checksums automatically refresh on the next request. No content
        blocks, images, book order, or user database rows are touched.
        """
        changes = []
        conn = self.get_connection()
        try:
            with conn:
                for book in conn.execute('SELECT id, slug, lang FROM books').fetchall():
                    before = [dict(r) for r in conn.execute(
                        'SELECT id, part_title, title FROM chapters WHERE book_id = ? ORDER BY ordinal',
                        (book['id'],))]
                    after = normalize_toc_titles(before, book['lang'], book['slug'])
                    for old, new in zip(before, after):
                        if old['title'] != new['title']:
                            changes.append({'slug': book['slug'], 'id': old['id'],
                                            'before': old['title'], 'after': new['title']})
                            if not dry_run:
                                conn.execute('UPDATE chapters SET title = ? WHERE id = ?',
                                             (new['title'], old['id']))
            return changes
        finally:
            conn.close()

    @staticmethod
    def _book_dict(row: sqlite3.Row) -> Dict:
        return {
            'id': row['id'], 'slug': row['slug'], 'title': row['title'], 'author': row['author'],
            'categories': json.loads(row['categories']),
            'lang': row['lang'], 'sources': json.loads(row['sources'] or '[]'),
            'cover_image_id': row['cover_image_id'], 'cover_image': row['cover_image'],
            'cover_thumbnail_token': row['cover_thumbnail_token'],
            'imported_at': row['imported_at'],
        }

    def _fetch_books(self, where: str, params: tuple) -> List[Dict]:
        conn = self.get_connection()
        try:
            return [self._book_dict(r) for r in conn.execute(
                f'''SELECT books.*, images.name AS cover_image,
                    (SELECT token FROM cover_thumbnails WHERE image_id = books.cover_image_id
                     GROUP BY token HAVING COUNT(*) = 3) AS cover_thumbnail_token FROM books '''
                f'LEFT JOIN images ON images.id = books.cover_image_id '
                f'{where} ORDER BY books.title COLLATE NOCASE, books.id', params)]
        finally:
            conn.close()

    def get_book(self, book_id: int) -> Optional[Dict]:
        rows = self._fetch_books('WHERE books.id = ?', (book_id,))
        return rows[0] if rows else None

    def get_book_by_slug(self, slug: str) -> Optional[Dict]:
        rows = self._fetch_books('WHERE books.slug = ?', (slug,))
        return rows[0] if rows else None

    def list_books(self) -> List[Dict]:
        return self._fetch_books('', ())

    def get_chapters(self, book_id: int) -> List[Dict]:
        conn = self.get_connection()
        try:
            return [{'id': r['id'], 'ordinal': r['ordinal'], 'part_title': r['part_title'],
                     'title': r['title'], 'blocks': json.loads(r['blocks'])}
                    for r in conn.execute(
                        'SELECT * FROM chapters WHERE book_id = ? ORDER BY ordinal', (book_id,))]
        finally:
            conn.close()

    def count_chapters(self, book_id: int) -> int:
        """Chapters excluding the Overview (ordinal 0), without loading any blocks."""
        conn = self.get_connection()
        try:
            return conn.execute('SELECT COUNT(*) FROM chapters WHERE book_id = ? AND ordinal > 0',
                                (book_id,)).fetchone()[0]
        finally:
            conn.close()

    def get_chapter_outline(self, book_id: int) -> List[Dict]:
        """id, ordinal, part_title and title of every chapter, without loading blocks."""
        conn = self.get_connection()
        try:
            return [dict(r) for r in conn.execute(
                'SELECT id, ordinal, part_title, title FROM chapters WHERE book_id = ? ORDER BY ordinal',
                (book_id,))]
        finally:
            conn.close()

    def get_chapter(self, book_id: int, ordinal: int) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            r = conn.execute('SELECT * FROM chapters WHERE book_id = ? AND ordinal = ?',
                             (book_id, ordinal)).fetchone()
            return {'id': r['id'], 'ordinal': r['ordinal'], 'part_title': r['part_title'],
                    'title': r['title'], 'blocks': json.loads(r['blocks'])} if r else None
        finally:
            conn.close()

    def get_image(self, book_id: int, name: str) -> Optional[Tuple[str, bytes]]:
        conn = self.get_connection()
        try:
            row = conn.execute('SELECT mime, data FROM images WHERE book_id = ? AND name = ?',
                               (book_id, name)).fetchone()
            return (row['mime'], bytes(row['data'])) if row else None
        finally:
            conn.close()

    # Library hooks (shared.progress.routes content_db surface)

    def library_word_totals(self, book_ids: List[int]) -> Dict[int, Dict[str, int]]:
        """Progress needs word totals, not full manifests or chapter text."""
        if not book_ids:
            return {}
        conn = self.get_connection()
        try:
            dirty = [r['book_id'] for r in conn.execute(
                f'''SELECT r.book_id FROM distill_reader_revision r
                    LEFT JOIN reader_version v ON v.book_id = r.book_id
                    WHERE r.book_id IN ({','.join('?' * len(book_ids))})
                    AND (r.indexed_revision IS NULL OR r.indexed_revision != r.revision OR v.book_id IS NULL)''',
                book_ids)]
            for book_id in dirty:
                self.ensure_reader_content(book_id)
            totals = {}
            for r in conn.execute(
                    f'''SELECT book_id, mode, SUM(word_count) AS words FROM reader_unit
                        WHERE book_id IN ({','.join('?' * len(book_ids))}) GROUP BY book_id, mode''', book_ids):
                totals.setdefault(r['book_id'], {})[r['mode']] = r['words']
            return totals
        finally:
            conn.close()

    def chapter_counts(self, book_ids: List[int]) -> Dict[int, int]:
        if not book_ids:
            return {}
        conn = self.get_connection()
        try:
            return {r['book_id']: r['n'] for r in conn.execute(
                f'''SELECT book_id, COUNT(*) AS n FROM chapters WHERE ordinal > 0
                    AND book_id IN ({','.join('?' * len(book_ids))}) GROUP BY book_id''', book_ids)}
        finally:
            conn.close()

    def library_books(self, book_ids: List[int]) -> Dict[int, Dict]:
        """Card fields keyed by id. cover_image_url is None until the web app builds image URLs."""
        conn = self.get_connection()
        try:
            return {
                row['id']: {**dict(row), 'cover_image_url': None}
                for row in conn.execute(
                    f"SELECT id, slug, title, author FROM books WHERE id IN ({','.join('?' * len(book_ids))})",
                    list(book_ids))
            }
        finally:
            conn.close()

    def chapter_titles(self, chapter_ids: List[int]) -> Dict[int, Dict]:
        conn = self.get_connection()
        try:
            return {
                row['id']: dict(row)
                for row in conn.execute(
                    f"SELECT id, ordinal AS chapter_number, title AS chapter_title FROM chapters "
                    f"WHERE id IN ({','.join('?' * len(chapter_ids))})", list(chapter_ids))
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Continuous-reader hooks (shared.reader.ReaderIndexMixin)
    # ------------------------------------------------------------------

    def ensure_reader_content(self, book_id: int) -> Dict:
        conn = self.get_connection()
        try:
            row = conn.execute('''SELECT v.*, r.revision, r.indexed_revision
                FROM distill_reader_revision r LEFT JOIN reader_version v ON v.book_id = r.book_id
                WHERE r.book_id = ?''', (book_id,)).fetchone()
            if row and row['version'] is not None and row['revision'] == row['indexed_revision']:
                return {k: row[k] for k in row.keys() if k not in ('revision', 'indexed_revision')}
            revision = row['revision'] if row else None
            version = super().ensure_reader_content(book_id)
            if revision is not None:
                # A concurrent edit must not be marked indexed by this request.
                with conn:
                    conn.execute('''UPDATE distill_reader_revision SET indexed_revision = ?
                        WHERE book_id = ? AND revision = ?''', (revision, book_id, revision))
            return version
        finally:
            conn.close()

    @staticmethod
    def _unit_visible_text(text: str) -> str:
        """Visible text of a unit: a block's text, or the raw string if it is not a block."""
        try:
            block = json.loads(text)
        except (TypeError, ValueError):
            return text or ''
        return block_text(block) if isinstance(block, dict) and 'type' in block else (text or '')

    @staticmethod
    def _reader_word_count(text: str) -> int:
        return word_count(DistillDatabase._unit_visible_text(text))

    @staticmethod
    def _reader_normalize_quote(text: str) -> str:
        return ReaderIndexMixin._reader_normalize_quote(DistillDatabase._unit_visible_text(text))

    @staticmethod
    def _reader_load_book(conn: sqlite3.Connection, book_id: int) -> Optional[Dict]:
        row = conn.execute('SELECT id FROM books WHERE id = ?', (book_id,)).fetchone()
        return {'id': row['id'], 'verse': False} if row else None

    @staticmethod
    def _reader_load_chapters(conn: sqlite3.Connection, book_id: int, chapter_ids: Optional[List[int]] = None) -> List[Dict]:
        query = 'SELECT id, ordinal, part_title, title, blocks FROM chapters WHERE book_id = ?'
        params: List = [book_id]
        if chapter_ids is not None:
            query += f" AND id IN ({','.join('?' * len(chapter_ids))})"
            params += list(chapter_ids)
        return [{'id': r['id'], 'chapter_number': r['ordinal'], 'chapter_title': r['title'],
                 'part_title': r['part_title'], 'blocks': json.loads(r['blocks'])}
                for r in conn.execute(query + ' ORDER BY ordinal', params)]

    @staticmethod
    def _reader_plain_coverage(chapters: List[Dict]) -> bool:
        return False

    @staticmethod
    def _reader_chapter_units(chapter: Dict, verse: bool, plain_coverage: bool) -> Dict[str, List[Optional[str]]]:
        return {
            'summary': [json.dumps(b, ensure_ascii=False, sort_keys=True) for b in chapter['blocks']],
            'original': [], 'plain': [],
        }

    def _reader_source_checksum(self, chapters: List[Dict]) -> str:
        source = [[c['id'], c['chapter_number'], c['chapter_title'], c.get('part_title'), c['blocks']]
                  for c in chapters]
        return hashlib.sha256(
            json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        ).hexdigest()

    @staticmethod
    def _reader_structure(conn: sqlite3.Connection, book_id: int) -> List[Dict]:
        structure: List[Dict] = []
        part_index, current_part = 0, None
        for row in conn.execute(
                'SELECT id, ordinal, part_title, title FROM chapters WHERE book_id = ? ORDER BY ordinal', (book_id,)):
            if row['part_title'] != current_part:
                current_part = row['part_title']
                if current_part:
                    part_index += 1
                    structure.append({
                        'kind': 'part', 'section_id': part_index, 'chapter_id': None,
                        'ordinal': len(structure), 'title': current_part,
                        'chapter_number': None, 'illustration_url': None,
                    })
            structure.append({
                'kind': 'chapter', 'section_id': None, 'chapter_id': row['id'], 'ordinal': len(structure),
                'title': row['title'], 'chapter_number': row['ordinal'], 'illustration_url': None,
            })
        return structure
