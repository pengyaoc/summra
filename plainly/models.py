import sqlite3
import json
import wave
import re
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from plainly import config
from plainly.study_cues import add_book_cues, add_chapter_cues
from shared.reader.index import ReaderIndexMixin, create_reader_tables

# Private column for chapter-list metadata, turned into reading_minutes /
# reading_time by add_chapter_cues(). Word count is approximated in SQL
# (whitespace separators + 1) so the chapter list never loads full chapter
# text; chapters.word_count can't be used because it counts the *summary*.
CHAPTER_CUE_COLUMNS = '''
    CASE WHEN chapter_text IS NULL OR TRIM(chapter_text) = '' THEN NULL
         ELSE LENGTH(chapter_text)
              - LENGTH(REPLACE(REPLACE(REPLACE(chapter_text, ' ', ''), CHAR(10), ''), CHAR(9), '')) + 1
    END AS _text_words'''


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug.

    Matches the frontend slugify logic for consistency.

    Args:
        text: Text to convert to slug

    Returns:
        URL-friendly slug string
    """
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


class Database(ReaderIndexMixin):
    """Database handler for Plainly"""

    def __init__(self, db_path: Path = config.DATABASE_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Books table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                filename TEXT UNIQUE NOT NULL,
                word_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cover_image_url TEXT,
                gutenberg_id INTEGER,
                cover_source TEXT DEFAULT 'unknown',
                slug TEXT UNIQUE,
                author_id INTEGER,
                about_text TEXT,
                relevance_now TEXT,
                is_poetry INTEGER DEFAULT 0,
                character_guide_url TEXT,
                timeline_url TEXT,
                themes_url TEXT,
                cefr_level TEXT
            )
        ''')

        # Summaries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                summary_type TEXT NOT NULL,
                content TEXT NOT NULL,
                word_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                UNIQUE(book_id, summary_type)
            )
        ''')

        # Chapters table (for comprehensive summaries)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                chapter_number INTEGER NOT NULL,
                chapter_title TEXT,
                chapter_text TEXT,
                summary TEXT NOT NULL,
                word_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                section_id INTEGER REFERENCES book_sections(id),
                illustration_url TEXT,
                modern_english_text TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                UNIQUE(book_id, chapter_number)
            )
        ''')

        # Book sections table (for two-level structure: Part/Book/Act → Chapters)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS book_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                section_type TEXT NOT NULL,
                section_number INTEGER NOT NULL,
                section_title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                UNIQUE(book_id, section_number)
            )
        ''')

        # Add section_id column to chapters table if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE chapters ADD COLUMN section_id INTEGER REFERENCES book_sections(id)")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Audio files table (for TTS)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audio_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_id INTEGER,
                chapter_id INTEGER,
                audio_path TEXT NOT NULL,
                duration REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (summary_id) REFERENCES summaries(id) ON DELETE CASCADE,
                FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
            )
        ''')

        # Authors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                country TEXT,
                bio TEXT,
                short_bio TEXT,
                long_bio TEXT,
                other_books TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Book categories junction table (many-to-many relationship)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS book_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
                UNIQUE(book_id, category_id)
            )
        ''')

        # Where a removed category's page now lives (apply_book_metadata.py
        # records it), so old /categories/<id> links keep working.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS category_redirects (
                old_id INTEGER PRIMARY KEY,
                new_id INTEGER  -- NULL: send to the Categories page
            )
        ''')

        # Blog posts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                excerpt TEXT,
                author TEXT DEFAULT 'Plainly Team',
                published_date DATE,
                updated_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Continuous-reader index. Book text lives only in `chapters`: a
        # reader unit is a paragraph's coordinates (chapter, ordinal) plus the
        # counts the manifest needs, and segment text is re-split from
        # `chapters` on read with the same function that compiled the units.
        # One version row per book; a recompile replaces its units.
        create_reader_tables(cursor)
        # Migrating from the old per-version tables: continue each book's
        # version numbering so markers saved before the migration are seen as
        # stale (and recovered by quote) rather than as current.
        if cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reader_content_version'").fetchone():
            cursor.execute('''
                INSERT OR IGNORE INTO reader_version (book_id, version, source_checksum, manifest_etag)
                SELECT book_id, MAX(version), '', '' FROM reader_content_version GROUP BY book_id
            ''')
        for old_table in ('reader_paragraph_mapping', 'reader_alignment_member', 'reader_alignment_row',
                          'reader_paragraph', 'reader_segment', 'reader_structure_entry',
                          'reader_mode_manifest', 'reader_content_version'):
            cursor.execute(f'DROP TABLE IF EXISTS {old_table}')

        # Column migrations for existing databases — every table above is
        # CREATE TABLE IF NOT EXISTS, so a fresh database already has every
        # column and each ALTER TABLE below is a silent no-op (caught as
        # sqlite3.OperationalError: duplicate column name). Kept as one
        # data-driven list instead of 18 copy-pasted try/except blocks.
        for table, column_def in self._COLUMN_MIGRATIONS:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
                conn.commit()
            except sqlite3.OperationalError:
                # Column already exists
                pass

        # books.full_text duplicated the chapters' text (only ingestion used
        # it, before splitting); the book lives in `chapters` alone.
        if 'full_text' in {row[1] for row in cursor.execute('PRAGMA table_info(books)')}:
            cursor.execute('ALTER TABLE books DROP COLUMN full_text')
            conn.commit()

        # books.slug needs a UNIQUE index rather than a UNIQUE column
        # constraint, since SQLite's ALTER TABLE ADD COLUMN doesn't support
        # UNIQUE — add the column (above) then the index separately.
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_books_slug ON books(slug)")
            conn.commit()
        except sqlite3.OperationalError:
            # Index already exists
            pass

        # Covering index for book listings (catalog, Discover, top 10, level
        # counts). Added when each books row stored the whole book
        # (full_text, dropped 2026-10-16) and reading listed columns walked the
        # text's overflow pages; still a cheaper read. With every listed column in the index,
        # SQLite never touches the rows. Rename it when its columns change so
        # existing databases rebuild it (tests/test_book_listing_index.py).
        cursor.execute("DROP INDEX IF EXISTS idx_books_listing_v1")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {self._LISTING_INDEX} ON books({', '.join(self._LISTING_COLUMNS)})")
        conn.commit()

        conn.commit()
        conn.close()

    # (table, column_definition) pairs applied by init_db() on every
    # instantiation. Order doesn't matter for correctness — ALTER TABLE ADD
    # COLUMN only requires the target table to already exist (all of them do,
    # created above), not any table a REFERENCES clause points at — but is
    # kept close to the original commit order for readability.
    _LISTING_INDEX = 'idx_books_listing_v2'
    _LISTING_COLUMNS = ('title', 'id', 'author', 'filename', 'word_count', 'gutenberg_id',
                        'cover_image_url', 'created_at', 'slug', 'cefr_level',
                        'audience', 'atos_level', 'interest_level', 'school_lists')

    _COLUMN_MIGRATIONS = [
        ("chapters", "chapter_text TEXT"),
        ("books", "cover_image_url TEXT"),
        ("books", "gutenberg_id INTEGER"),
        ("books", "cover_source TEXT DEFAULT 'unknown'"),
        ("books", "slug TEXT"),
        ("books", "author_id INTEGER REFERENCES authors(id)"),
        ("chapters", "section_id INTEGER REFERENCES book_sections(id)"),
        ("chapters", "illustration_url TEXT"),
        ("books", "about_text TEXT"),
        ("books", "relevance_now TEXT"),
        ("chapters", "modern_english_text TEXT"),
        ("books", "is_poetry INTEGER DEFAULT 0"),
        ("authors", "short_bio TEXT"),
        ("authors", "long_bio TEXT"),
        ("books", "character_guide_url TEXT"),
        ("books", "timeline_url TEXT"),
        ("books", "themes_url TEXT"),
        ("blog_posts", "header_image_url TEXT"),
        # Reviewed book metadata (scripts/content/apply_book_metadata.py)
        ("books", "audience TEXT"),
        ("books", "atos_level REAL"),
        ("books", "interest_level TEXT"),
        ("books", "school_lists TEXT"),
    ]

    def add_book(self, title: str, author: str, filename: str, full_text: str,
                 gutenberg_id: int = None, cover_image_url: str = None, author_id: int = None, is_poetry: bool = False) -> int:
        """Add a new book to the database

        Args:
            title: Book title
            author: Author name (stored for backward compatibility)
            filename: Original filename
            full_text: Full book text (only counted; the text is stored per chapter)
            gutenberg_id: Project Gutenberg ID (optional)
            cover_image_url: Path to cover image (optional)
            author_id: Foreign key to authors table (optional, will auto-lookup if not provided)
            is_poetry: Whether this book is poetry (preserves line breaks) (optional)

        Returns:
            book_id: The ID of the newly created book
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        word_count = len(full_text.split())

        # Auto-generate slug from title
        slug = slugify(title)

        # Auto-lookup author_id if not provided
        if author_id is None and author:
            author_record = self.get_author_by_name(author)
            if author_record:
                author_id = author_record['id']

        cursor.execute('''
            INSERT INTO books (title, author, filename, word_count, gutenberg_id, cover_image_url, author_id, slug, is_poetry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, author, filename, word_count, gutenberg_id, cover_image_url, author_id, slug, 1 if is_poetry else 0))

        book_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return book_id

    def update_book_poetry_flag(self, book_id: int, is_poetry: bool):
        """Update book's is_poetry flag"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE books
            SET is_poetry = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (1 if is_poetry else 0, book_id))

        conn.commit()
        conn.close()

    def update_book_cover(self, book_id: int, gutenberg_id: int, cover_image_url: str, cover_source: str = None):
        """Update book cover image URL, Gutenberg ID, and cover source"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if cover_source:
            cursor.execute('''
                UPDATE books
                SET gutenberg_id = ?, cover_image_url = ?, cover_source = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (gutenberg_id, cover_image_url, cover_source, book_id))
        else:
            cursor.execute('''
                UPDATE books
                SET gutenberg_id = ?, cover_image_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (gutenberg_id, cover_image_url, book_id))

        conn.commit()
        conn.close()

    # WHERE-clause fragments for _get_book_with_author_by — an allowlist, not
    # a caller-supplied column name, so no SQL-injection surface even though
    # the query string is built with an f-string.
    _BOOK_LOOKUP_WHERE = {
        'id': 'b.id = ?',
        'slug': 'b.slug = ?',
    }

    def _get_book_with_author_by(self, lookup: str, value) -> Optional[Dict]:
        """Shared query for get_book/get_book_by_slug — identical author-join
        SELECT, differing only in which books column is matched."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(f'''
            SELECT b.*, a.country as author_country, a.other_books as author_other_books, a.short_bio as author_bio
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.id
            WHERE {self._BOOK_LOOKUP_WHERE[lookup]}
        ''', (value,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._book_cues(row)
        return None

    def get_book(self, book_id: int) -> Optional[Dict]:
        """Get book by ID with author metadata"""
        return self._get_book_with_author_by('id', book_id)

    def get_book_by_filename(self, filename: str) -> Optional[Dict]:
        """Get book by filename"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM books WHERE filename = ?', (filename,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_book_by_slug(self, slug: str) -> Optional[Dict]:
        """Get book by slug (SEO-friendly URL identifier) with author metadata"""
        return self._get_book_with_author_by('slug', slug)

    def update_book_slug(self, book_id: int, slug: str):
        """Update book's slug for SEO-friendly URLs"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE books
            SET slug = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (slug, book_id))

        conn.commit()
        conn.close()

    def get_books_by_gutenberg_ids(self, gutenberg_ids: List[int]) -> List[Dict]:
        """Get books matching the given Gutenberg IDs (unordered, no categories)"""
        if not gutenberg_ids:
            return []
        conn = self.get_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(gutenberg_ids))
        cursor.execute(
            f'SELECT id, title, author, gutenberg_id, cover_image_url, slug, word_count, cefr_level, atos_level, interest_level, school_lists FROM books '
            f'WHERE gutenberg_id IN ({placeholders})',
            list(gutenberg_ids),
        )
        books = [self._book_cues(row) for row in cursor.fetchall()]
        conn.close()
        return books

    def get_all_books(self) -> List[Dict]:
        """Get all books with their categories"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, created_at, slug, cefr_level, atos_level, interest_level, school_lists FROM books ORDER BY title')
        rows = cursor.fetchall()

        self.plain_english_book_ids(conn)  # warm the cache on this connection
        books = [self._book_cues(row) for row in rows]

        # Add categories to each book — one query for all books (same rows and
        # order as get_book_categories), not one query + connection per book.
        cursor.execute('''
            SELECT bc.book_id AS _book_id, c.* FROM categories c
            INNER JOIN book_categories bc ON c.id = bc.category_id
            ORDER BY c.name
        ''')
        categories_by_book = {}
        for row in cursor.fetchall():
            category = dict(row)
            categories_by_book.setdefault(category.pop('_book_id'), []).append(category)
        for book in books:
            book['categories'] = categories_by_book.get(book['id'], [])

        conn.close()
        return books

    def add_summary(self, book_id: int, summary_type: str, content: str) -> int:
        """Add or update a summary"""
        conn = self.get_connection()
        cursor = conn.cursor()

        word_count = len(content.split())

        cursor.execute('''
            INSERT INTO summaries (book_id, summary_type, content, word_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(book_id, summary_type) DO UPDATE SET
                content = excluded.content,
                word_count = excluded.word_count
        ''', (book_id, summary_type, content, word_count))

        summary_id = cursor.execute(
            'SELECT id FROM summaries WHERE book_id = ? AND summary_type = ?',
            (book_id, summary_type),
        ).fetchone()['id']
        conn.commit()
        conn.close()

        return summary_id

    def get_summary(self, book_id: int, summary_type: str) -> Optional[Dict]:
        """Get summary by book ID and type"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM summaries
            WHERE book_id = ? AND summary_type = ?
        ''', (book_id, summary_type))

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def add_chapter(self, book_id: int, chapter_number: int,
                    chapter_title: str, summary: str, chapter_text: str = None,
                    section_id: int = None, illustration_url: str = None,
                    modern_english_text: str = None) -> int:
        """Add or update a chapter summary

        If chapter already exists and a parameter is None, preserves the existing value.
        This allows updating summaries without accidentally deleting chapter_text.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        word_count = len(summary.split())

        # Check if chapter already exists
        cursor.execute('''
            SELECT chapter_text, section_id, illustration_url, modern_english_text
            FROM chapters
            WHERE book_id = ? AND chapter_number = ?
        ''', (book_id, chapter_number))

        existing = cursor.fetchone()

        # Preserve existing values if new values are None
        if existing:
            if chapter_text is None:
                chapter_text = existing['chapter_text']
            if section_id is None:
                section_id = existing['section_id']
            if illustration_url is None:
                illustration_url = existing['illustration_url']
            if modern_english_text is None:
                modern_english_text = existing['modern_english_text']

        cursor.execute('''
            INSERT INTO chapters
            (book_id, chapter_number, chapter_title, chapter_text, summary, word_count, section_id, illustration_url, modern_english_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(book_id, chapter_number) DO UPDATE SET
                chapter_title = excluded.chapter_title,
                chapter_text = excluded.chapter_text,
                summary = excluded.summary,
                word_count = excluded.word_count,
                section_id = excluded.section_id,
                illustration_url = excluded.illustration_url,
                modern_english_text = excluded.modern_english_text
        ''', (book_id, chapter_number, chapter_title, chapter_text, summary, word_count, section_id, illustration_url, modern_english_text))

        chapter_id = cursor.execute(
            'SELECT id FROM chapters WHERE book_id = ? AND chapter_number = ?',
            (book_id, chapter_number),
        ).fetchone()['id']
        conn.commit()
        conn.close()

        return chapter_id

    def get_chapters(self, book_id: int) -> List[Dict]:
        """Get all chapters for a book"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM chapters
            WHERE book_id = ?
            ORDER BY chapter_number
        ''', (book_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_chapters_metadata(self, book_id: int) -> List[Dict]:
        """Get chapter metadata only (no summary or full text) for efficient loading"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(f'''
            SELECT id, book_id, chapter_number, chapter_title, word_count, section_id, illustration_url,
                   {CHAPTER_CUE_COLUMNS}
            FROM chapters
            WHERE book_id = ?
            ORDER BY chapter_number
        ''', (book_id,))

        rows = cursor.fetchall()
        conn.close()

        return [add_chapter_cues(dict(row)) for row in rows]

    def get_chapter_outline(self, book_id: int) -> List[Dict]:
        """Chapter ids, numbers and titles with text lengths in characters (no
        text), for the Kindle reader's contents and whole-book progress."""
        conn = self.get_connection()
        rows = conn.execute('''
            SELECT id, chapter_number, chapter_title,
                   LENGTH(COALESCE(chapter_text, '')) AS text_chars,
                   LENGTH(TRIM(COALESCE(modern_english_text, ''), char(32) || char(9) || char(10) || char(13))) AS plain_chars
            FROM chapters WHERE book_id = ? ORDER BY chapter_number
        ''', (book_id,)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def count_chapters(self, book_id: int) -> int:
        """Number of chapters in a book (for the book page's meta row)."""
        conn = self.get_connection()
        count = conn.execute('SELECT COUNT(*) FROM chapters WHERE book_id = ?', (book_id,)).fetchone()[0]
        conn.close()
        return count

    # Which books have Plain English, for every listing's "Original only"
    # tag and Discover's Plain English filter. One query stops at each book's
    # first rewritten chapter; it only changes when rewrites are generated,
    # so each process keeps it for a few minutes.
    _PLAIN_ENGLISH_TTL = 300

    def plain_english_book_ids(self, conn=None) -> set:
        """Ids of books with Plain English. Pass `conn` to reuse an open connection."""
        cached = getattr(self, '_plain_english_ids', None)
        if cached and time.monotonic() - cached[0] < self._PLAIN_ENGLISH_TTL:
            return cached[1]
        own = conn is None
        conn = conn or self.get_connection()
        ids = {row[0] for row in conn.execute('''
            SELECT b.id FROM books b WHERE EXISTS (
                SELECT 1 FROM chapters c WHERE c.book_id = b.id
                  AND c.modern_english_text IS NOT NULL
                  AND LENGTH(TRIM(c.modern_english_text, char(32) || char(9) || char(10) || char(13))) > 0)
        ''')}
        if own:
            conn.close()
        self._plain_english_ids = (time.monotonic(), ids)
        return ids

    def _book_cues(self, row) -> Dict:
        """A listing row as a book dict with study cues and `has_plain_english`."""
        book = add_book_cues(dict(row))
        book['has_plain_english'] = book.get('id') in self.plain_english_book_ids()
        return book

    def book_has_modern_english(self, book_id: int) -> bool:
        """True iff at least one chapter for this book has non-empty modern_english_text.

        Treats any whitespace-only value (spaces, tabs, newlines, carriage returns)
        as empty — SQLite's bare TRIM() strips only spaces, so we pass an explicit
        whitespace character set.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM chapters
            WHERE book_id = ?
              AND modern_english_text IS NOT NULL
              AND LENGTH(TRIM(modern_english_text, char(32) || char(9) || char(10) || char(13))) > 0
            LIMIT 1
        ''', (book_id,))
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def get_chapter(self, book_id: int, chapter_number: int) -> Optional[Dict]:
        """Get a single chapter by book ID and chapter number"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM chapters
            WHERE book_id = ? AND chapter_number = ?
        ''', (book_id, chapter_number))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def update_chapter_modern_english(self, book_id: int, chapter_number: int, modern_english_text: str):
        """Update modern English text for a chapter

        Args:
            book_id: Database ID of the book
            chapter_number: Chapter number
            modern_english_text: Modern English translation text
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE chapters
            SET modern_english_text = ?
            WHERE book_id = ? AND chapter_number = ?
        ''', (modern_english_text, book_id, chapter_number))

        conn.commit()
        conn.close()

    def update_chapter_text(self, book_id: int, chapter_number: int, chapter_text: str):
        """Update full text for a chapter

        Args:
            book_id: Database ID of the book
            chapter_number: Chapter number
            chapter_text: Full chapter text
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE chapters
            SET chapter_text = ?
            WHERE book_id = ? AND chapter_number = ?
        ''', (chapter_text, book_id, chapter_number))

        conn.commit()
        conn.close()

    def update_chapter_both_texts(self, book_id: int, chapter_number: int, chapter_text: str = None, modern_english_text: str = None):
        """Update both chapter text and modern English text

        Args:
            book_id: Database ID of the book
            chapter_number: Chapter number
            chapter_text: Full chapter text (optional)
            modern_english_text: Modern English translation text (optional)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        updates = []
        params = []

        if chapter_text is not None:
            updates.append("chapter_text = ?")
            params.append(chapter_text)

        if modern_english_text is not None:
            updates.append("modern_english_text = ?")
            params.append(modern_english_text)

        if not updates:
            conn.close()
            return

        params.extend([book_id, chapter_number])
        query = f'''
            UPDATE chapters
            SET {", ".join(updates)}
            WHERE book_id = ? AND chapter_number = ?
        '''

        cursor.execute(query, params)
        conn.commit()
        conn.close()

    def add_audio_file(self, summary_id: Optional[int], chapter_id: Optional[int],
                      audio_path: str, duration: float) -> int:
        """Add audio file reference"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO audio_files (summary_id, chapter_id, audio_path, duration)
            VALUES (?, ?, ?, ?)
        ''', (summary_id, chapter_id, audio_path, duration))

        audio_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return audio_id

    def get_audio_file(self, summary_id: Optional[int] = None,
                      chapter_id: Optional[int] = None) -> Optional[Dict]:
        """Get audio file by summary_id or chapter_id"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if summary_id:
            cursor.execute('SELECT * FROM audio_files WHERE summary_id = ?', (summary_id,))
        elif chapter_id:
            cursor.execute('SELECT * FROM audio_files WHERE chapter_id = ?', (chapter_id,))
        else:
            conn.close()
            return None

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def add_book_section(self, book_id: int, section_type: str, section_number: int,
                        section_title: str = None) -> int:
        """Add a book section (Part/Book/Act)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO book_sections
            (book_id, section_type, section_number, section_title)
            VALUES (?, ?, ?, ?)
        ''', (book_id, section_type, section_number, section_title))

        section_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return section_id

    def get_book_sections(self, book_id: int) -> List[Dict]:
        """Get all book sections for a book, ordered by section number"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM book_sections
            WHERE book_id = ?
            ORDER BY section_number
        ''', (book_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_chapters_by_section(self, section_id: int) -> List[Dict]:
        """Get all chapters for a specific book section"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM chapters
            WHERE section_id = ?
            ORDER BY chapter_number
        ''', (section_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_chapters_metadata_by_section(self, section_id: int) -> List[Dict]:
        """Get chapter metadata only for a specific book section (no summary or full text)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(f'''
            SELECT id, book_id, chapter_number, chapter_title, word_count, section_id, illustration_url,
                   {CHAPTER_CUE_COLUMNS}
            FROM chapters
            WHERE section_id = ?
            ORDER BY chapter_number
        ''', (section_id,))

        rows = cursor.fetchall()
        conn.close()

        return [add_chapter_cues(dict(row)) for row in rows]

    def get_chapters_without_section(self, book_id: int) -> List[Dict]:
        """Get chapters that don't belong to any section (preface/introduction chapters)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, book_id, chapter_number, chapter_title, summary, word_count,
                   created_at, chapter_text, section_id
            FROM chapters
            WHERE book_id = ? AND section_id IS NULL
            ORDER BY chapter_number
        ''', (book_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_chapters_metadata_without_section(self, book_id: int) -> List[Dict]:
        """Get chapter metadata only for chapters without section (no summary or full text)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(f'''
            SELECT id, book_id, chapter_number, chapter_title, word_count, section_id, illustration_url,
                   {CHAPTER_CUE_COLUMNS}
            FROM chapters
            WHERE book_id = ? AND section_id IS NULL
            ORDER BY chapter_number
        ''', (book_id,))

        rows = cursor.fetchall()
        conn.close()

        return [add_chapter_cues(dict(row)) for row in rows]

    def _build_book_structure(self, book_id: int, metadata_only: bool) -> Dict:
        """Shared control flow for get_book_structure/get_book_structure_metadata —
        the two differ only in which chapter-fetch variant (full vs metadata-only)
        they call at each of the three chapter-loading points below."""
        if metadata_only:
            fetch_without_section = self.get_chapters_metadata_without_section
            fetch_by_section = self.get_chapters_metadata_by_section
            fetch_flat = self.get_chapters_metadata
        else:
            fetch_without_section = self.get_chapters_without_section
            fetch_by_section = self.get_chapters_by_section
            fetch_flat = self.get_chapters

        sections = self.get_book_sections(book_id)

        if sections:
            # Book has sections - return hierarchical structure
            result = {
                'has_sections': True,
                'sections': []
            }

            # First, add any chapters without section_id (preface/introduction)
            preface_chapters = fetch_without_section(book_id)
            if preface_chapters:
                result['sections'].append({
                    'id': None,
                    'type': 'PREFACE',
                    'number': 0,
                    'title': preface_chapters[0].get('chapter_title', 'Preface'),
                    'chapters': preface_chapters
                })

            # Then add regular sections
            for section in sections:
                chapters = fetch_by_section(section['id'])
                result['sections'].append({
                    'id': section['id'],
                    'type': section['section_type'],
                    'number': section['section_number'],
                    'title': section['section_title'],
                    'chapters': chapters
                })

            return result
        else:
            # Book has no sections - return flat chapter list
            chapters = fetch_flat(book_id)
            return {
                'has_sections': False,
                'sections': [{
                    'id': None,
                    'type': None,
                    'number': 1,
                    'title': 'Chapters',
                    'chapters': chapters
                }]
            }

    def get_book_structure(self, book_id: int) -> Dict:
        """
        Get complete book structure including sections and chapters.

        Returns:
        {
            'has_sections': bool,
            'sections': [
                {
                    'id': 1,
                    'type': 'PART',
                    'number': 1,
                    'title': 'The Old Buccaneer',
                    'chapters': [...]
                },
                ...
            ]
        }

        If book has no sections, returns flat chapter list under a single default section.
        """
        return self._build_book_structure(book_id, metadata_only=False)

    def get_book_structure_metadata(self, book_id: int) -> Dict:
        """
        Get book structure with chapter metadata only (no summaries or full text).
        Same structure as get_book_structure but optimized for displaying chapter lists.

        Returns:
        {
            'has_sections': bool,
            'sections': [
                {
                    'id': 1,
                    'type': 'PART',
                    'number': 1,
                    'title': 'The Old Buccaneer',
                    'chapters': [metadata only...]
                },
                ...
            ]
        }
        """
        return self._build_book_structure(book_id, metadata_only=True)

    # Category-related methods

    def add_category(self, name: str, description: str = None) -> int:
        """Add a new category"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR IGNORE INTO categories (name, description)
            VALUES (?, ?)
        ''', (name, description))

        category_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return category_id

    def get_category_redirect(self, old_id: int):
        """For a removed category: the id that replaced it, 'all' when its
        page should go to the Categories page, or None if it never existed."""
        conn = self.get_connection()
        row = conn.execute('SELECT new_id FROM category_redirects WHERE old_id = ?', (old_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return row[0] if row[0] is not None else 'all'

    def get_category(self, category_id: int) -> Optional[Dict]:
        """Get category by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_category_by_name(self, name: str) -> Optional[Dict]:
        """Get category by name"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM categories WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_categories(self) -> List[Dict]:
        """Get all categories"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM categories ORDER BY name')
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def add_book_category(self, book_id: int, category_id: int) -> int:
        """Associate a book with a category"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR IGNORE INTO book_categories (book_id, category_id)
            VALUES (?, ?)
        ''', (book_id, category_id))

        book_category_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return book_category_id

    def remove_book_category(self, book_id: int, category_id: int):
        """Remove category from a book"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM book_categories
            WHERE book_id = ? AND category_id = ?
        ''', (book_id, category_id))

        conn.commit()
        conn.close()

    def get_book_categories(self, book_id: int) -> List[Dict]:
        """Get all categories for a book"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT c.* FROM categories c
            INNER JOIN book_categories bc ON c.id = bc.category_id
            WHERE bc.book_id = ?
            ORDER BY c.name
        ''', (book_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_books_by_category(self, category_id: int) -> List[Dict]:
        """Get all books for a specific category"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT b.id, b.title, b.author, b.filename, b.word_count,
                   b.gutenberg_id, b.cover_image_url, b.created_at, b.slug, b.cefr_level, b.atos_level, b.interest_level, b.school_lists
            FROM books b
            INNER JOIN book_categories bc ON b.id = bc.book_id
            WHERE bc.category_id = ?
            ORDER BY b.title
        ''', (category_id,))

        rows = cursor.fetchall()
        conn.close()

        return [self._book_cues(row) for row in rows]

    def clear_book_categories(self, book_id: int):
        """Remove all categories from a book"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM book_categories WHERE book_id = ?', (book_id,))

        conn.commit()
        conn.close()

    def has_audio_for_summary(self, summary_id: int) -> bool:
        """Check if audio file exists for a summary (in DB or on disk)"""
        if not summary_id:
            return False

        conn = self.get_connection()
        cursor = conn.cursor()

        # Check database first
        cursor.execute('''
            SELECT audio_path FROM audio_files
            WHERE summary_id = ?
        ''', (summary_id,))

        row = cursor.fetchone()

        if row:
            # Verify file exists on disk
            audio_path = config.BASE_DIR / 'frontend' / 'static' / row['audio_path']
            if audio_path.exists():
                conn.close()
                return True

        # If not in database, check for pre-generated audio files on disk
        # Get book_id and summary_type from the summary
        cursor.execute('''
            SELECT book_id, summary_type FROM summaries
            WHERE id = ?
        ''', (summary_id,))

        summary_row = cursor.fetchone()
        conn.close()

        if summary_row:
            book_id = summary_row['book_id']
            summary_type = summary_row['summary_type']

            # Check for pre-generated files with naming pattern: book_{book_id}_{type}_{provider}.{ext}
            # Priority order: opus > gemini wav > vits > legacy complete
            audio_id = f"book_{book_id}_{summary_type}"

            # Check Opus (compressed, speech-optimized)
            opus_path = config.TTS_OUTPUT_DIR / f"{audio_id}_gemini.opus"
            if opus_path.exists():
                return True

            # Check Gemini TTS WAV (fallback)
            gemini_path = config.TTS_OUTPUT_DIR / f"{audio_id}_gemini.wav"
            if gemini_path.exists():
                return True

            # Check VITS TTS
            vits_path = config.TTS_OUTPUT_DIR / f"{audio_id}_vits.wav"
            if vits_path.exists():
                return True

            # Check legacy complete
            complete_path = config.TTS_OUTPUT_DIR / f"{audio_id}_complete.wav"
            if complete_path.exists():
                return True

        return False

    def has_audio_for_chapter(self, chapter_id: int) -> bool:
        """Check if audio file exists for a chapter (in DB or on disk)"""
        if not chapter_id:
            return False

        conn = self.get_connection()
        cursor = conn.cursor()

        # Check database first
        cursor.execute('''
            SELECT audio_path FROM audio_files
            WHERE chapter_id = ?
        ''', (chapter_id,))

        row = cursor.fetchone()

        if row:
            # Verify file exists on disk
            audio_path = config.BASE_DIR / 'frontend' / 'static' / row['audio_path']
            if audio_path.exists():
                conn.close()
                return True

        # If not in database, check for pre-generated audio files on disk
        # Get book_id and chapter_number from the chapter
        cursor.execute('''
            SELECT book_id, chapter_number FROM chapters
            WHERE id = ?
        ''', (chapter_id,))

        chapter_row = cursor.fetchone()
        conn.close()

        if chapter_row:
            book_id = chapter_row['book_id']
            chapter_number = chapter_row['chapter_number']

            # Check for pre-generated files with naming pattern: book_{book_id}_chapter_{chapter_number}_{type}_{provider}.{ext}
            # We check for both summary and fulltext variants
            # Priority order: opus > gemini wav > vits > legacy complete
            for content_type in ['summary', 'fulltext']:
                audio_id = f"book_{book_id}_chapter_{chapter_number}_{content_type}"

                # Check Opus (compressed, speech-optimized)
                opus_path = config.TTS_OUTPUT_DIR / f"{audio_id}_gemini.opus"
                if opus_path.exists():
                    return True

                # Check Gemini TTS WAV (fallback)
                gemini_path = config.TTS_OUTPUT_DIR / f"{audio_id}_gemini.wav"
                if gemini_path.exists():
                    return True

                # Check VITS TTS
                vits_path = config.TTS_OUTPUT_DIR / f"{audio_id}_vits.wav"
                if vits_path.exists():
                    return True

                # Check legacy complete
                complete_path = config.TTS_OUTPUT_DIR / f"{audio_id}_complete.wav"
                if complete_path.exists():
                    return True

        return False

    # Author-related methods

    def add_author(self, name: str, country: str = None, bio: str = None) -> int:
        """Add a new author"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR IGNORE INTO authors (name, country, bio)
            VALUES (?, ?, ?)
        ''', (name, country, bio))

        author_id = cursor.lastrowid

        # If INSERT was ignored (author already exists), get the existing author_id
        if author_id == 0:
            cursor.execute('SELECT id FROM authors WHERE name = ?', (name,))
            row = cursor.fetchone()
            if row:
                author_id = row['id']

        conn.commit()
        conn.close()

        return author_id

    def get_author(self, author_id: int) -> Optional[Dict]:
        """Get author by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM authors WHERE id = ?', (author_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_author_by_name(self, name: str) -> Optional[Dict]:
        """Get author by name"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM authors WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_authors(self) -> List[Dict]:
        """Get all authors"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, name FROM authors ORDER BY name')
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def update_author(self, author_id: int, country: str = None, bio: str = None):
        """Update author information"""
        conn = self.get_connection()
        cursor = conn.cursor()

        updates = []
        params = []

        if country is not None:
            updates.append('country = ?')
            params.append(country)

        if bio is not None:
            updates.append('bio = ?')
            params.append(bio)

        if updates:
            params.append(author_id)
            query = f"UPDATE authors SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

        conn.close()

    def update_book_author_id(self, book_id: int, author_id: int):
        """Update book's author_id foreign key"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE books
            SET author_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (author_id, book_id))

        conn.commit()
        conn.close()

    def get_books_by_author_id(self, author_id: int, exclude_book_id: int = None, limit: int = 5) -> List[Dict]:
        """Get books by author ID, optionally excluding a specific book"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if exclude_book_id:
            cursor.execute('''
                SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, slug, cefr_level, atos_level, interest_level, school_lists
                FROM books
                WHERE author_id = ? AND id != ?
                ORDER BY title
                LIMIT ?
            ''', (author_id, exclude_book_id, limit))
        else:
            cursor.execute('''
                SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, slug, cefr_level, atos_level, interest_level, school_lists
                FROM books
                WHERE author_id = ?
                ORDER BY title
                LIMIT ?
            ''', (author_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [self._book_cues(row) for row in rows]

    def get_books_by_author_name(self, author_name: str, exclude_book_id: int = None, limit: int = 20) -> List[Dict]:
        """Get books by author name, optionally excluding a specific book"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if exclude_book_id:
            cursor.execute('''
                SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, slug, cefr_level, atos_level, interest_level, school_lists
                FROM books
                WHERE LOWER(author) = LOWER(?) AND id != ?
                ORDER BY title
                LIMIT ?
            ''', (author_name, exclude_book_id, limit))
        else:
            cursor.execute('''
                SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, slug, cefr_level, atos_level, interest_level, school_lists
                FROM books
                WHERE LOWER(author) = LOWER(?)
                ORDER BY title
                LIMIT ?
            ''', (author_name, limit))

        rows = cursor.fetchall()
        conn.close()

        return [self._book_cues(row) for row in rows]

    def get_books_in_same_categories(self, book_id: int, limit: int = 10) -> List[Dict]:
        """
        Get books that share categories with the given book.
        Prioritizes books from categories with fewer total books (more specific categories).
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get all categories for this book, ordered by category size (smallest first)
        cursor.execute('''
            SELECT bc.category_id, COUNT(bc2.book_id) as category_size
            FROM book_categories bc
            LEFT JOIN book_categories bc2 ON bc.category_id = bc2.category_id
            WHERE bc.book_id = ?
            GROUP BY bc.category_id
            ORDER BY category_size ASC
        ''', (book_id,))

        categories = cursor.fetchall()

        # Collect books from each category in order (smallest categories first)
        seen_book_ids = {book_id}  # Don't include the current book
        related_books = []

        for category_row in categories:
            category_id = category_row['category_id']

            # Get books from this category that we haven't seen yet
            cursor.execute('''
                SELECT b.id, b.title, b.author, b.filename, b.word_count,
                       b.gutenberg_id, b.cover_image_url, b.slug, b.cefr_level, b.atos_level, b.interest_level, b.school_lists
                FROM books b
                INNER JOIN book_categories bc ON b.id = bc.book_id
                WHERE bc.category_id = ? AND b.id NOT IN ({})
                ORDER BY b.title
            '''.format(','.join('?' * len(seen_book_ids))),
            (category_id, *seen_book_ids))

            category_books = cursor.fetchall()

            for book in category_books:
                if book['id'] not in seen_book_ids:
                    related_books.append(self._book_cues(book))
                    seen_book_ids.add(book['id'])

                    # Stop if we've reached the limit
                    if len(related_books) >= limit:
                        conn.close()
                        return related_books

        conn.close()
        return related_books

    def get_books_by_author_country(self, country: str, exclude_book_id: int = None, limit: int = 5) -> List[Dict]:
        """Get books by authors from the same country"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if exclude_book_id:
            cursor.execute('''
                SELECT b.id, b.title, b.author, b.filename, b.word_count,
                       b.gutenberg_id, b.cover_image_url, b.slug, b.cefr_level, b.atos_level, b.interest_level, b.school_lists
                FROM books b
                INNER JOIN authors a ON b.author_id = a.id
                WHERE a.country = ? AND b.id != ?
                ORDER BY b.title
                LIMIT ?
            ''', (country, exclude_book_id, limit))
        else:
            cursor.execute('''
                SELECT b.id, b.title, b.author, b.filename, b.word_count,
                       b.gutenberg_id, b.cover_image_url, b.slug, b.cefr_level, b.atos_level, b.interest_level, b.school_lists
                FROM books b
                INNER JOIN authors a ON b.author_id = a.id
                WHERE a.country = ?
                ORDER BY b.title
                LIMIT ?
            ''', (country, limit))

        rows = cursor.fetchall()
        conn.close()

        return [self._book_cues(row) for row in rows]

    def get_related_books(self, book_id: int) -> Dict:
        """
        Get related books for a given book, ordered and deduplicated.

        Returns books in this priority order (up to 10 total):
        1. Books by the same author
        2. Books in the same categories (prioritizing smaller/more specific categories)

        Returns:
        {
            'by_author': [...],
            'by_category': [...],
            'by_country': []  # Kept for backwards compatibility but not used
        }
        """
        book = self.get_book(book_id)
        if not book:
            return {'by_author': [], 'by_category': [], 'by_country': []}

        seen_book_ids = {book_id}
        related_books_by_author = []
        related_books_by_category = []

        # 1. Get books by same author (up to 10)
        if book.get('author_id'):
            author_books = self.get_books_by_author_id(book['author_id'], exclude_book_id=book_id, limit=10)
            for book_dict in author_books:
                if book_dict['id'] not in seen_book_ids:
                    related_books_by_author.append(book_dict)
                    seen_book_ids.add(book_dict['id'])

        # 2. Get books in same categories (fill up to 10 total)
        remaining_slots = 10 - len(related_books_by_author)
        if remaining_slots > 0:
            category_books = self.get_books_in_same_categories(book_id, limit=remaining_slots)
            for book_dict in category_books:
                if book_dict['id'] not in seen_book_ids:
                    related_books_by_category.append(book_dict)
                    seen_book_ids.add(book_dict['id'])

        return {
            'by_author': related_books_by_author,
            'by_category': related_books_by_category,
            'by_country': []  # No longer used, kept for backwards compatibility
        }

    def update_book_metadata(self, book_id: int, about_text: str = None, relevance_now: str = None):
        """Update book metadata fields (about_text, relevance_now)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        updates = []
        params = []

        if about_text is not None:
            updates.append("about_text = ?")
            params.append(about_text)

        if relevance_now is not None:
            updates.append("relevance_now = ?")
            params.append(relevance_now)

        if updates:
            params.append(book_id)
            query = f"UPDATE books SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

        conn.close()

    def update_author_info(self, author_name: str, country: str = None, other_books: List[str] = None):
        """Update or create author with country and other books information"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Check if author exists
        cursor.execute("SELECT id, country, other_books FROM authors WHERE name = ?", (author_name,))
        author = cursor.fetchone()

        if author:
            # Update existing author
            author_id = author['id']
            updates = []
            params = []

            if country and not author['country']:  # Only update if not already set
                updates.append("country = ?")
                params.append(country)

            if other_books:
                # Merge with existing books
                # Handle both old comma-separated format and new JSON format
                if author['other_books']:
                    try:
                        existing_books = json.loads(author['other_books'])
                    except (json.JSONDecodeError, TypeError):
                        # Fallback for old comma-separated format
                        existing_books = [b.strip() for b in author['other_books'].split(',') if b.strip()]
                else:
                    existing_books = []
                all_books = list(set(existing_books + other_books))  # Remove duplicates
                updates.append("other_books = ?")
                params.append(json.dumps(all_books[:10]))  # Store as JSON array, limit to 10

            if updates:
                params.append(author_id)
                query = f"UPDATE authors SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
        else:
            # Create new author
            other_books_json = json.dumps(other_books[:10]) if other_books else None
            cursor.execute(
                "INSERT INTO authors (name, country, other_books) VALUES (?, ?, ?)",
                (author_name, country, other_books_json)
            )
            author_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return author_id

    def save_similar_books(self, book_id: int, similar_books: List[Dict[str, str]]):
        """
        Save similar books for a given book.
        similar_books is a list of dicts with 'title' and 'author' keys.
        This method will try to match them to existing books in the database.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # First, clear existing similar books for this book
        cursor.execute("DELETE FROM similar_books WHERE book_id = ?", (book_id,))

        # Try to match each similar book to an existing book in our database
        for rank, similar_book in enumerate(similar_books[:5], start=1):
            title = similar_book['title']
            author = similar_book['author']

            # Try to find matching book in our database
            # First try exact match on title
            cursor.execute(
                "SELECT id FROM books WHERE title = ? AND author LIKE ?",
                (title, f"%{author.split()[0]}%")  # Match on first name of author
            )
            result = cursor.fetchone()

            if result:
                similar_book_id = result['id']
                # Don't create self-reference
                if similar_book_id != book_id:
                    try:
                        cursor.execute(
                            "INSERT INTO similar_books (book_id, similar_book_id, rank) VALUES (?, ?, ?)",
                            (book_id, similar_book_id, rank)
                        )
                    except sqlite3.IntegrityError:
                        # Already exists, skip
                        pass

        conn.commit()
        conn.close()

    def get_similar_books(self, book_id: int, limit: int = 5) -> List[Dict]:
        """Get similar books for a given book"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT b.id, b.title, b.author, b.slug, b.cover_image_url, sb.rank
            FROM similar_books sb
            JOIN books b ON sb.similar_book_id = b.id
            WHERE sb.book_id = ?
            ORDER BY sb.rank
            LIMIT ?
        """, (book_id, limit))

        books = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return books

    # Blog-related methods

    def add_blog_post(self, slug: str, title: str, content: str, excerpt: str = None,
                      author: str = 'Plainly Team', published_date: str = None, header_image_url: str = None) -> int:
        """Add a new blog post to the database"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO blog_posts (slug, title, content, excerpt, author, published_date, updated_date, header_image_url)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (slug, title, content, excerpt, author, published_date, header_image_url))

        blog_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return blog_id

    def get_all_blog_posts(self) -> List[Dict]:
        """Get all blog posts (title, slug, excerpt, date, header image only)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, slug, title, excerpt, author, published_date, created_at, header_image_url
            FROM blog_posts
            ORDER BY published_date DESC, created_at DESC
        ''')

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_blog_post_by_slug(self, slug: str) -> Optional[Dict]:
        """Get full blog post by slug"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM blog_posts
            WHERE slug = ?
        ''', (slug,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    # ------------------------------------------------------------------
    # Continuous-reader hooks (shared.reader.ReaderIndexMixin)
    # ------------------------------------------------------------------

    @staticmethod
    def _reader_load_book(conn: sqlite3.Connection, book_id: int) -> Optional[Dict]:
        row = conn.execute('SELECT id, is_poetry FROM books WHERE id = ?', (book_id,)).fetchone()
        return {'id': row['id'], 'verse': bool(row['is_poetry'])} if row else None

    @classmethod
    def _reader_plain_coverage(cls, chapters: List[Dict]) -> bool:
        return any(cls._reader_split_paragraphs(c.get('modern_english_text') or '') for c in chapters)

    @classmethod
    def _reader_chapter_units(cls, chapter: Dict, verse: bool, plain_coverage: bool) -> Dict[str, List[Optional[str]]]:
        """Paragraph texts of one chapter per mode; None is a Plain English gap.

        The compiler and every read use this one function, so a stored
        (chapter_id, chapter_ordinal) always indexes the same paragraph.
        Side-by-Side row i pairs original[i] with plain[i]."""
        units = {
            'summary': cls._reader_split_paragraphs(chapter.get('summary') or ''),
            'original': cls._reader_split_paragraphs(chapter.get('chapter_text') or '', verse),
            'plain': cls._reader_split_paragraphs(chapter.get('modern_english_text') or ''),
        }
        if not plain_coverage:
            units['plain'] = []
        elif not units['plain']:
            units['plain'] = [None] * max(1, len(units['original']))
        return units

    @staticmethod
    def _reader_load_chapters(conn: sqlite3.Connection, book_id: int, chapter_ids: Optional[List[int]] = None) -> List[Dict]:
        query = '''
            SELECT c.id, c.book_id, c.chapter_number, c.chapter_title, c.chapter_text,
                   c.modern_english_text, c.summary, c.section_id, c.illustration_url,
                   s.section_title
            FROM chapters c LEFT JOIN book_sections s ON s.id = c.section_id
            WHERE c.book_id = ?'''
        params: List = [book_id]
        if chapter_ids is not None:
            query += f" AND c.id IN ({','.join('?' * len(chapter_ids))})"
            params += list(chapter_ids)
        return [dict(row) for row in conn.execute(query + ' ORDER BY c.chapter_number', params).fetchall()]

    def _reader_source_checksum(self, chapters: List[Dict]) -> str:
        source = [
            {
                'id': chapter['id'],
                'number': chapter['chapter_number'],
                'title': chapter.get('chapter_title') or '',
                'summary': chapter.get('summary') or '',
                'original': chapter.get('chapter_text') or '',
                'plain': chapter.get('modern_english_text') or '',
                'section_id': chapter.get('section_id'),
                'section_title': chapter.get('section_title') or '',
                # Only present for verse, so prose checksums are unchanged.
                **({'verse': True} if chapter.get('verse') else {}),
            }
            for chapter in chapters
        ]
        return hashlib.sha256(
            json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        ).hexdigest()

    @staticmethod
    def _reader_structure(conn: sqlite3.Connection, book_id: int) -> List[Dict]:
        structure = []
        seen_sections = set()
        for row in conn.execute('''
            SELECT c.id, c.chapter_number, c.chapter_title, c.illustration_url, c.section_id,
                   s.id AS section_exists, s.section_title
            FROM chapters c LEFT JOIN book_sections s ON s.id = c.section_id
            WHERE c.book_id = ? ORDER BY c.chapter_number
        ''', (book_id,)):
            if row['section_id'] and row['section_id'] not in seen_sections:
                seen_sections.add(row['section_id'])
                if row['section_exists']:
                    structure.append({
                        'kind': 'part', 'section_id': row['section_id'], 'chapter_id': None,
                        'ordinal': len(structure), 'title': row['section_title'] or 'Part',
                        'chapter_number': None, 'illustration_url': None,
                    })
            structure.append({
                'kind': 'chapter', 'section_id': None, 'chapter_id': row['id'], 'ordinal': len(structure),
                'title': row['chapter_title'] or f"Chapter {row['chapter_number']}",
                'chapter_number': row['chapter_number'], 'illustration_url': row['illustration_url'],
            })
        return structure
