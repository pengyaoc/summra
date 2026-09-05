"""User management and reading progress database models.

This module handles user authentication and reading progress tracking
in a separate database (summra.db) from the main content database.
"""

import sqlite3
import hashlib
import secrets
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


class UserDatabase:
    """Database handler for user management and reading progress."""

    def __init__(self, db_path: Path = None):
        """Initialize user database.

        Args:
            db_path: Path to user database. Defaults to summra.db in project root.
        """
        if db_path is None:
            # Default to config.USER_DATABASE_PATH (data/summra.db), matching
            # DATABASE_PATH's convention so this stays writable under
            # systemd's ProtectSystem=strict (see tests/test_deploy_config.py).
            try:
                from . import config
            except ImportError:
                from backend import config
            db_path = config.USER_DATABASE_PATH

        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize user database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')

        # Reading progress table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reading_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                chapter_number INTEGER NOT NULL,
                page_number INTEGER DEFAULT 0,
                scroll_position INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, book_id)
            )
        ''')

        # Chapter completion tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapter_completion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                chapter_number INTEGER NOT NULL,
                completed INTEGER DEFAULT 0,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, book_id, chapter_number)
            )
        ''')

        # Create indexes for performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_reading_progress_user
            ON reading_progress(user_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chapter_completion_user
            ON chapter_completion(user_id, book_id)
        ''')

        conn.commit()
        conn.close()

    def hash_password(self, password: str, salt: str = None) -> tuple[str, str]:
        """Hash password with salt using SHA-256.

        Args:
            password: Plain text password
            salt: Optional salt (generates new one if not provided)

        Returns:
            Tuple of (password_hash, salt)
        """
        if salt is None:
            salt = secrets.token_hex(32)

        password_hash = hashlib.sha256(
            (password + salt).encode('utf-8')
        ).hexdigest()

        return password_hash, salt

    def create_user(self, username: str, password: str) -> Optional[int]:
        """Create a new user account.

        Args:
            username: Username (must be unique)
            password: Plain text password

        Returns:
            User ID if successful, None if username already exists
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Hash password
            password_hash, salt = self.hash_password(password)

            # Insert user
            cursor.execute('''
                INSERT INTO users (username, password_hash, salt)
                VALUES (?, ?, ?)
            ''', (username, password_hash, salt))

            user_id = cursor.lastrowid
            conn.commit()
            return user_id

        except sqlite3.IntegrityError:
            # Username already exists
            return None
        finally:
            conn.close()

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            User dict if authenticated, None otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get user
        cursor.execute('''
            SELECT id, username, password_hash, salt, created_at, last_login
            FROM users
            WHERE username = ?
        ''', (username,))

        row = cursor.fetchone()

        if row is None:
            conn.close()
            return None

        # Verify password
        password_hash, _ = self.hash_password(password, row['salt'])

        if password_hash != row['password_hash']:
            conn.close()
            return None

        # Update last login
        cursor.execute('''
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (row['id'],))
        conn.commit()

        # Return user dict
        user = {
            'id': row['id'],
            'username': row['username'],
            'created_at': row['created_at'],
            'last_login': datetime.now().isoformat()
        }

        conn.close()
        return user

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User dict if found, None otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, created_at, last_login
            FROM users
            WHERE id = ?
        ''', (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return {
            'id': row['id'],
            'username': row['username'],
            'created_at': row['created_at'],
            'last_login': row['last_login']
        }

    def save_reading_progress(
        self,
        user_id: int,
        book_id: int,
        chapter_number: int,
        page_number: int = 0,
        scroll_position: int = 0
    ) -> bool:
        """Save or update reading progress for a user.

        Args:
            user_id: User ID
            book_id: Book ID
            chapter_number: Current chapter number
            page_number: Current page number (for pagination)
            scroll_position: Scroll position in pixels

        Returns:
            True if successful
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO reading_progress
            (user_id, book_id, chapter_number, page_number, scroll_position, last_updated)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, book_id) DO UPDATE SET
                chapter_number = excluded.chapter_number,
                page_number = excluded.page_number,
                scroll_position = excluded.scroll_position,
                last_updated = CURRENT_TIMESTAMP
        ''', (user_id, book_id, chapter_number, page_number, scroll_position))

        conn.commit()
        conn.close()
        return True

    def get_reading_progress(self, user_id: int, book_id: int) -> Optional[Dict]:
        """Get reading progress for a user and book.

        Args:
            user_id: User ID
            book_id: Book ID

        Returns:
            Progress dict if found, None otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT chapter_number, page_number, scroll_position, last_updated
            FROM reading_progress
            WHERE user_id = ? AND book_id = ?
        ''', (user_id, book_id))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return {
            'chapter_number': row['chapter_number'],
            'page_number': row['page_number'],
            'scroll_position': row['scroll_position'],
            'last_updated': row['last_updated']
        }

    def get_all_reading_progress(self, user_id: int) -> List[Dict]:
        """Get all reading progress for a user.

        Args:
            user_id: User ID

        Returns:
            List of progress dicts
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT book_id, chapter_number, page_number, scroll_position, last_updated
            FROM reading_progress
            WHERE user_id = ?
            ORDER BY last_updated DESC
        ''', (user_id,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'book_id': row['book_id'],
                'chapter_number': row['chapter_number'],
                'page_number': row['page_number'],
                'scroll_position': row['scroll_position'],
                'last_updated': row['last_updated']
            }
            for row in rows
        ]

    def mark_chapter_complete(
        self,
        user_id: int,
        book_id: int,
        chapter_number: int,
        completed: bool = True
    ) -> bool:
        """Mark a chapter as completed or incomplete.

        Args:
            user_id: User ID
            book_id: Book ID
            chapter_number: Chapter number
            completed: True to mark complete, False to mark incomplete

        Returns:
            True if successful
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if completed:
            cursor.execute('''
                INSERT INTO chapter_completion
                (user_id, book_id, chapter_number, completed, completed_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, book_id, chapter_number) DO UPDATE SET
                    completed = 1,
                    completed_at = CURRENT_TIMESTAMP
            ''', (user_id, book_id, chapter_number))
        else:
            cursor.execute('''
                INSERT INTO chapter_completion
                (user_id, book_id, chapter_number, completed, completed_at)
                VALUES (?, ?, ?, 0, NULL)
                ON CONFLICT(user_id, book_id, chapter_number) DO UPDATE SET
                    completed = 0,
                    completed_at = NULL
            ''', (user_id, book_id, chapter_number))

        conn.commit()
        conn.close()
        return True

    def get_completed_chapters(self, user_id: int, book_id: int) -> List[int]:
        """Get list of completed chapter numbers for a user and book.

        Args:
            user_id: User ID
            book_id: Book ID

        Returns:
            List of completed chapter numbers
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT chapter_number
            FROM chapter_completion
            WHERE user_id = ? AND book_id = ? AND completed = 1
            ORDER BY chapter_number
        ''', (user_id, book_id))

        rows = cursor.fetchall()
        conn.close()

        return [row['chapter_number'] for row in rows]

    def is_chapter_complete(
        self,
        user_id: int,
        book_id: int,
        chapter_number: int
    ) -> bool:
        """Check if a chapter is marked as complete.

        Args:
            user_id: User ID
            book_id: Book ID
            chapter_number: Chapter number

        Returns:
            True if chapter is complete, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT completed
            FROM chapter_completion
            WHERE user_id = ? AND book_id = ? AND chapter_number = ?
        ''', (user_id, book_id, chapter_number))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return False

        return row['completed'] == 1
