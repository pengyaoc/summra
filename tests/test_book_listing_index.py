"""Listing queries must not touch the books rows themselves.

Each books row stores the whole book (`full_text`) before columns such as
gutenberg_id, slug and cefr_level, so reading those columns from the table
walks the book text's overflow pages. On the small prod VM, with the
database mostly on disk, that made the home page take 6–10 s and the
every-page level counts stall chapter pages too. A covering index holds
every column these queries need, so SQLite answers them from the index.
"""
import sqlite3

from backend import models
from backend.routes import common, pages


def _plans_for(db, call):
    """Run `call` and return the query plan of every SELECT it ran on books."""
    statements = []
    original = db.get_connection

    def traced():
        conn = original()
        conn.set_trace_callback(statements.append)
        return conn

    db.get_connection = traced
    try:
        call()
    finally:
        db.get_connection = original
    conn = sqlite3.connect(db.db_path)
    plans = {}
    for sql in statements:
        if sql.lstrip().upper().startswith('SELECT') and ' books' in sql and 'book_categories' not in sql:
            plans[sql] = ' | '.join(row[-1] for row in conn.execute(f'EXPLAIN QUERY PLAN {sql}'))
    conn.close()
    return plans


def test_listing_queries_are_answered_from_a_covering_index(test_db_path, monkeypatch):
    db = models.Database(db_path=test_db_path)
    monkeypatch.setattr(common, 'db', db)
    for call in (db.get_all_books, pages._top_10_books):
        plans = _plans_for(db, call)
        assert plans, f'{call.__name__} ran no books query?'
        for sql, plan in plans.items():
            assert 'COVERING INDEX' in plan, f'{call.__name__}: {sql!r} → {plan}'
