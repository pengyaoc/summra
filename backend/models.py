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

        conn.commit()
        conn.close()

    def add_book(self, title: str, author: str, filename: str, full_text: str,
                 gutenberg_id: int = None, cover_image_url: str = None) -> int:
        """Add a new book to the database"""
        conn = self.get_connection()
        cursor = conn.cursor()

        word_count = len(full_text.split())

        cursor.execute('''
            INSERT INTO books (title, author, filename, full_text, word_count, gutenberg_id, cover_image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, author, filename, full_text, word_count, gutenberg_id, cover_image_url))

        book_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return book_id

    def update_book_cover(self, book_id: int, gutenberg_id: int, cover_image_url: str):
        """Update book cover image URL and Gutenberg ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE books
            SET gutenberg_id = ?, cover_image_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (gutenberg_id, cover_image_url, book_id))

        conn.commit()
        conn.close()

    def get_book(self, book_id: int) -> Optional[Dict]:
        """Get book by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM books WHERE id = ?', (book_id,))
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

    def get_all_books(self) -> List[Dict]:
        """Get all books"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, created_at FROM books ORDER BY title')
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

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
                    section_id: int = None) -> int:
        """Add or update a chapter summary"""
        conn = self.get_connection()
        cursor = conn.cursor()

        word_count = len(summary.split())

        cursor.execute('''
            INSERT OR REPLACE INTO chapters
            (book_id, chapter_number, chapter_title, chapter_text, summary, word_count, section_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (book_id, chapter_number, chapter_title, chapter_text, summary, word_count, section_id))

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
            SELECT id, book_id, chapter_number, chapter_title, word_count, section_id
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
            SELECT id, book_id, chapter_number, chapter_title, word_count, section_id
            FROM chapters
            WHERE section_id = ?
            ORDER BY chapter_number
        ''', (section_id,))

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
