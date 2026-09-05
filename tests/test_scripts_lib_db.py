"""Tests for scripts/lib/db.py — the shared DB-connection helper that
replaces 13+ scripts' individually hardcoded DB_PATH constants.
"""
import sqlite3

from backend import config
from scripts.lib.db import get_connection


def test_get_connection_points_at_config_database_path():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA database_list")
        row = cursor.fetchone()
        # PRAGMA database_list's 'file' column is the absolute path sqlite
        # actually opened — must match config.DATABASE_PATH exactly, not
        # some other hardcoded relative path a caller happened to resolve to.
        assert row['file'] == str(config.DATABASE_PATH)
    finally:
        conn.close()


def test_get_connection_has_row_factory_set():
    """Rows must support both index and column-name access (sqlite3.Row),
    matching backend/models.py's Database.get_connection() convention —
    a strict superset of plain-tuple access, so this is backward compatible
    with any script that only ever did positional (row[0]) access."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM books LIMIT 1")
        row = cursor.fetchone()
        if row is not None:
            assert row['id'] == row[0]
            assert row['title'] == row[1]
    finally:
        conn.close()


def test_get_connection_returns_a_working_sqlite_connection():
    conn = get_connection()
    try:
        assert isinstance(conn, sqlite3.Connection)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM books")
        count = cursor.fetchone()[0]
        assert count >= 0
    finally:
        conn.close()


def test_get_connection_honors_explicit_db_path_override(test_db_path):
    """Callers pass their own module-level DB_PATH explicitly
    (get_connection(DB_PATH)) rather than relying on the config default —
    this is what makes `patch.object(some_script, "DB_PATH", tmp_path)`
    (the pattern several scripts' tests already use) actually take effect.
    A bare get_connection() ignoring an explicit path would silently
    reconnect to the real production database instead of a test's temp one.
    """
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(test_db_path)
    conn.execute("CREATE TABLE marker (id INTEGER)")
    conn.commit()
    conn.close()

    conn = get_connection(test_db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row['name'] for row in cursor.fetchall()}
        assert 'marker' in tables
        assert 'books' not in tables, "connected to the real DB instead of the override path"
    finally:
        conn.close()
