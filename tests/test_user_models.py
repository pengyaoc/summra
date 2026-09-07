"""Tests for the email-keyed user model (consolidated login, 2026-09-05).

Replaces the old username/password schema — see WORK_LOG.md and
pchauth's spec, docs/superpowers/specs/2026-09-05-consolidated-login-design.md.
"""
from backend.user_models import UserDatabase


def _marker(ordinal=0, paragraph_id=None):
    return {
        "content_version": 1,
        "chapter_id": 10,
        "paragraph_id": paragraph_id or f"paragraph-{ordinal}",
        "offset": 0,
        "quote": f"paragraph {ordinal}",
        "ordinal": ordinal,
        "word_position": ordinal * 10,
    }


def _mutation(sequence, *, cause="page_turn", base_revision=0, boundaries=0, active_seconds=0):
    return {
        "mutation_id": f"mutation-{sequence}", "device_id": "device-a", "device_sequence": sequence,
        "book_id": 7, "mode": "original", "event_cause": cause, "base_revision": base_revision,
        "sequential_boundaries_delta": boundaries, "active_seconds_delta": active_seconds,
    }


def test_upsert_by_email_creates_new_user(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    user_id = db.upsert_user_by_email("me@example.com")
    assert isinstance(user_id, int)


def test_upsert_by_email_is_idempotent(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    first_id = db.upsert_user_by_email("me@example.com")
    second_id = db.upsert_user_by_email("me@example.com")
    assert first_id == second_id


def test_upsert_by_email_is_case_insensitive(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    first_id = db.upsert_user_by_email("Me@Example.com")
    second_id = db.upsert_user_by_email("me@example.com")
    assert first_id == second_id


def test_schema_has_no_password_columns(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    conn = db.get_connection()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    conn.close()
    assert "password_hash" not in columns
    assert "salt" not in columns
    assert "email" in columns
    assert "subject" in columns
    assert "name" in columns


def test_get_user_by_id_returns_email(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    user_id = db.upsert_user_by_email("me@example.com")
    user = db.get_user_by_id(user_id)
    assert user["email"] == "me@example.com"


def test_get_user_by_id_returns_none_for_unknown_id(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    assert db.get_user_by_id(999) is None


def test_migrates_an_existing_old_schema_empty_table(test_db_path):
    import sqlite3

    conn = sqlite3.connect(test_db_path)
    conn.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

    db = UserDatabase(db_path=test_db_path)
    user_id = db.upsert_user_by_email("me@example.com")
    assert isinstance(user_id, int)


def test_refuses_to_migrate_a_non_empty_old_schema_table(test_db_path):
    import sqlite3

    conn = sqlite3.connect(test_db_path)
    conn.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    conn.execute(
        "INSERT INTO users (username, password_hash, salt) VALUES ('x', 'y', 'z')"
    )
    conn.commit()
    conn.close()

    import pytest
    with pytest.raises(RuntimeError, match="non-empty"):
        UserDatabase(db_path=test_db_path)


def test_progress_requires_sequential_meaningful_engagement(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    user_id = db.upsert_user_by_email("reader@example.com")
    first = db.apply_mutation(user_id, _mutation(1), _marker(0), None)
    second = db.apply_mutation(user_id, _mutation(2, base_revision=1, boundaries=1), _marker(1), _marker(1))
    third = db.apply_mutation(user_id, _mutation(3, base_revision=2, boundaries=1), _marker(2), _marker(2))
    assert first["projection"]["book"]["status"] == "preview"
    assert second["projection"]["book"]["status"] == "preview"
    assert third["projection"]["book"]["status"] == "in_progress"
    assert len(db.get_library_projection(user_id)) == 1


def test_progress_mutation_is_idempotent_and_conflicts_keep_projection(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    user_id = db.upsert_user_by_email("reader@example.com")
    accepted = db.apply_mutation(user_id, _mutation(1), _marker(0), None)
    duplicate = db.apply_mutation(user_id, _mutation(1), _marker(0), None)
    conflict = db.apply_mutation(user_id, _mutation(2, base_revision=0), _marker(4), _marker(4))
    assert accepted["result"] == "accepted"
    assert duplicate["result"] == "duplicate"
    assert conflict["result"] == "conflict"
    assert conflict["projection"]["modes"][0]["current_marker"]["ordinal"] == 0


def test_completion_and_manual_unfinish_preserve_mode_marker(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    user_id = db.upsert_user_by_email("reader@example.com")
    completed = db.apply_mutation(
        user_id, _mutation(1, cause="completion"), _marker(9), _marker(9), completion_allowed=True,
    )
    unfinished = db.apply_mutation(
        user_id, _mutation(2, cause="manual_unfinish", base_revision=1), _marker(9), None,
    )
    assert completed["projection"]["book"]["status"] == "finished"
    assert unfinished["projection"]["book"]["status"] == "in_progress"
    assert unfinished["projection"]["modes"][0]["current_marker"]["paragraph_id"] == "paragraph-9"
