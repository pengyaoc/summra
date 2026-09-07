"""Authenticated reading state for the continuous reader.

Content lives in ``data/database.db``. This database contains only user-owned
state and accepted mutation history; content IDs are checked by route-level
validation before they reach these projection methods.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


VALID_MODES = {'summary', 'original', 'plain', 'side_by_side'}
VALID_CAUSES = {
    'page_turn', 'mode_exit', 'toc', 'hidden', 'pagehide', 'navigation',
    'completion', 'manual_unfinish',
}


class UserDatabase:
    """SQLite persistence for current/furthest markers and mutations."""

    def __init__(self, db_path: Path = None):
        if db_path is None:
            try:
                from . import config
            except ImportError:
                from backend import config
            db_path = config.USER_DATABASE_PATH
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        return conn

    def init_db(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            self._migrate_password_schema(cursor)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    subject TEXT UNIQUE,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS book_reading_state (
                    user_id INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    last_mode TEXT CHECK(last_mode IN ('summary', 'original', 'plain', 'side_by_side')),
                    status TEXT NOT NULL DEFAULT 'preview'
                        CHECK(status IN ('preview', 'in_progress', 'finished')),
                    meaningfully_started_at TIMESTAMP,
                    last_meaningful_read_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    completion_revision INTEGER,
                    manual_unfinished_at TIMESTAMP,
                    revision INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, book_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mode_reading_state (
                    user_id INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    mode TEXT NOT NULL CHECK(mode IN ('summary', 'original', 'plain', 'side_by_side')),
                    content_version INTEGER NOT NULL,
                    current_chapter_id INTEGER NOT NULL,
                    current_paragraph_id TEXT NOT NULL,
                    current_offset REAL NOT NULL CHECK(current_offset >= 0 AND current_offset <= 1),
                    current_quote TEXT,
                    current_ordinal INTEGER NOT NULL,
                    current_word_position INTEGER NOT NULL,
                    current_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    furthest_chapter_id INTEGER,
                    furthest_paragraph_id TEXT,
                    furthest_offset REAL,
                    furthest_quote TEXT,
                    furthest_ordinal INTEGER,
                    furthest_word_position INTEGER,
                    furthest_updated_at TIMESTAMP,
                    active_reading_seconds INTEGER NOT NULL DEFAULT 0,
                    sequential_boundary_count INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 0,
                    last_device_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, book_id, mode),
                    FOREIGN KEY (user_id, book_id)
                        REFERENCES book_reading_state(user_id, book_id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS progress_mutation (
                    mutation_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    device_id TEXT NOT NULL,
                    device_sequence INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    mode TEXT CHECK(mode IN ('summary', 'original', 'plain', 'side_by_side')),
                    event_cause TEXT NOT NULL,
                    content_version INTEGER,
                    current_marker TEXT,
                    qualified_furthest_marker TEXT,
                    active_seconds_delta INTEGER NOT NULL DEFAULT 0,
                    sequential_boundaries_delta INTEGER NOT NULL DEFAULT 0,
                    completion_transition TEXT,
                    base_revision INTEGER,
                    accepted_revision INTEGER,
                    result TEXT NOT NULL CHECK(result IN ('accepted', 'duplicate', 'conflict', 'rejected')),
                    recovery_level TEXT,
                    client_occurred_at TIMESTAMP,
                    server_received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, device_id, device_sequence)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_book_reading_library
                ON book_reading_state(user_id, status, last_meaningful_read_at DESC)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_progress_mutation_user_book
                ON progress_mutation(user_id, book_id, server_received_at DESC)
            ''')
            conn.commit()
        finally:
            conn.close()

    def _migrate_password_schema(self, cursor: sqlite3.Cursor) -> None:
        columns = {row[1] for row in cursor.execute('PRAGMA table_info(users)').fetchall()}
        if not columns or 'email' in columns:
            return
        row_count = cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if row_count:
            raise RuntimeError('refusing to replace a non-empty legacy users table')
        cursor.execute('DROP TABLE users')

    def upsert_user_by_email(self, email: str) -> int:
        email = email.strip().lower()
        conn = self.get_connection()
        try:
            with conn:
                conn.execute('''
                    INSERT INTO users (email, last_login) VALUES (?, CURRENT_TIMESTAMP)
                    ON CONFLICT(email) DO UPDATE SET last_login = CURRENT_TIMESTAMP
                ''', (email,))
            return conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()['id']
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            row = conn.execute('''
                SELECT id, email, created_at, last_login FROM users WHERE id = ?
            ''', (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _marker_from_row(row: sqlite3.Row, prefix: str) -> Optional[Dict]:
        paragraph_id = row[f'{prefix}_paragraph_id']
        if paragraph_id is None:
            return None
        return {
            'content_version': row['content_version'],
            'chapter_id': row[f'{prefix}_chapter_id'],
            'paragraph_id': paragraph_id,
            'offset': row[f'{prefix}_offset'],
            'quote': row[f'{prefix}_quote'],
            'ordinal': row[f'{prefix}_ordinal'],
            'word_position': row[f'{prefix}_word_position'],
        }

    def _mode_projection(self, row: sqlite3.Row) -> Dict:
        result = dict(row)
        result['current_marker'] = self._marker_from_row(row, 'current')
        result['furthest_marker'] = self._marker_from_row(row, 'furthest')
        for prefix in ('current', 'furthest'):
            for suffix in ('chapter_id', 'paragraph_id', 'offset', 'quote', 'ordinal', 'word_position'):
                result.pop(f'{prefix}_{suffix}', None)
        return result

    def _get_book_projection_in_connection(self, conn, user_id: int, book_id: int) -> Dict:
        book = conn.execute('''
            SELECT * FROM book_reading_state WHERE user_id = ? AND book_id = ?
        ''', (user_id, book_id)).fetchone()
        modes = conn.execute('''
            SELECT * FROM mode_reading_state WHERE user_id = ? AND book_id = ?
            ORDER BY CASE mode WHEN 'summary' THEN 1 WHEN 'original' THEN 2 WHEN 'plain' THEN 3 ELSE 4 END
        ''', (user_id, book_id)).fetchall()
        return {'book': dict(book) if book else None, 'modes': [self._mode_projection(row) for row in modes]}

    def get_book_projection(self, user_id: int, book_id: int) -> Dict:
        conn = self.get_connection()
        try:
            return self._get_book_projection_in_connection(conn, user_id, book_id)
        finally:
            conn.close()

    def get_library_projection(self, user_id: int) -> List[Dict]:
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                SELECT * FROM book_reading_state
                WHERE user_id = ? AND status IN ('in_progress', 'finished')
                ORDER BY
                    CASE status WHEN 'in_progress' THEN 0 ELSE 1 END,
                    CASE WHEN status = 'in_progress' THEN last_meaningful_read_at END DESC,
                    CASE WHEN status = 'finished' THEN finished_at END DESC
            ''', (user_id,)).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                mode = conn.execute('''
                    SELECT * FROM mode_reading_state
                    WHERE user_id = ? AND book_id = ? AND mode = ?
                ''', (user_id, item['book_id'], item['last_mode'])).fetchone()
                item['last_mode_state'] = self._mode_projection(mode) if mode else None
                result.append(item)
            return result
        finally:
            conn.close()

    @staticmethod
    def _marker_values(marker: Optional[Dict]):
        if not marker:
            return (None, None, None, None, None, None)
        return (
            marker['chapter_id'], marker['paragraph_id'], marker['offset'], marker.get('quote'),
            marker['ordinal'], marker['word_position'],
        )

    def _insert_mutation(
        self, conn, user_id, payload, current_marker, furthest_marker, result, accepted_revision,
        active_delta, boundary_delta, completion_transition=None,
    ):
        conn.execute('''
            INSERT INTO progress_mutation (
                mutation_id, user_id, device_id, device_sequence, book_id, mode, event_cause,
                content_version, current_marker, qualified_furthest_marker, active_seconds_delta,
                sequential_boundaries_delta, completion_transition, base_revision, accepted_revision,
                result, recovery_level, client_occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            payload['mutation_id'], user_id, payload['device_id'], int(payload['device_sequence']),
            payload['book_id'], payload.get('mode'), payload['event_cause'], current_marker['content_version'],
            json.dumps(current_marker), json.dumps(furthest_marker) if furthest_marker else None,
            active_delta, boundary_delta, completion_transition, payload.get('base_revision'),
            accepted_revision, result, payload.get('recovery_level'), payload.get('client_occurred_at'),
        ))

    def apply_mutation(
        self,
        user_id: int,
        payload: Dict[str, Any],
        current_marker: Optional[Dict],
        furthest_marker: Optional[Dict],
        completion_allowed: bool = False,
    ) -> Dict:
        """Apply one already-validated mutation and return its projection."""
        mutation_id = str(payload.get('mutation_id') or '')
        device_id = str(payload.get('device_id') or '')
        mode = payload.get('mode')
        cause = payload.get('event_cause')
        book_id = payload.get('book_id')
        if not mutation_id or not device_id or mode not in VALID_MODES or cause not in VALID_CAUSES:
            raise ValueError('invalid mutation identity, mode, or cause')
        if not isinstance(book_id, int):
            raise ValueError('book_id is required')
        try:
            device_sequence = int(payload.get('device_sequence'))
            base_revision = int(payload.get('base_revision') or 0)
        except (TypeError, ValueError):
            raise ValueError('device_sequence and base_revision must be integers')
        if device_sequence < 1 or not current_marker:
            raise ValueError('a valid current marker is required')

        active_delta = max(0, min(int(payload.get('active_seconds_delta') or 0), 60))
        boundary_delta = max(0, min(int(payload.get('sequential_boundaries_delta') or 0), 10))

        conn = self.get_connection()
        try:
            with conn:
                duplicate = conn.execute('SELECT 1 FROM progress_mutation WHERE mutation_id = ?', (mutation_id,)).fetchone()
                if duplicate:
                    return {'result': 'duplicate', 'projection': self._get_book_projection_in_connection(conn, user_id, book_id)}

                existing = conn.execute('''
                    SELECT * FROM mode_reading_state WHERE user_id = ? AND book_id = ? AND mode = ?
                ''', (user_id, book_id, mode)).fetchone()
                if existing and base_revision != existing['revision']:
                    self._insert_mutation(conn, user_id, payload, current_marker, furthest_marker,
                                          'conflict', None, active_delta, boundary_delta)
                    return {
                        'result': 'conflict',
                        'projection': self._get_book_projection_in_connection(conn, user_id, book_id),
                        'local_candidate': current_marker,
                    }

                book = conn.execute('''
                    SELECT * FROM book_reading_state WHERE user_id = ? AND book_id = ?
                ''', (user_id, book_id)).fetchone()
                if not book:
                    conn.execute('''
                        INSERT INTO book_reading_state (user_id, book_id, last_mode) VALUES (?, ?, ?)
                    ''', (user_id, book_id, mode))
                    book = conn.execute('''
                        SELECT * FROM book_reading_state WHERE user_id = ? AND book_id = ?
                    ''', (user_id, book_id)).fetchone()

                accepted_furthest = furthest_marker
                if accepted_furthest and existing and existing['furthest_word_position'] is not None:
                    if accepted_furthest['word_position'] < existing['furthest_word_position']:
                        accepted_furthest = None
                if not accepted_furthest and existing and existing['furthest_paragraph_id']:
                    accepted_furthest = self._marker_from_row(existing, 'furthest')

                mode_revision = (existing['revision'] if existing else 0) + 1
                if existing:
                    conn.execute('''
                        UPDATE mode_reading_state SET
                            content_version = ?, current_chapter_id = ?, current_paragraph_id = ?, current_offset = ?,
                            current_quote = ?, current_ordinal = ?, current_word_position = ?, current_updated_at = CURRENT_TIMESTAMP,
                            furthest_chapter_id = ?, furthest_paragraph_id = ?, furthest_offset = ?, furthest_quote = ?,
                            furthest_ordinal = ?, furthest_word_position = ?,
                            furthest_updated_at = CASE WHEN ? IS NULL THEN furthest_updated_at ELSE CURRENT_TIMESTAMP END,
                            active_reading_seconds = active_reading_seconds + ?,
                            sequential_boundary_count = sequential_boundary_count + ?, revision = ?, last_device_id = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND book_id = ? AND mode = ?
                    ''', (
                        current_marker['content_version'], current_marker['chapter_id'], current_marker['paragraph_id'],
                        current_marker['offset'], current_marker.get('quote'), current_marker['ordinal'], current_marker['word_position'],
                        *self._marker_values(accepted_furthest),
                        accepted_furthest['paragraph_id'] if accepted_furthest else None,
                        active_delta, boundary_delta, mode_revision, device_id, user_id, book_id, mode,
                    ))
                else:
                    conn.execute('''
                        INSERT INTO mode_reading_state (
                            user_id, book_id, mode, content_version, current_chapter_id, current_paragraph_id,
                            current_offset, current_quote, current_ordinal, current_word_position,
                            furthest_chapter_id, furthest_paragraph_id, furthest_offset, furthest_quote,
                            furthest_ordinal, furthest_word_position, furthest_updated_at,
                            active_reading_seconds, sequential_boundary_count, revision, last_device_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  CASE WHEN ? IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END, ?, ?, ?, ?)
                    ''', (
                        user_id, book_id, mode, current_marker['content_version'], current_marker['chapter_id'],
                        current_marker['paragraph_id'], current_marker['offset'], current_marker.get('quote'),
                        current_marker['ordinal'], current_marker['word_position'], *self._marker_values(accepted_furthest),
                        accepted_furthest['paragraph_id'] if accepted_furthest else None,
                        active_delta, boundary_delta, mode_revision, device_id,
                    ))

                new_mode = conn.execute('''
                    SELECT * FROM mode_reading_state WHERE user_id = ? AND book_id = ? AND mode = ?
                ''', (user_id, book_id, mode)).fetchone()
                meaningful = bool(book['meaningfully_started_at']) or (
                    new_mode['sequential_boundary_count'] >= 2 or
                    (new_mode['active_reading_seconds'] >= 60 and new_mode['current_ordinal'] > 0)
                )
                transition = None
                if cause == 'manual_unfinish':
                    status, transition = 'in_progress', 'unfinished'
                elif completion_allowed and cause == 'completion':
                    status, transition = 'finished', 'finished'
                elif book['status'] == 'finished':
                    status = 'finished'
                elif meaningful:
                    status = 'in_progress'
                else:
                    status = book['status']

                book_revision = book['revision'] + 1
                conn.execute('''
                    UPDATE book_reading_state SET
                        last_mode = ?, status = ?,
                        meaningfully_started_at = CASE WHEN meaningfully_started_at IS NULL AND ? THEN CURRENT_TIMESTAMP ELSE meaningfully_started_at END,
                        last_meaningful_read_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE last_meaningful_read_at END,
                        finished_at = CASE WHEN ? = 'finished' THEN COALESCE(finished_at, CURRENT_TIMESTAMP)
                                           WHEN ? = 'unfinished' THEN NULL ELSE finished_at END,
                        completion_revision = CASE WHEN ? IS NOT NULL THEN ? ELSE completion_revision END,
                        manual_unfinished_at = CASE WHEN ? = 'unfinished' THEN CURRENT_TIMESTAMP ELSE manual_unfinished_at END,
                        revision = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND book_id = ?
                ''', (
                    mode, status, int(meaningful), int(meaningful), transition, transition,
                    transition, book_revision, transition, book_revision, user_id, book_id,
                ))
                self._insert_mutation(conn, user_id, payload, current_marker, accepted_furthest,
                                      'accepted', book_revision, active_delta, boundary_delta, transition)
                return {'result': 'accepted', 'projection': self._get_book_projection_in_connection(conn, user_id, book_id)}
        finally:
            conn.close()
