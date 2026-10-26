"""Distill content database: imported books and the shared reader index hooks.

A book is a validated folder (see book_format.py). Each chapter's blocks are
stored as JSON; the reader's only mode is 'summary', one unit per block.
"""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from distill import config
from distill.book_format import block_text, iter_chapters, list_images, load_book, validate_book, word_count
from shared.reader.index import ReaderIndexMixin, create_reader_tables

_IMAGE_MIMES = {'.jpg': 'image/jpeg', '.png': 'image/png'}


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
            create_reader_tables(conn.cursor())
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

        conn = self.get_connection()
        try:
            with conn:
                conn.execute('''
                    INSERT INTO books (slug, title, author, lang, sources, imported_at, content_checksum)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(slug) DO UPDATE SET
                        title = excluded.title, author = excluded.author, lang = excluded.lang,
                        sources = excluded.sources, imported_at = excluded.imported_at,
                        content_checksum = excluded.content_checksum
                ''', (book['slug'], book['title'], book.get('author'), book['lang'],
                      json.dumps(book.get('sources', []), ensure_ascii=False),
                      datetime.now().isoformat(sep=' ', timespec='seconds'), checksum))
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
                cover = Path(book['cover']).name if book.get('cover') else None
                cover_row = conn.execute('SELECT id FROM images WHERE book_id = ? AND name = ?',
                                         (book_id, cover)).fetchone() if cover else None
                conn.execute('UPDATE books SET cover_image_id = ? WHERE id = ?',
                             (cover_row['id'] if cover_row else None, book_id))
            return book_id
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @staticmethod
    def _book_dict(row: sqlite3.Row) -> Dict:
        return {
            'id': row['id'], 'slug': row['slug'], 'title': row['title'], 'author': row['author'],
            'lang': row['lang'], 'sources': json.loads(row['sources'] or '[]'),
            'cover_image_id': row['cover_image_id'], 'cover_image': row['cover_image'],
            'imported_at': row['imported_at'],
        }

    def _fetch_books(self, where: str, params: tuple) -> List[Dict]:
        conn = self.get_connection()
        try:
            return [self._book_dict(r) for r in conn.execute(
                f'SELECT books.*, images.name AS cover_image FROM books '
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

    def get_image(self, book_id: int, name: str) -> Optional[Tuple[str, bytes]]:
        conn = self.get_connection()
        try:
            row = conn.execute('SELECT mime, data FROM images WHERE book_id = ? AND name = ?',
                               (book_id, name)).fetchone()
            return (row['mime'], bytes(row['data'])) if row else None
        finally:
            conn.close()

    # Library hooks (shared.progress.routes content_db surface)

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
