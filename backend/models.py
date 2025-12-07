import sqlite3
import json
import wave
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import config


class Database:
    """Database handler for Summra"""

    def __init__(self, db_path: Path = config.DATABASE_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                UNIQUE(book_id, chapter_number)
            )
        ''')

        # Add chapter_text column if it doesn't exist (migration for existing databases)
        try:
            cursor.execute("ALTER TABLE chapters ADD COLUMN chapter_text TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add cover_image_url column if it doesn't exist (migration for existing databases)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN cover_image_url TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add gutenberg_id column if it doesn't exist (migration for existing databases)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN gutenberg_id INTEGER")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add cover_source column if it doesn't exist (migration for existing databases)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN cover_source TEXT DEFAULT 'unknown'")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add slug column for SEO-friendly URLs (migration for existing databases)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN slug TEXT UNIQUE")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add author_id column for foreign key relationship (migration for existing databases)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN author_id INTEGER REFERENCES authors(id)")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

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

        # Add illustration_url column to chapters table if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE chapters ADD COLUMN illustration_url TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add about_text and relevance_now columns to books table if they don't exist (migration)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN about_text TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        try:
            cursor.execute("ALTER TABLE books ADD COLUMN relevance_now TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add modern_english_text column to chapters table if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE chapters ADD COLUMN modern_english_text TEXT")
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

        # Add short_bio and long_bio columns if they don't exist (migration for existing databases)
        try:
            cursor.execute("ALTER TABLE authors ADD COLUMN short_bio TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        try:
            cursor.execute("ALTER TABLE authors ADD COLUMN long_bio TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add character_guide_url column to books table if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN character_guide_url TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add timeline_url column to books table if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN timeline_url TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add themes_url column to books table if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN themes_url TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        conn.commit()
        conn.close()

    def add_book(self, title: str, author: str, filename: str, full_text: str,
                 gutenberg_id: int = None, cover_image_url: str = None, author_id: int = None) -> int:
        """Add a new book to the database

        Args:
            title: Book title
            author: Author name (stored for backward compatibility)
            filename: Original filename
            full_text: Full book text
            gutenberg_id: Project Gutenberg ID (optional)
            cover_image_url: Path to cover image (optional)
            author_id: Foreign key to authors table (optional, will auto-lookup if not provided)

        Returns:
            book_id: The ID of the newly created book
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        word_count = len(full_text.split())

        # Auto-lookup author_id if not provided
        if author_id is None and author:
            author_record = self.get_author_by_name(author)
            if author_record:
                author_id = author_record['id']

        cursor.execute('''
            INSERT INTO books (title, author, filename, full_text, word_count, gutenberg_id, cover_image_url, author_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, author, filename, full_text, word_count, gutenberg_id, cover_image_url, author_id))

        book_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return book_id

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

    def get_book(self, book_id: int) -> Optional[Dict]:
        """Get book by ID with author metadata"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT b.*, a.country as author_country, a.other_books as author_other_books, a.short_bio as author_bio
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.id
            WHERE b.id = ?
        ''', (book_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

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
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT b.*, a.country as author_country, a.other_books as author_other_books, a.short_bio as author_bio
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.id
            WHERE b.slug = ?
        ''', (slug,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

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

        cursor.execute('SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, created_at FROM books ORDER BY title')
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
            INSERT OR REPLACE INTO summaries (book_id, summary_type, content, word_count)
            VALUES (?, ?, ?, ?)
        ''', (book_id, summary_type, content, word_count))

        summary_id = cursor.lastrowid
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
        """Add or update a chapter summary"""
        conn = self.get_connection()
        cursor = conn.cursor()

        word_count = len(summary.split())

        cursor.execute('''
            INSERT OR REPLACE INTO chapters
            (book_id, chapter_number, chapter_title, chapter_text, summary, word_count, section_id, illustration_url, modern_english_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (book_id, chapter_number, chapter_title, chapter_text, summary, word_count, section_id, illustration_url, modern_english_text))

        chapter_id = cursor.lastrowid
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
        sections = self.get_book_sections(book_id)

        if sections:
            # Book has sections - return hierarchical structure
            result = {
                'has_sections': True,
                'sections': []
            }

            # First, add any chapters without section_id (preface/introduction)
            preface_chapters = self.get_chapters_without_section(book_id)
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
                chapters = self.get_chapters_by_section(section['id'])
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
            chapters = self.get_chapters(book_id)
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
        sections = self.get_book_sections(book_id)

        if sections:
            # Book has sections - return hierarchical structure
            result = {
                'has_sections': True,
                'sections': []
            }

            # First, add any chapters without section_id (preface/introduction)
            preface_chapters = self.get_chapters_metadata_without_section(book_id)
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
                chapters = self.get_chapters_metadata_by_section(section['id'])
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
            chapters = self.get_chapters_metadata(book_id)
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
