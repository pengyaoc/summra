"""Shared database-path helper for one-off scripts.

Before this, 13+ scripts each hardcoded their own DB_PATH — some via
`Path(__file__).parent.parent.parent / 'data' / 'database.db'` (breaks if
the script moves one directory level deeper or shallower), some via the
bare relative string `'data/database.db'` (only works if the script is run
from the repo root). All of them duplicated what backend/config.py already
gets right. Use this instead:

    from backend import config
    from scripts.lib.db import get_connection

    DB_PATH = config.DATABASE_PATH   # keep this module-level name — tests
                                      # patch.object(this_module, "DB_PATH", ...)
                                      # to point at a temp test DB
    ...
    conn = get_connection(DB_PATH)
"""
import sqlite3

from backend import config


def get_connection(db_path=None) -> sqlite3.Connection:
    """A sqlite3 connection with row_factory set so rows support both index
    and column-name access — matching backend/models.py's
    Database.get_connection().

    db_path defaults to config.DATABASE_PATH. Callers should still keep
    their own module-level `DB_PATH = config.DATABASE_PATH` and pass it
    explicitly (`get_connection(DB_PATH)`), rather than relying on this
    default — tests commonly monkeypatch a script's own `DB_PATH` module
    attribute to point at a temp database, which only works if the
    connection call site reads that attribute at call time.
    """
    conn = sqlite3.connect(db_path if db_path is not None else config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn
