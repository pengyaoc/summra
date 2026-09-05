"""
Deployment-config regressions from the wordpress-2-vm service hardening work.

These guard properties required for the systemd ProtectSystem=strict sandbox:
all mutable state must resolve under data/, not the repo root, and the
gunicorn bind address/thread count must be overridable via environment
variables rather than hardcoded, so one committed gunicorn_config.py works
both standalone (port 5000) and cohosted (port 5001).
"""
import importlib
import os
from pathlib import Path

import pytest


def test_user_database_path_resolves_under_data_dir():
    """UserDatabase's default path must live under data/, matching
    DATABASE_PATH's convention, so it stays writable when the repo root
    becomes read-only under systemd's ProtectSystem=strict."""
    from backend import config

    assert hasattr(config, "USER_DATABASE_PATH"), (
        "config.py must define USER_DATABASE_PATH so user_models.UserDatabase() "
        "doesn't default to a path in the repo root (summra.db), which breaks "
        "under ProtectSystem=strict since SQLite needs to write -wal/-shm "
        "siblings into that same directory."
    )
    assert config.USER_DATABASE_PATH.parent.name == "data"
    assert config.USER_DATABASE_PATH.name == "summra.db"


def test_user_database_uses_configured_path():
    """app_base.py's UserDatabase() call site must pass config.USER_DATABASE_PATH
    explicitly rather than relying on the class's repo-root default."""
    from backend.user_models import UserDatabase

    db = UserDatabase.__init__
    # Inspect app_base's actual call site behavior by importing it fresh and
    # checking the resulting user_db.db_path, not just the class default.
    from backend import config

    # `from backend import app_base` risks returning a stale cached
    # attribute rather than the module in sys.modules if another test popped
    # it; import_module always resolves the real sys.modules entry.
    app_base = importlib.import_module("backend.app_base")

    assert app_base.user_db.db_path == config.USER_DATABASE_PATH, (
        f"app_base.user_db.db_path is {app_base.user_db.db_path!r}, expected "
        f"{config.USER_DATABASE_PATH!r} — the UserDatabase() call site in "
        "app_base.py must pass config.USER_DATABASE_PATH explicitly."
    )


def test_user_database_class_default_matches_configured_path():
    """UserDatabase()'s own default (used by any caller that doesn't pass a
    path explicitly — e.g. a script or a future test) must match
    config.USER_DATABASE_PATH (data/summra.db), not fall back to a repo-root
    summra.db. app_base.py's call site already passes the path explicitly
    (see test_user_database_uses_configured_path above), but the class
    default was never fixed to match, so any other caller still creates a
    stray repo-root summra.db."""
    from backend import config
    from backend.user_models import UserDatabase

    db = UserDatabase()
    assert db.db_path == config.USER_DATABASE_PATH, (
        f"UserDatabase()'s default db_path is {db.db_path!r}, expected "
        f"{config.USER_DATABASE_PATH!r} — the class default in "
        "user_models.py must use config.USER_DATABASE_PATH."
    )


def test_gunicorn_bind_defaults_to_5000_when_unset():
    """Standalone deploys (no GUNICORN_BIND set) must keep binding :5000."""
    env = {k: v for k, v in os.environ.items() if k != "GUNICORN_BIND"}
    _run_gunicorn_config_module(env)
    assert _last_module_globals["bind"] == "127.0.0.1:5000"


def test_gunicorn_bind_honours_env_override():
    """Cohosted deploys set GUNICORN_BIND to avoid a --bind CLI override
    baked into the systemd unit's ExecStart."""
    env = {**os.environ, "GUNICORN_BIND": "127.0.0.1:5001"}
    _run_gunicorn_config_module(env)
    assert _last_module_globals["bind"] == "127.0.0.1:5001"


def test_gunicorn_worker_class_is_gthread_not_gevent():
    """gevent has no py3.13 wheel for its pinned version and forced an
    unpinned workaround on the VM; gthread is stdlib-only and needs none."""
    _run_gunicorn_config_module(dict(os.environ))
    assert _last_module_globals["worker_class"] == "gthread"


def test_gunicorn_threads_defaults_to_4_and_honours_env_override():
    _run_gunicorn_config_module({k: v for k, v in os.environ.items() if k != "GUNICORN_THREADS"})
    assert _last_module_globals["threads"] == 4

    env = {**os.environ, "GUNICORN_THREADS": "8"}
    _run_gunicorn_config_module(env)
    assert _last_module_globals["threads"] == 8


_last_module_globals = {}


def _run_gunicorn_config_module(env):
    """gunicorn_config.py is a plain script (no functions to import), read at
    startup by the gunicorn CLI — so exec it fresh under a patched os.environ
    each time rather than importing (import would cache module-level values
    across test cases)."""
    global _last_module_globals
    config_path = Path(__file__).parent.parent / "deploy" / "gunicorn_config.py"
    source = config_path.read_text()
    old_environ = os.environ.copy()
    os.environ.clear()
    os.environ.update(env)
    try:
        module_globals = {"__name__": "gunicorn_config", "__file__": str(config_path)}
        exec(compile(source, str(config_path), "exec"), module_globals)
        _last_module_globals = module_globals
    finally:
        os.environ.clear()
        os.environ.update(old_environ)
