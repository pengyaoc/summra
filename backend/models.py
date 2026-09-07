import sqlite3
import json
import wave
import re
import hashlib
import uuid
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

try:
    from . import config
except ImportError:
    from backend import config


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


class Database:
    """Database handler for Summra"""

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
                full_text TEXT,
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

        # Blog posts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                excerpt TEXT,
                author TEXT DEFAULT 'Summra Team',
                published_date DATE,
                updated_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Continuous-reader content. These records are generated from the
        # existing chapter blobs and are immutable once published. Keeping
        # them in the content database means reader requests never need to
        # parse an entire chapter or book on the hot path.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_content_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                alignment_version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft', 'published', 'retired')),
                manifest_etag TEXT NOT NULL,
                source_checksum TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                UNIQUE(book_id, version)
            )
        ''')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reader_one_published_version
            ON reader_content_version(book_id) WHERE status = 'published'
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_mode_manifest (
                content_version_id INTEGER NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('summary', 'original', 'plain', 'side_by_side')),
                availability TEXT NOT NULL CHECK(availability IN ('available', 'partial', 'unavailable')),
                total_word_count INTEGER NOT NULL DEFAULT 0,
                unit_count INTEGER NOT NULL DEFAULT 0,
                first_segment_id TEXT,
                last_segment_id TEXT,
                terminal_paragraph_id TEXT,
                PRIMARY KEY (content_version_id, mode),
                FOREIGN KEY (content_version_id) REFERENCES reader_content_version(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_structure_entry (
                id TEXT PRIMARY KEY,
                content_version_id INTEGER NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('part', 'chapter')),
                section_id INTEGER,
                chapter_id INTEGER,
                ordinal INTEGER NOT NULL,
                title TEXT NOT NULL,
                FOREIGN KEY (content_version_id) REFERENCES reader_content_version(id) ON DELETE CASCADE,
                FOREIGN KEY (section_id) REFERENCES book_sections(id) ON DELETE CASCADE,
                FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
                UNIQUE(content_version_id, ordinal)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_segment (
                id TEXT PRIMARY KEY,
                content_version_id INTEGER NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('summary', 'original', 'plain', 'side_by_side')),
                ordinal INTEGER NOT NULL,
                first_unit_ordinal INTEGER NOT NULL,
                last_unit_ordinal INTEGER NOT NULL,
                first_word_offset INTEGER NOT NULL DEFAULT 0,
                last_word_offset INTEGER NOT NULL DEFAULT 0,
                byte_count INTEGER NOT NULL,
                unit_count INTEGER NOT NULL,
                oversized_unit INTEGER NOT NULL DEFAULT 0,
                etag TEXT NOT NULL,
                FOREIGN KEY (content_version_id) REFERENCES reader_content_version(id) ON DELETE CASCADE,
                UNIQUE(content_version_id, mode, ordinal)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_paragraph (
                id TEXT NOT NULL,
                content_version_id INTEGER NOT NULL,
                segment_id TEXT,
                chapter_id INTEGER NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('summary', 'original', 'plain')),
                availability TEXT NOT NULL DEFAULT 'available' CHECK(availability IN ('available', 'gap')),
                ordinal INTEGER NOT NULL,
                chapter_ordinal INTEGER NOT NULL,
                content TEXT,
                normalized_quote TEXT,
                word_count INTEGER NOT NULL DEFAULT 0,
                word_start INTEGER NOT NULL DEFAULT 0,
                fallback_paragraph_id TEXT,
                FOREIGN KEY (content_version_id) REFERENCES reader_content_version(id) ON DELETE CASCADE,
                FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
                FOREIGN KEY (segment_id) REFERENCES reader_segment(id) ON DELETE SET NULL,
                PRIMARY KEY (content_version_id, id),
                UNIQUE(content_version_id, mode, ordinal),
                UNIQUE(content_version_id, mode, chapter_id, chapter_ordinal)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_alignment_row (
                id TEXT NOT NULL,
                content_version_id INTEGER NOT NULL,
                segment_id TEXT,
                chapter_id INTEGER NOT NULL,
                ordinal INTEGER NOT NULL,
                chapter_ordinal INTEGER NOT NULL,
                canonical_word_count INTEGER NOT NULL DEFAULT 0,
                word_start INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (content_version_id) REFERENCES reader_content_version(id) ON DELETE CASCADE,
                FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
                FOREIGN KEY (segment_id) REFERENCES reader_segment(id) ON DELETE SET NULL,
                PRIMARY KEY (content_version_id, id),
                UNIQUE(content_version_id, ordinal),
                UNIQUE(content_version_id, chapter_id, chapter_ordinal)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_alignment_member (
                content_version_id INTEGER NOT NULL,
                alignment_row_id TEXT NOT NULL,
                member_mode TEXT NOT NULL CHECK(member_mode IN ('original', 'plain')),
                paragraph_id TEXT,
                available INTEGER NOT NULL CHECK(available IN (0, 1)),
                PRIMARY KEY (content_version_id, alignment_row_id, member_mode),
                FOREIGN KEY (content_version_id, alignment_row_id)
                    REFERENCES reader_alignment_row(content_version_id, id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reader_paragraph_mapping (
                content_version_id INTEGER NOT NULL,
                old_content_version INTEGER NOT NULL,
                old_paragraph_id TEXT NOT NULL,
                new_paragraph_id TEXT NOT NULL,
                mapping_reason TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (content_version_id, old_content_version, old_paragraph_id),
                FOREIGN KEY (content_version_id) REFERENCES reader_content_version(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_reader_paragraph_segment
            ON reader_paragraph(segment_id, ordinal)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_reader_alignment_segment
            ON reader_alignment_row(segment_id, ordinal)
        ''')

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

        # books.slug needs a UNIQUE index rather than a UNIQUE column
        # constraint, since SQLite's ALTER TABLE ADD COLUMN doesn't support
        # UNIQUE — add the column (above) then the index separately.
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_books_slug ON books(slug)")
            conn.commit()
        except sqlite3.OperationalError:
            # Index already exists
            pass

        conn.commit()
        conn.close()

    # (table, column_definition) pairs applied by init_db() on every
    # instantiation. Order doesn't matter for correctness — ALTER TABLE ADD
    # COLUMN only requires the target table to already exist (all of them do,
    # created above), not any table a REFERENCES clause points at — but is
    # kept close to the original commit order for readability.
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
    ]

    def add_book(self, title: str, author: str, filename: str, full_text: str,
                 gutenberg_id: int = None, cover_image_url: str = None, author_id: int = None, is_poetry: bool = False) -> int:
        """Add a new book to the database

        Args:
            title: Book title
            author: Author name (stored for backward compatibility)
            filename: Original filename
            full_text: Full book text
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
            INSERT INTO books (title, author, filename, full_text, word_count, gutenberg_id, cover_image_url, author_id, slug, is_poetry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, author, filename, full_text, word_count, gutenberg_id, cover_image_url, author_id, slug, 1 if is_poetry else 0))

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
            return dict(row)
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

    def get_all_books(self) -> List[Dict]:
        """Get all books with their categories"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, created_at, slug, cefr_level FROM books ORDER BY title')
        rows = cursor.fetchall()

        books = [dict(row) for row in rows]

        # Add categories to each book
        for book in books:
            book['categories'] = self.get_book_categories(book['id'])

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

        cursor.execute('''
            SELECT id, book_id, chapter_number, chapter_title, word_count, section_id, illustration_url
            FROM chapters
            WHERE book_id = ?
            ORDER BY chapter_number
        ''', (book_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

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

        cursor.execute('''
            SELECT id, book_id, chapter_number, chapter_title, word_count, section_id, illustration_url
            FROM chapters
            WHERE section_id = ?
            ORDER BY chapter_number
        ''', (section_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

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

        cursor.execute('''
            SELECT id, book_id, chapter_number, chapter_title, word_count, section_id, illustration_url
            FROM chapters
            WHERE book_id = ? AND section_id IS NULL
            ORDER BY chapter_number
        ''', (book_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

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
                   b.gutenberg_id, b.cover_image_url, b.created_at
            FROM books b
            INNER JOIN book_categories bc ON b.id = bc.book_id
            WHERE bc.category_id = ?
            ORDER BY b.title
        ''', (category_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

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
                SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, slug
                FROM books
                WHERE author_id = ? AND id != ?
                ORDER BY title
                LIMIT ?
            ''', (author_id, exclude_book_id, limit))
        else:
            cursor.execute('''
                SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, slug
                FROM books
                WHERE author_id = ?
                ORDER BY title
                LIMIT ?
            ''', (author_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_books_by_author_name(self, author_name: str, exclude_book_id: int = None, limit: int = 20) -> List[Dict]:
        """Get books by author name, optionally excluding a specific book"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if exclude_book_id:
            cursor.execute('''
                SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, slug
                FROM books
                WHERE LOWER(author) = LOWER(?) AND id != ?
                ORDER BY title
                LIMIT ?
            ''', (author_name, exclude_book_id, limit))
        else:
            cursor.execute('''
                SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, slug
                FROM books
                WHERE LOWER(author) = LOWER(?)
                ORDER BY title
                LIMIT ?
            ''', (author_name, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

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
                       b.gutenberg_id, b.cover_image_url, b.slug
                FROM books b
                INNER JOIN book_categories bc ON b.id = bc.book_id
                WHERE bc.category_id = ? AND b.id NOT IN ({})
                ORDER BY b.title
            '''.format(','.join('?' * len(seen_book_ids))),
            (category_id, *seen_book_ids))

            category_books = cursor.fetchall()

            for book in category_books:
                if book['id'] not in seen_book_ids:
                    related_books.append(dict(book))
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
                       b.gutenberg_id, b.cover_image_url, b.slug
                FROM books b
                INNER JOIN authors a ON b.author_id = a.id
                WHERE a.country = ? AND b.id != ?
                ORDER BY b.title
                LIMIT ?
            ''', (country, exclude_book_id, limit))
        else:
            cursor.execute('''
                SELECT b.id, b.title, b.author, b.filename, b.word_count,
                       b.gutenberg_id, b.cover_image_url, b.slug
                FROM books b
                INNER JOIN authors a ON b.author_id = a.id
                WHERE a.country = ?
                ORDER BY b.title
                LIMIT ?
            ''', (country, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

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
                      author: str = 'Summra Team', published_date: str = None, header_image_url: str = None) -> int:
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
    # Continuous-reader content compiler and query surface
    # ------------------------------------------------------------------

    @staticmethod
    def _reader_normalize_quote(text: str) -> str:
        """A short, presentation-independent public-domain recovery excerpt."""
        return re.sub(r'\s+', ' ', (text or '').strip().lower())[:180]

    @staticmethod
    def _reader_split_paragraphs(text: str) -> List[str]:
        """Match the current chapter renderer: every nonempty source line is
        a logical paragraph. Empty source is represented by no rows; callers
        create an explicit Plain-English gap where needed."""
        return [p.strip() for p in (text or '').splitlines() if p.strip()]

    @staticmethod
    def _reader_word_count(text: str) -> int:
        return len(re.findall(r"\b[\w’'-]+\b", text or ''))

    @staticmethod
    def _reader_id(prefix: str) -> str:
        return f'{prefix}_{uuid.uuid4().hex}'

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
            }
            for chapter in chapters
        ]
        return hashlib.sha256(
            json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        ).hexdigest()

    def ensure_reader_content(self, book_id: int) -> Dict:
        """Return the published content version, compiling one when source
        content changed. Compilation is deterministic in ordering and retains
        paragraph identities when a paragraph's normalized source survives.

        A deployment may call this for every book as an explicit backfill;
        the reader routes also call it for a newly opened book so development
        data is usable without a separate operational step.
        """
        conn = self.get_connection()
        try:
            book = conn.execute('SELECT id FROM books WHERE id = ?', (book_id,)).fetchone()
            if not book:
                raise ValueError('Book not found')
            chapters = [dict(row) for row in conn.execute('''
                SELECT id, book_id, chapter_number, chapter_title, chapter_text,
                       modern_english_text, summary, section_id, illustration_url
                FROM chapters WHERE book_id = ? ORDER BY chapter_number
            ''', (book_id,)).fetchall()]
            if not chapters:
                raise ValueError('Book has no chapters')

            checksum = self._reader_source_checksum(chapters)
            published = conn.execute('''
                SELECT * FROM reader_content_version
                WHERE book_id = ? AND status = 'published'
            ''', (book_id,)).fetchone()
            if published and published['source_checksum'] == checksum:
                return dict(published)

            return self._compile_reader_content(conn, book_id, chapters, checksum, dict(published) if published else None)
        finally:
            conn.close()

    def _compile_reader_content(
        self,
        conn: sqlite3.Connection,
        book_id: int,
        chapters: List[Dict],
        checksum: str,
        previous: Optional[Dict],
    ) -> Dict:
        """Compile one immutable reader version in a single transaction."""
        max_version = conn.execute(
            'SELECT COALESCE(MAX(version), 0) AS max_version FROM reader_content_version WHERE book_id = ?',
            (book_id,),
        ).fetchone()['max_version']
        version_number = max_version + 1
        manifest_seed = f'{book_id}:{version_number}:{checksum}'
        manifest_etag = hashlib.sha256(manifest_seed.encode('utf-8')).hexdigest()

        # A unique normalized source match lets ordinary regenerated content
        # retain its durable ID. Ambiguous repeated paragraphs intentionally
        # receive a new ID and are covered by ordinal recovery/mapping.
        reusable_ids: Dict[tuple, List[str]] = defaultdict(list)
        previous_version_id = previous['id'] if previous else None
        if previous_version_id:
            for row in conn.execute('''
                SELECT id, mode, chapter_id, normalized_quote
                FROM reader_paragraph
                WHERE content_version_id = ? AND normalized_quote IS NOT NULL
            ''', (previous_version_id,)):
                reusable_ids[(row['mode'], row['chapter_id'], row['normalized_quote'])].append(row['id'])

        with conn:
            conn.execute('''
                INSERT INTO reader_content_version
                    (book_id, version, alignment_version, status, manifest_etag, source_checksum)
                VALUES (?, ?, 1, 'draft', ?, ?)
            ''', (book_id, version_number, manifest_etag, checksum))
            content_version_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']

            # Structural hierarchy is versioned because it is part of a
            # reader manifest, even though the source chapter IDs remain
            # stable across versions.
            structure_ordinal = 0
            seen_sections = set()
            for chapter in chapters:
                section_id = chapter.get('section_id')
                if section_id and section_id not in seen_sections:
                    section = conn.execute(
                        'SELECT section_title FROM book_sections WHERE id = ?', (section_id,)
                    ).fetchone()
                    if section:
                        conn.execute('''
                            INSERT INTO reader_structure_entry
                                (id, content_version_id, kind, section_id, chapter_id, ordinal, title)
                            VALUES (?, ?, 'part', ?, NULL, ?, ?)
                        ''', (
                            self._reader_id('struct'), content_version_id, section_id,
                            structure_ordinal, section['section_title'] or 'Part',
                        ))
                        structure_ordinal += 1
                    seen_sections.add(section_id)
                conn.execute('''
                    INSERT INTO reader_structure_entry
                        (id, content_version_id, kind, section_id, chapter_id, ordinal, title)
                    VALUES (?, ?, 'chapter', NULL, ?, ?, ?)
                ''', (
                    self._reader_id('struct'), content_version_id, chapter['id'], structure_ordinal,
                    chapter.get('chapter_title') or f"Chapter {chapter['chapter_number']}",
                ))
                structure_ordinal += 1

            paragraph_rows: Dict[str, List[Dict]] = {'summary': [], 'original': [], 'plain': []}
            global_ordinal = {'summary': 0, 'original': 0, 'plain': 0}
            by_chapter_mode: Dict[tuple, List[Dict]] = {}

            def paragraph_id_for(mode: str, chapter_id: int, text: str) -> str:
                quote = self._reader_normalize_quote(text)
                candidates = reusable_ids.get((mode, chapter_id, quote), [])
                return candidates.pop() if len(candidates) == 1 else self._reader_id('para')

            # Summary, Original, and Plain English all have separate logical
            # sequences. Plain gaps are emitted only when the book has at
            # least some Plain English coverage; a fully absent mode is
            # reported unavailable instead of creating a fake sequence.
            plain_coverage = any(self._reader_split_paragraphs(c.get('modern_english_text') or '') for c in chapters)
            for chapter in chapters:
                source_by_mode = {
                    'summary': self._reader_split_paragraphs(chapter.get('summary') or ''),
                    'original': self._reader_split_paragraphs(chapter.get('chapter_text') or ''),
                    'plain': self._reader_split_paragraphs(chapter.get('modern_english_text') or ''),
                }
                for mode in ('summary', 'original', 'plain'):
                    source = source_by_mode[mode]
                    rows = []
                    if mode == 'plain' and not source and plain_coverage:
                        originals = source_by_mode['original'] or ['']
                        source = [None] * len(originals)
                    for chapter_ordinal, text in enumerate(source):
                        availability = 'available' if text is not None else 'gap'
                        fallback_id = None
                        if mode == 'plain' and text is None:
                            original_rows = by_chapter_mode.get((chapter['id'], 'original'), [])
                            if chapter_ordinal < len(original_rows):
                                fallback_id = original_rows[chapter_ordinal]['id']
                        text = text or ''
                        row = {
                            'id': paragraph_id_for(mode, chapter['id'], text) if availability == 'available' else self._reader_id('gap'),
                            'chapter_id': chapter['id'],
                            'mode': mode,
                            'availability': availability,
                            'ordinal': global_ordinal[mode],
                            'chapter_ordinal': chapter_ordinal,
                            'content': text if availability == 'available' else None,
                            'normalized_quote': self._reader_normalize_quote(text) if availability == 'available' else None,
                            'word_count': self._reader_word_count(text) if availability == 'available' else 0,
                            'fallback_paragraph_id': fallback_id,
                        }
                        global_ordinal[mode] += 1
                        rows.append(row)
                        paragraph_rows[mode].append(row)
                    by_chapter_mode[(chapter['id'], mode)] = rows

            for mode, rows in paragraph_rows.items():
                word_start = 0
                for row in rows:
                    row['word_start'] = word_start
                    word_start += row['word_count']
                    conn.execute('''
                        INSERT INTO reader_paragraph
                            (id, content_version_id, chapter_id, mode, availability, ordinal,
                             chapter_ordinal, content, normalized_quote, word_count, word_start,
                             fallback_paragraph_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['id'], content_version_id, row['chapter_id'], row['mode'], row['availability'],
                        row['ordinal'], row['chapter_ordinal'], row['content'], row['normalized_quote'],
                        row['word_count'], row['word_start'], row['fallback_paragraph_id'],
                    ))

            alignment_rows: List[Dict] = []
            alignment_ordinal = 0
            alignment_word_start = 0
            for chapter in chapters:
                originals = by_chapter_mode.get((chapter['id'], 'original'), [])
                plains = by_chapter_mode.get((chapter['id'], 'plain'), []) if plain_coverage else []
                for chapter_ordinal in range(max(len(originals), len(plains))):
                    original = originals[chapter_ordinal] if chapter_ordinal < len(originals) else None
                    plain = plains[chapter_ordinal] if chapter_ordinal < len(plains) else None
                    canonical_words = (original or plain or {}).get('word_count', 0)
                    row = {
                        'id': self._reader_id('alignment'),
                        'chapter_id': chapter['id'],
                        'ordinal': alignment_ordinal,
                        'chapter_ordinal': chapter_ordinal,
                        'canonical_word_count': canonical_words,
                        'word_start': alignment_word_start,
                        'original': original,
                        'plain': plain,
                    }
                    alignment_rows.append(row)
                    alignment_ordinal += 1
                    alignment_word_start += canonical_words
                    conn.execute('''
                        INSERT INTO reader_alignment_row
                            (id, content_version_id, chapter_id, ordinal, chapter_ordinal,
                             canonical_word_count, word_start)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['id'], content_version_id, row['chapter_id'], row['ordinal'],
                        row['chapter_ordinal'], row['canonical_word_count'], row['word_start'],
                    ))
                    for member_mode, member in (('original', original), ('plain', plain)):
                        available = bool(member and member['availability'] == 'available')
                        conn.execute('''
                            INSERT INTO reader_alignment_member
                                (content_version_id, alignment_row_id, member_mode, paragraph_id, available)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            content_version_id, row['id'], member_mode,
                            member['id'] if available else None, int(available),
                        ))

            def make_segments(mode: str, rows: List[Dict], text_for_row) -> List[Dict]:
                segments = []
                current = []
                byte_count = 0
                for row in rows:
                    row_bytes = len((text_for_row(row) or '').encode('utf-8'))
                    would_overflow = current and (len(current) >= 80 or byte_count + row_bytes > 24 * 1024)
                    if would_overflow:
                        segments.append((current, byte_count))
                        current, byte_count = [], 0
                    current.append(row)
                    byte_count += row_bytes
                    if row_bytes > 64 * 1024:
                        segments.append((current, byte_count))
                        current, byte_count = [], 0
                if current:
                    segments.append((current, byte_count))

                saved = []
                for segment_ordinal, (units, size) in enumerate(segments):
                    segment_id = self._reader_id('segment')
                    oversized = int(len(units) == 1 and size > 64 * 1024)
                    etag = hashlib.sha256(
                        f'{content_version_id}:{mode}:{segment_ordinal}:{size}:{units[0]["id"]}:{units[-1]["id"]}'.encode('utf-8')
                    ).hexdigest()
                    conn.execute('''
                        INSERT INTO reader_segment
                            (id, content_version_id, mode, ordinal, first_unit_ordinal, last_unit_ordinal,
                             first_word_offset, last_word_offset, byte_count, unit_count, oversized_unit, etag)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        segment_id, content_version_id, mode, segment_ordinal,
                        units[0]['ordinal'], units[-1]['ordinal'], units[0]['word_start'],
                        units[-1]['word_start'] + units[-1].get('word_count', units[-1].get('canonical_word_count', 0)),
                        size, len(units), oversized, etag,
                    ))
                    for unit in units:
                        target = 'reader_alignment_row' if mode == 'side_by_side' else 'reader_paragraph'
                        conn.execute(
                            f'UPDATE {target} SET segment_id = ? WHERE content_version_id = ? AND id = ?',
                            (segment_id, content_version_id, unit['id']),
                        )
                    saved.append({'id': segment_id, 'ordinal': segment_ordinal, 'etag': etag})
                return saved

            all_segments = {}
            for mode in ('summary', 'original', 'plain'):
                all_segments[mode] = make_segments(mode, paragraph_rows[mode], lambda row: row.get('content') or '')
            all_segments['side_by_side'] = make_segments(
                'side_by_side', alignment_rows,
                lambda row: ' '.join(
                    (member or {}).get('content') or '' for member in (row.get('original'), row.get('plain'))
                ),
            )

            for mode in ('summary', 'original', 'plain', 'side_by_side'):
                rows = alignment_rows if mode == 'side_by_side' else paragraph_rows[mode]
                total_words = sum(row.get('canonical_word_count', row.get('word_count', 0)) for row in rows)
                if mode == 'plain' and not plain_coverage:
                    availability = 'unavailable'
                elif mode == 'plain' and any(row['availability'] == 'gap' for row in rows):
                    availability = 'partial'
                elif mode == 'side_by_side' and not plain_coverage:
                    availability = 'unavailable'
                elif rows:
                    availability = 'available'
                else:
                    availability = 'unavailable'
                segments = all_segments[mode] if availability != 'unavailable' else []
                conn.execute('''
                    INSERT INTO reader_mode_manifest
                        (content_version_id, mode, availability, total_word_count, unit_count,
                         first_segment_id, last_segment_id, terminal_paragraph_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    content_version_id, mode, availability, total_words, len(rows),
                    segments[0]['id'] if segments else None,
                    segments[-1]['id'] if segments else None,
                    rows[-1]['id'] if rows and segments else None,
                ))

            if previous_version_id:
                old_rows = conn.execute('''
                    SELECT id, mode, chapter_id, chapter_ordinal, normalized_quote
                    FROM reader_paragraph WHERE content_version_id = ?
                ''', (previous_version_id,)).fetchall()
                current_by_quote = {
                    (row['mode'], row['chapter_id'], row['normalized_quote']): row['id']
                    for rows in paragraph_rows.values() for row in rows
                    if row['normalized_quote']
                }
                current_by_ordinal = {
                    (row['mode'], row['chapter_id'], row['chapter_ordinal']): row['id']
                    for rows in paragraph_rows.values() for row in rows
                }
                for old in old_rows:
                    new_id = current_by_quote.get((old['mode'], old['chapter_id'], old['normalized_quote']))
                    reason = 'quote' if new_id else 'ordinal'
                    new_id = new_id or current_by_ordinal.get((old['mode'], old['chapter_id'], old['chapter_ordinal']))
                    if new_id:
                        conn.execute('''
                            INSERT INTO reader_paragraph_mapping
                                (content_version_id, old_content_version, old_paragraph_id,
                                 new_paragraph_id, mapping_reason, confidence)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            content_version_id, previous_version_id, old['id'], new_id,
                            reason, 1.0 if reason == 'quote' else 0.7,
                        ))

            if previous_version_id:
                conn.execute("UPDATE reader_content_version SET status = 'retired' WHERE id = ?", (previous_version_id,))
            conn.execute('''
                UPDATE reader_content_version
                SET status = 'published', published_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (content_version_id,))

        return dict(conn.execute('SELECT * FROM reader_content_version WHERE id = ?', (content_version_id,)).fetchone())

    def get_reader_manifest(self, book_id: int) -> Dict:
        version = self.ensure_reader_content(book_id)
        conn = self.get_connection()
        try:
            book = self.get_book(book_id)
            if not book:
                raise ValueError('Book not found')
            modes = [dict(row) for row in conn.execute('''
                SELECT mode, availability, total_word_count, unit_count, first_segment_id,
                       last_segment_id, terminal_paragraph_id
                FROM reader_mode_manifest WHERE content_version_id = ? ORDER BY
                    CASE mode WHEN 'summary' THEN 1 WHEN 'original' THEN 2 WHEN 'plain' THEN 3 ELSE 4 END
            ''', (version['id'],)).fetchall()]
            segments = [dict(row) for row in conn.execute('''
                SELECT id, mode, ordinal, first_unit_ordinal, last_unit_ordinal,
                       first_word_offset, last_word_offset, byte_count, unit_count, oversized_unit, etag
                FROM reader_segment WHERE content_version_id = ? ORDER BY mode, ordinal
            ''', (version['id'],)).fetchall()]
            structure = [dict(row) for row in conn.execute('''
                SELECT s.kind, s.section_id, s.chapter_id, s.ordinal, s.title,
                       c.chapter_number, c.illustration_url
                FROM reader_structure_entry s
                LEFT JOIN chapters c ON c.id = s.chapter_id
                WHERE s.content_version_id = ? ORDER BY s.ordinal
            ''', (version['id'],)).fetchall()]
            return {
                'book': {
                    'id': book['id'], 'slug': book['slug'], 'title': book['title'],
                    'author': book['author'], 'cover_image_url': book.get('cover_image_url'),
                },
                'content_version': version['version'],
                'content_version_id': version['id'],
                'etag': version['manifest_etag'],
                'modes': modes,
                'structure': structure,
                'segments': segments,
            }
        finally:
            conn.close()

    def get_reader_segment(self, book_id: int, segment_id: str, mode: str) -> Optional[Dict]:
        if mode not in {'summary', 'original', 'plain', 'side_by_side'}:
            return None
        version = self.ensure_reader_content(book_id)
        conn = self.get_connection()
        try:
            segment = conn.execute('''
                SELECT * FROM reader_segment
                WHERE id = ? AND content_version_id = ? AND mode = ?
            ''', (segment_id, version['id'], mode)).fetchone()
            if not segment:
                return None
            segment = dict(segment)
            previous = conn.execute('''
                SELECT id FROM reader_segment WHERE content_version_id = ? AND mode = ? AND ordinal = ?
            ''', (version['id'], mode, segment['ordinal'] - 1)).fetchone()
            following = conn.execute('''
                SELECT id FROM reader_segment WHERE content_version_id = ? AND mode = ? AND ordinal = ?
            ''', (version['id'], mode, segment['ordinal'] + 1)).fetchone()
            if mode == 'side_by_side':
                rows = [dict(row) for row in conn.execute('''
                    SELECT r.id, r.chapter_id, r.ordinal, r.chapter_ordinal,
                           r.canonical_word_count, r.word_start,
                           c.chapter_number, c.chapter_title
                    FROM reader_alignment_row r JOIN chapters c ON c.id = r.chapter_id
                    WHERE r.content_version_id = ? AND r.segment_id = ? ORDER BY r.ordinal
                ''', (version['id'], segment_id)).fetchall()]
                for row in rows:
                    members = conn.execute('''
                        SELECT m.member_mode, m.available, p.id, p.content, p.normalized_quote, p.word_count
                        FROM reader_alignment_member m
                        LEFT JOIN reader_paragraph p
                          ON p.content_version_id = m.content_version_id AND p.id = m.paragraph_id
                        WHERE m.content_version_id = ? AND m.alignment_row_id = ?
                    ''', (version['id'], row['id'])).fetchall()
                    row['members'] = {member['member_mode']: dict(member) for member in members}
                units = rows
            else:
                units = [dict(row) for row in conn.execute('''
                    SELECT p.id, p.chapter_id, p.ordinal, p.chapter_ordinal, p.content,
                           p.availability, p.normalized_quote, p.word_count, p.word_start,
                           p.fallback_paragraph_id, c.chapter_number, c.chapter_title
                    FROM reader_paragraph p JOIN chapters c ON c.id = p.chapter_id
                    WHERE p.content_version_id = ? AND p.segment_id = ? ORDER BY p.ordinal
                ''', (version['id'], segment_id)).fetchall()]
            return {
                'id': segment['id'], 'mode': mode, 'content_version': version['version'],
                'etag': segment['etag'], 'previous_segment_id': previous['id'] if previous else None,
                'next_segment_id': following['id'] if following else None, 'units': units,
                'word_range': [segment['first_word_offset'], segment['last_word_offset']],
            }
        finally:
            conn.close()

    def resolve_reader_marker(self, book_id: int, marker: Dict) -> Optional[Dict]:
        """Validate and enrich a marker with authoritative ordering values."""
        if not marker or marker.get('mode') not in {'summary', 'original', 'plain', 'side_by_side'}:
            return None
        version = self.ensure_reader_content(book_id)
        if marker.get('content_version') not in (None, version['version']):
            # Content changed; mapping/recovery is handled by the reader on
            # retrieval. New writes always target the published version.
            return None
        offset = marker.get('offset', 0)
        try:
            offset = max(0.0, min(1.0, float(offset)))
        except (TypeError, ValueError):
            return None
        conn = self.get_connection()
        try:
            if marker['mode'] == 'side_by_side':
                row = conn.execute('''
                    SELECT id, chapter_id, ordinal, word_start, canonical_word_count
                    FROM reader_alignment_row
                    WHERE content_version_id = ? AND id = ?
                ''', (version['id'], marker.get('paragraph_id'))).fetchone()
                if not row:
                    return None
                words = row['canonical_word_count']
            else:
                row = conn.execute('''
                    SELECT id, chapter_id, ordinal, word_start, word_count, normalized_quote
                    FROM reader_paragraph
                    WHERE content_version_id = ? AND mode = ? AND id = ?
                ''', (version['id'], marker['mode'], marker.get('paragraph_id'))).fetchone()
                if not row:
                    return None
                words = row['word_count']
            if marker.get('chapter_id') not in (None, row['chapter_id']):
                return None
            return {
                'book_id': book_id, 'mode': marker['mode'], 'content_version': version['version'],
                'chapter_id': row['chapter_id'], 'paragraph_id': row['id'], 'offset': offset,
                'quote': marker.get('quote') or (row['normalized_quote'] if 'normalized_quote' in row.keys() else ''),
                'ordinal': row['ordinal'], 'word_position': row['word_start'] + int(words * offset),
            }
        finally:
            conn.close()

    def recover_reader_marker(self, book_id: int, marker: Dict) -> Optional[Dict]:
        """Recover a historical marker into the current published version.

        Recovery is deliberately read-only.  The caller can render the result
        and only persist it after a real post-restore reader action, so a
        failed/cancelled restore never destroys the original durable anchor.
        """
        if not marker or marker.get('mode') not in {'summary', 'original', 'plain', 'side_by_side'}:
            return None
        version = self.ensure_reader_content(book_id)
        current_version = version['version']
        source_version = marker.get('content_version')
        if source_version in (None, current_version):
            resolved = self.resolve_reader_marker(book_id, marker)
            if resolved:
                resolved['recovery_level'] = 'same_id'
            return resolved

        conn = self.get_connection()
        try:
            old_version = conn.execute('''
                SELECT id FROM reader_content_version WHERE book_id = ? AND version = ?
            ''', (book_id, source_version)).fetchone()
            if not old_version:
                return None
            mode = marker['mode']
            old_id = marker.get('paragraph_id')
            old_chapter = marker.get('chapter_id')
            target_id = None
            target_chapter = old_chapter
            recovery_level = None

            if mode == 'side_by_side':
                same = conn.execute('''
                    SELECT id, chapter_id FROM reader_alignment_row
                    WHERE content_version_id = ? AND id = ?
                ''', (version['id'], old_id)).fetchone()
                if same:
                    target_id, target_chapter, recovery_level = same['id'], same['chapter_id'], 'same_id'
                if not target_id:
                    mapped = conn.execute('''
                        SELECT current_member.alignment_row_id AS id, current_row.chapter_id
                        FROM reader_alignment_member old_member
                        JOIN reader_paragraph_mapping mapping
                          ON mapping.old_content_version = old_member.content_version_id
                         AND mapping.old_paragraph_id = old_member.paragraph_id
                         AND mapping.content_version_id = ?
                        JOIN reader_alignment_member current_member
                          ON current_member.content_version_id = ?
                         AND current_member.paragraph_id = mapping.new_paragraph_id
                        JOIN reader_alignment_row current_row
                          ON current_row.content_version_id = current_member.content_version_id
                         AND current_row.id = current_member.alignment_row_id
                        WHERE old_member.content_version_id = ? AND old_member.alignment_row_id = ?
                          AND old_member.available = 1
                        ORDER BY CASE old_member.member_mode WHEN 'original' THEN 0 ELSE 1 END
                        LIMIT 1
                    ''', (version['id'], version['id'], old_version['id'], old_id)).fetchone()
                    if mapped:
                        target_id, target_chapter, recovery_level = mapped['id'], mapped['chapter_id'], 'mapping'
                if not target_id:
                    old_row = conn.execute('''
                        SELECT chapter_id, chapter_ordinal FROM reader_alignment_row
                        WHERE content_version_id = ? AND id = ?
                    ''', (old_version['id'], old_id)).fetchone()
                    if old_row:
                        nearest = conn.execute('''
                            SELECT id, chapter_id FROM reader_alignment_row
                            WHERE content_version_id = ? AND chapter_id = ?
                            ORDER BY ABS(chapter_ordinal - ?) ASC, chapter_ordinal ASC LIMIT 1
                        ''', (version['id'], old_row['chapter_id'], old_row['chapter_ordinal'])).fetchone()
                        if nearest:
                            target_id, target_chapter, recovery_level = nearest['id'], nearest['chapter_id'], 'ordinal'
            else:
                same = conn.execute('''
                    SELECT id, chapter_id FROM reader_paragraph
                    WHERE content_version_id = ? AND mode = ? AND id = ?
                ''', (version['id'], mode, old_id)).fetchone()
                if same:
                    target_id, target_chapter, recovery_level = same['id'], same['chapter_id'], 'same_id'
                if not target_id:
                    mapped = conn.execute('''
                        SELECT new_paragraph_id AS id FROM reader_paragraph_mapping
                        WHERE content_version_id = ? AND old_content_version = ? AND old_paragraph_id = ?
                    ''', (version['id'], old_version['id'], old_id)).fetchone()
                    if mapped:
                        target = conn.execute('''
                            SELECT id, chapter_id FROM reader_paragraph
                            WHERE content_version_id = ? AND mode = ? AND id = ?
                        ''', (version['id'], mode, mapped['id'])).fetchone()
                        if target:
                            target_id, target_chapter, recovery_level = target['id'], target['chapter_id'], 'mapping'
                if not target_id and marker.get('quote'):
                    quote = self._reader_normalize_quote(marker['quote'])
                    quoted = conn.execute('''
                        SELECT id, chapter_id FROM reader_paragraph
                        WHERE content_version_id = ? AND mode = ? AND chapter_id = ?
                          AND normalized_quote = ?
                    ''', (version['id'], mode, old_chapter, quote)).fetchall()
                    if len(quoted) == 1:
                        target_id, target_chapter, recovery_level = quoted[0]['id'], quoted[0]['chapter_id'], 'quote'
                if not target_id:
                    old_row = conn.execute('''
                        SELECT chapter_id, chapter_ordinal FROM reader_paragraph
                        WHERE content_version_id = ? AND mode = ? AND id = ?
                    ''', (old_version['id'], mode, old_id)).fetchone()
                    if old_row:
                        nearest = conn.execute('''
                            SELECT id, chapter_id FROM reader_paragraph
                            WHERE content_version_id = ? AND mode = ? AND chapter_id = ?
                            ORDER BY ABS(chapter_ordinal - ?) ASC, chapter_ordinal ASC LIMIT 1
                        ''', (version['id'], mode, old_row['chapter_id'], old_row['chapter_ordinal'])).fetchone()
                        if nearest:
                            target_id, target_chapter, recovery_level = nearest['id'], nearest['chapter_id'], 'ordinal'

            if not target_id and old_chapter:
                table = 'reader_alignment_row' if mode == 'side_by_side' else 'reader_paragraph'
                mode_clause = '' if mode == 'side_by_side' else ' AND mode = ?'
                params = [version['id'], old_chapter]
                if mode != 'side_by_side':
                    params.append(mode)
                chapter_opening = conn.execute(
                    f'''SELECT id, chapter_id FROM {table}
                        WHERE content_version_id = ? AND chapter_id = ?{mode_clause}
                        ORDER BY chapter_ordinal LIMIT 1''', params
                ).fetchone()
                if chapter_opening:
                    target_id, target_chapter, recovery_level = chapter_opening['id'], chapter_opening['chapter_id'], 'chapter_opening'
            if not target_id:
                table = 'reader_alignment_row' if mode == 'side_by_side' else 'reader_paragraph'
                mode_clause = '' if mode == 'side_by_side' else ' AND mode = ?'
                params = [version['id']]
                if mode != 'side_by_side':
                    params.append(mode)
                opening = conn.execute(
                    f'''SELECT id, chapter_id FROM {table}
                        WHERE content_version_id = ?{mode_clause}
                        ORDER BY ordinal LIMIT 1''', params
                ).fetchone()
                if opening:
                    target_id, target_chapter, recovery_level = opening['id'], opening['chapter_id'], 'book_opening'
            if not target_id:
                return None
            recovered = self.resolve_reader_marker(book_id, {
                'mode': mode, 'content_version': current_version, 'chapter_id': target_chapter,
                'paragraph_id': target_id, 'offset': marker.get('offset', 0),
            })
            if recovered:
                recovered['recovery_level'] = recovery_level
            return recovered
        finally:
            conn.close()

    def map_reader_marker(self, book_id: int, marker: Dict, target_mode: str) -> Optional[Dict]:
        """Map a published marker into another reader mode.

        Full-text modes use the explicit alignment rows. Summary mappings are
        intentionally chapter-scoped because summaries are not sentence-aligned
        with source text.
        """
        if target_mode not in {'summary', 'original', 'plain', 'side_by_side'}:
            return None
        source = self.resolve_reader_marker(book_id, marker)
        if not source:
            return None
        if source['mode'] == target_mode:
            return source
        version = self.ensure_reader_content(book_id)
        conn = self.get_connection()
        try:
            target = None
            if target_mode == 'summary':
                target = conn.execute('''
                    SELECT id, chapter_id FROM reader_paragraph
                    WHERE content_version_id = ? AND mode = 'summary' AND availability = 'available'
                      AND chapter_id = ? ORDER BY chapter_ordinal LIMIT 1
                ''', (version['id'], source['chapter_id'])).fetchone()
            elif source['mode'] == 'summary':
                if target_mode == 'side_by_side':
                    target = conn.execute('''
                        SELECT id, chapter_id FROM reader_alignment_row
                        WHERE content_version_id = ? AND chapter_id = ? ORDER BY chapter_ordinal LIMIT 1
                    ''', (version['id'], source['chapter_id'])).fetchone()
                else:
                    target = conn.execute('''
                        SELECT id, chapter_id FROM reader_paragraph
                        WHERE content_version_id = ? AND mode = ? AND availability = 'available'
                          AND chapter_id = ? ORDER BY chapter_ordinal LIMIT 1
                    ''', (version['id'], target_mode, source['chapter_id'])).fetchone()
            elif source['mode'] == 'side_by_side':
                target = conn.execute('''
                    SELECT p.id, p.chapter_id
                    FROM reader_alignment_member m
                    JOIN reader_paragraph p
                      ON p.content_version_id = m.content_version_id AND p.id = m.paragraph_id
                    WHERE m.content_version_id = ? AND m.alignment_row_id = ?
                      AND m.member_mode = ? AND m.available = 1
                ''', (version['id'], source['paragraph_id'], target_mode)).fetchone()
            elif target_mode == 'side_by_side':
                target = conn.execute('''
                    SELECT m.alignment_row_id AS id, r.chapter_id
                    FROM reader_alignment_member m
                    JOIN reader_alignment_row r
                      ON r.content_version_id = m.content_version_id AND r.id = m.alignment_row_id
                    WHERE m.content_version_id = ? AND m.paragraph_id = ? AND m.member_mode = ?
                ''', (version['id'], source['paragraph_id'], source['mode'])).fetchone()
            else:
                target = conn.execute('''
                    SELECT p.id, p.chapter_id
                    FROM reader_alignment_member source_member
                    JOIN reader_alignment_member target_member
                      ON target_member.content_version_id = source_member.content_version_id
                     AND target_member.alignment_row_id = source_member.alignment_row_id
                    JOIN reader_paragraph p
                      ON p.content_version_id = target_member.content_version_id AND p.id = target_member.paragraph_id
                    WHERE source_member.content_version_id = ? AND source_member.paragraph_id = ?
                      AND source_member.member_mode = ? AND target_member.member_mode = ?
                      AND target_member.available = 1
                ''', (version['id'], source['paragraph_id'], source['mode'], target_mode)).fetchone()
            if not target:
                return None
            return self.resolve_reader_marker(book_id, {
                'mode': target_mode, 'content_version': version['version'],
                'chapter_id': target['chapter_id'], 'paragraph_id': target['id'], 'offset': 0,
            })
        finally:
            conn.close()
