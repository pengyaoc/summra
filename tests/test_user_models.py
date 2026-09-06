"""Tests for the email-keyed user model (consolidated login, 2026-09-05).

Replaces the old username/password schema — see WORK_LOG.md and
pchauth's spec, docs/superpowers/specs/2026-09-05-consolidated-login-design.md.
"""
from backend.user_models import UserDatabase


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
