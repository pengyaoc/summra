# Distill Phase 1 — Repo Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the repo into `shared/`, `plainly/` and `distill/` so Distill can be built on shared auth, progress, reader-index and web plumbing, with Plainly behaving exactly as before.

**Architecture:** Extract the code both apps need into a new top-level `shared` Python package, with no import back into either app (enforced by a test). Rename the `backend` package to `plainly`, and move `frontend/` and `scripts/` under it. The reader index becomes a mixin with three hook methods, which Plainly's `Database` implements today and Distill's will implement in phase 3. Frontend assets (reader JS, Kindle templates/CSS/JS) stay in Plainly for now. The owner requires the web reader to be heavily shared, not forked. So the Distill web-app plan (phase 3) opens by extracting the common reader components into `shared/` and switching Plainly onto them, before any Distill reader code is written (spec §5.7). Deploying the renamed layout to the VM is the last task.

**Tech Stack:** Python 3.11, Flask, SQLite, pytest, Playwright e2e harness (`tests/e2e/*.mjs`), esbuild, Apache + systemd user unit on the VM.

**Spec:** `docs/superpowers/specs/2026-10-24-distill-design.md` (§5.1 and §5.9 phase 1). This is plan 1 of 6. Plans for phases 2–6 are written after this one lands, against the real module names.

## Global Constraints

- Plainly must be unchanged in behaviour, URLs and data. No test may be edited to make it pass, except the one replacement called out in Task 2, which needs the owner's OK.
- `shared/` must never import `plainly`, `distill`, `backend` or `scripts`.
- No compatibility shims or re-export modules at old paths. Every import is updated to the new path in the same task.
- Runtime data stays in top-level `data/` (`data/database.db`, `data/summra.db`). File names and locations don't change.
- Env var names (`SUMMRA_*`, `FEATURE_*`, `GUNICORN_*`) don't change.
- The repo is public. Nothing under `data/` is committed.
- Each task ends with the full suite green: `venv/bin/pytest tests/ -q`, with a pass count ≥ the Task 1 baseline. Each task's commit message records the count.
- Deploying to production (Task 7) needs the owner's go-ahead in chat right before it runs.

## Review Focus

1. **Gunicorn entry point after the rename.** The VM's unit runs `backend.app_prod:app`. A missed rename means production fails to start. Task 7 changes the unit and checks `is-active` plus HTTP 200 before Apache is touched.
2. **Static files after `frontend/` moves.** Apache's `Alias ${SUMMRA_PREFIX}/static/` points at `/opt/summra/frontend/static/`. Covers and illustrations would 404 while pages still return 200. Task 6 adds a test that the repo's Apache fragment and `config.COVERS_DIR` point at the same directory. Task 7 curls a real cover image.
3. **Paths computed from `__file__` in moved scripts.** `scripts/**` that compute the repo root with `Path(__file__).parents[N]` silently point one level off after moving under `plainly/`. Task 6 adds a test asserting `plainly.config.BASE_DIR` is the repo root, and greps every `__file__` use in the moved scripts.
4. **String-based patch targets in tests.** `patch('backend.config.X')` and `monkeypatch.setattr('backend....')` aren't import statements, so a find-replace over imports misses them, and a test can pass while patching nothing. Task 5's sweep covers every `backend.` string. Task 5 also adds a guard test that no `.py` or `.mjs` file still contains `backend.` or `from backend`.
5. **Saved reading positions across the reader-index move.** If the extracted mixin computes a different `source_checksum`, every book recompiles to a new version. Saved places then fall back to quote recovery. Task 4 pins the checksum for a fixture book before and after the move.

---

### Task 1: Baseline and `shared` package skeleton with a layering guard

**Files:**
- Create: `shared/__init__.py`, `distill/__init__.py` (empty docstring modules)
- Create: `tests/shared/__init__.py`, `tests/shared/test_layering.py`
- Modify: `pyproject.toml` (`[tool.setuptools.packages.find] include`)

**Interfaces:**
- Produces: importable packages `shared`, `distill`, and the guard test `tests/shared/test_layering.py`, which later tasks keep green.

- [ ] **Step 1: Record the baseline.** Run `venv/bin/pytest tests/ -q | tail -3`. Then, with Flask running (`python backend/app.py`), run `cd tests/e2e && node smoke.mjs && node kindle_mode.mjs`. Write the pass count and e2e results into the `WORK_LOG.md` Distill entry. Expected: all green (current count was 816 on 2026-10-19).
- [ ] **Step 2: Write the failing guard test.**

```python
# tests/shared/test_layering.py
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ('plainly', 'distill', 'backend', 'scripts')

def _imports(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module

def test_shared_package_exists():
    assert (ROOT / 'shared' / '__init__.py').is_file()

def test_shared_imports_no_app_code():
    bad = [(str(p.relative_to(ROOT)), m) for p in (ROOT / 'shared').rglob('*.py')
           for m in _imports(p) if m.split('.')[0] in FORBIDDEN]
    assert bad == []
```

- [ ] **Step 3: Run it to verify it fails.** Run `venv/bin/pytest tests/shared/test_layering.py -v`. Expected: `test_shared_package_exists` FAILS (no `shared/`).
- [ ] **Step 4: Create the packages.** Create `shared/__init__.py` and `distill/__init__.py`. Set the pyproject include to `["backend*", "scripts*", "shared*", "distill*"]`. Run `venv/bin/pip install -e .`.
- [ ] **Step 5: Run the guard and full suite.** `venv/bin/pytest tests/ -q`. Expected: baseline + 2 passed.
- [ ] **Step 6: Commit.** `git add shared distill tests/shared pyproject.toml WORK_LOG.md && git commit -m "Add shared/distill package skeleton and layering guard"`

### Task 2: `shared.auth` — pchauth, user state, whoami

**Files:**
- Move (`git mv`): `backend/pchauth/` → `shared/auth/pchauth/`, `backend/user_models.py` → `shared/auth/user_models.py`, `backend/whoami.py` → `shared/auth/whoami.py`
- Create: `shared/auth/__init__.py`
- Modify: `backend/app_base.py`, `backend/progress_routes.py`, `backend/routes/kindle.py`, every test or script importing those modules (find with `grep -rlE "pchauth|user_models|whoami" --include='*.py' .`, excluding `venv`)
- Test: `tests/shared/test_auth_package.py`. Move `tests/test_user_models.py`, `tests/test_user_hints.py`, `tests/test_pchauth_integration.py` into `tests/shared/`.

**Interfaces:**
- Produces:
  - `shared.auth.user_models.UserDatabase(db_path: Path, valid_hints: frozenset[str] = frozenset())`. `db_path` is now required, and `self.valid_hints` holds the hints the app accepts.
  - `shared.auth.user_models.VALID_MODES` and `VALID_CAUSES` are unchanged.
  - `shared.auth.pchauth.flask_adapter.init_pchauth` and `login_required` are unchanged.
  - `shared.auth.whoami.whoami_bp` and `whoami.user_db` are unchanged.
- Plainly keeps its hint names: `backend/config.py` gains `READER_HINTS = frozenset({'reader_swipe_mobile', 'reader_nav_desktop'})`, and `app_base` passes it in.

- [ ] **Step 1: Write the failing test.**

```python
# tests/shared/test_auth_package.py
import pytest
from shared.auth.user_models import UserDatabase

def test_user_database_requires_explicit_path():
    with pytest.raises(TypeError):
        UserDatabase()

def test_hints_are_supplied_by_the_app(tmp_path):
    db = UserDatabase(tmp_path / 'u.db', valid_hints=frozenset({'a'}))
    assert db.valid_hints == frozenset({'a'})
```

- [ ] **Step 2: Run it to verify it fails.** `venv/bin/pytest tests/shared/test_auth_package.py -v`. Expected: FAIL with `ModuleNotFoundError: shared.auth`.
- [ ] **Step 3: Move the modules and rewrite the imports.**
  - Drop the `try/except ImportError` relative-import fallbacks in the moved files, using absolute `shared.auth...` imports.
  - Remove `UserDatabase`'s config fallback.
  - Remove `VALID_HINTS` from `shared`. `progress_routes` checks `user_db.valid_hints` instead.
  - Update every `UserDatabase(` call site to pass a path. In Plainly that's `config.USER_DATABASE_PATH`.
- [ ] **Step 4: Replace the class-default test (owner OK needed).** `tests/test_deploy_config.py::test_user_database_class_default_matches_configured_path` asserts the old default, which this task removes on purpose (shared code can't know Plainly's path). Replace its body with the `TypeError` assertion above, keeping `test_user_database_uses_configured_path` as is. Record the replacement in the commit message and `WORK_LOG.md`. **The owner approves this before execution starts.**
- [ ] **Step 5: Run the full suite.** `venv/bin/pytest tests/ -q`. Expected: ≥ baseline, all pass, layering guard green.
- [ ] **Step 6: Commit.** `git commit -m "Move pchauth, user state and whoami into shared.auth"`

### Task 3: `shared.progress` — progress and library routes

**Files:**
- Move: `backend/progress_routes.py` → `shared/progress/routes.py`
- Create: `shared/progress/__init__.py`
- Modify: `backend/app_base.py`, `backend/routes/kindle.py`, `backend/routes/pages.py`, and the tests importing `progress_routes`

**Interfaces:**
- Consumes: `shared.auth.user_models.UserDatabase`, `shared.auth.pchauth.flask_adapter.login_required`.
- Produces: `shared.progress.routes.progress_bp` (same `/api` prefix and routes), plus module attributes `user_db` and `content_db`, still injected by the app.
- `content_db` is duck-typed. Its required surface is listed in the module docstring, taken from the actual calls in the file: `get_book`, `resolve_reader_marker`, `recover_reader_marker`, `get_reader_manifest`, and whatever else the file calls. Phase 3's Distill DB implements the same list.

- [ ] **Step 1: Write the failing test.** Add `tests/shared/test_progress_package.py::test_progress_blueprint_registers_on_bare_app`:
  - It builds a bare `Flask(__name__)`.
  - It sets `routes.user_db` to a `UserDatabase(tmp_path/'u.db')` and `routes.content_db` to a stub with `get_book=lambda i: None`.
  - It registers `progress_bp` with pchauth `AuthConfig(mode='off')`.
  - It asserts `POST /api/progress/v2/mutations` with `{"book_id": 1}` returns 400 `{'error': 'Unknown book'}`.
- [ ] **Step 2: Run it to verify it fails.** Expected: `ModuleNotFoundError: shared.progress`.
- [ ] **Step 3: Move the module and update the imports.** Write the `content_db` surface docstring.
- [ ] **Step 4: Run the full suite.** Expected: all pass, ≥ baseline.
- [ ] **Step 5: Commit.** `git commit -m "Move progress routes into shared.progress"`

### Task 4: `shared.reader` — reader-index mixin extracted from `models.py`

**Files:**
- Create: `shared/reader/__init__.py`, `shared/reader/index.py`
- Modify: `backend/models.py` (remove lines ~1809–2294, the "Continuous-reader index and query surface" block, and the `reader_version` / `reader_unit` DDL at ~226–266)
- Test: `tests/shared/test_reader_index.py`. The existing `tests/test_reader_storage.py`, `test_reader_manifest_chapter_ids.py` and `test_reader_verse_passages.py` must pass unchanged.

**Interfaces:**
- Produces, in `shared/reader/index.py`:
  - `create_reader_tables(cursor: sqlite3.Cursor) -> None`. The `reader_version` and `reader_unit` `CREATE TABLE/INDEX IF NOT EXISTS` statements, verbatim. The old-table migration and drops stay in Plainly's `models.py`.
  - `class ReaderIndexMixin`. It holds every `_reader_*` helper and the public methods `ensure_reader_content`, `get_reader_manifest`, `get_reader_segment`, `resolve_reader_marker`, `recover_reader_marker`, `map_reader_marker`, plus any other public reader method in that block. Signatures and return shapes are unchanged, and so are the class constants `_READER_MODES`, `_READER_SEGMENT_UNITS`, `_READER_SEGMENT_BYTES` and `_READER_OVERSIZED_BYTES`.
  - **Hooks the host class must implement:**
    - `get_connection() -> sqlite3.Connection`
    - `get_book(book_id) -> Optional[dict]`. Used by `get_reader_manifest`. Plainly's existing method satisfies it.
    - `_reader_load_book(conn, book_id) -> Optional[dict]`. Returns `{'id', 'verse': bool}`, or `None`. This replaces the inline `SELECT id, is_poetry FROM books`.
    - `_reader_load_chapters(conn, book_id, chapter_ids=None) -> list[dict]`. Each dict carries at least `id`, `chapter_number` and `chapter_title`.
    - `_reader_chapter_units(chapter, verse, plain_coverage) -> dict[str, list[Optional[str]]]`
    - `_reader_source_checksum(chapters) -> str`
  - Plainly's `Database(ReaderIndexMixin)` keeps its current implementations of those hooks, so behaviour and checksums are byte-identical.

- [ ] **Step 1: Pin the checksum (Review Focus 5).** Add `tests/test_reader_storage.py::test_source_checksum_is_stable_for_fixture_book`. Keep it in Plainly's tests, since it's about Plainly's data:
  - Build a two-chapter book in a `test_db_path` database.
  - Call `db.ensure_reader_content(book_id)`.
  - Assert `source_checksum` equals the literal hex string printed by running the test once against the current code. Paste that literal in.
  - It passes before the move and must still pass after.
- [ ] **Step 2: Write the failing mixin test.** In `tests/shared/test_reader_index.py`, define a minimal `FakeContent(ReaderIndexMixin)` over an in-memory-file SQLite DB:
  - `create_reader_tables` plus one `chapters(id, book_id, chapter_number, chapter_title, body)` table.
  - Hooks that put each `\n`-split line of `body` into mode `'summary'`, with `original` and `plain` empty.

  Tests:

```python
def test_manifest_counts_units_without_plainly(fake):
    fake.add_chapter(1, 1, 'One', 'a b\nc d e')
    fake.add_chapter(2, 1, 'Two', 'f')
    manifest = fake.get_reader_manifest(1)
    summary = next(m for m in manifest['modes'] if m['mode'] == 'summary')
    assert summary['terminal_paragraph_id'] == '2.0'

def test_marker_resolves_to_word_position(fake):
    fake.add_chapter(1, 1, 'One', 'a b\nc d e')
    m = fake.resolve_reader_marker(1, {'mode': 'summary', 'paragraph_id': '1.1', 'offset': 0})
    assert (m['ordinal'], m['word_position']) == (1, 2)

def test_unknown_paragraph_is_rejected(fake):
    fake.add_chapter(1, 1, 'One', 'a')
    assert fake.resolve_reader_marker(1, {'mode': 'summary', 'paragraph_id': '1.9'}) is None
```

  `FakeContent.get_book` returns `{'id': book_id}` for book 1. The manifest's `modes[]` entries carry `mode`, `availability`, `unit_count`, `total_word_count` and `terminal_paragraph_id` (`models.py:2026`).
- [ ] **Step 3: Run them to verify they fail.** Expected: `ModuleNotFoundError: shared.reader`.
- [ ] **Step 4: Extract the code.**
  - Move the block and the two DDL statements.
  - Add `_reader_load_book` to Plainly's `Database`, returning `{'id': row['id'], 'verse': bool(row['is_poetry'])}`.
  - Make `Database` inherit `ReaderIndexMixin`.
  - Call `create_reader_tables(cursor)` where the DDL was.
- [ ] **Step 5: Run the full suite.** Expected: all pass, including the pinned checksum, ≥ baseline + 4.
- [ ] **Step 6: Commit.** `git commit -m "Extract reader index into shared.reader mixin"`

### Task 5: `shared.web` and `shared.kindle`; rename `backend` → `plainly`

**Files:**
- Create:
  - `shared/web.py`: `PrefixMiddleware`, `gzip_response`, `make_asset_v`, with the code moved from `backend/app_base.py:50-69, 166-193, 239-258`.
  - `shared/kindle.py`: moved from `backend/kindle.py`.
- Rename (`git mv`): `backend/` → `plainly/`
- Modify:
  - every `backend` reference in `*.py`, `*.mjs`, `*.toml`, `*.ini`, `*.json` and `*.sh`, including string patch targets like `'backend.config.ILLUSTRATIONS_DIR'` in `tests/conftest.py`
  - `deploy/systemd/summra.service` (`ExecStart ... plainly.app_prod:app`)
  - `.claude/launch.json`, if it runs `backend/app.py`
- Move: Plainly-only tests from `tests/test_*.py` → `tests/plainly/` (everything not already in `tests/shared/`). `tests/conftest.py` stays at `tests/`.
- Test: `tests/shared/test_web.py`, plus `tests/test_layering_names.py` (repo-wide stale-name guard, top-level)

**Interfaces:**
- Produces:
  - `shared.web.PrefixMiddleware(wsgi_app)`. Unchanged behaviour.
  - `shared.web.install_web_basics(app: Flask, static_dir_override_env: str = 'SUMMRA_STATIC_DIR_OVERRIDE') -> None`. It wraps the app with `PrefixMiddleware`, registers `gzip_response` as an `after_request` hook, and sets the `asset_v` Jinja global. Plainly's `app_base` calls it at the same point where today's code runs, so hook order (gzip before cache headers) is preserved.
  - `shared.kindle.is_kindle_user_agent(ua: str) -> bool`. Unchanged.
  - `plainly.app_prod:app` and `plainly.app:app` are the new entry points.
  - The dev command becomes `python plainly/app.py`.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/shared/test_web.py
import gzip
from flask import Flask
from shared.web import install_web_basics

def _app():
    app = Flask(__name__)
    install_web_basics(app)
    app.add_url_rule('/', 'i', lambda: 'x' * 2000)
    app.add_url_rule('/where', 'w', lambda: __import__('flask').request.script_root)
    return app

def test_gzips_large_html():
    r = _app().test_client().get('/', headers={'Accept-Encoding': 'gzip'})
    assert r.headers['Content-Encoding'] == 'gzip' and gzip.decompress(r.data) == b'x' * 2000

def test_honours_forwarded_prefix():
    r = _app().test_client().get('/distill/where', headers={'X-Forwarded-Prefix': '/distill'})
    assert r.data == b'/distill'
```

```python
# tests/test_layering_names.py — Review Focus 4
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SKIP = {'venv', 'node_modules', '.git', 'archive', 'data', '.claude'}

def test_no_stale_backend_references():
    pat = re.compile(r"\bfrom backend\b|\bimport backend\b|['\"]backend\.|backend/app")
    hits = [str(p.relative_to(ROOT)) for ext in ('*.py', '*.mjs', '*.sh', '*.toml', '*.service')
            for p in ROOT.rglob(ext)
            if not SKIP & set(p.relative_to(ROOT).parts) and pat.search(p.read_text(errors='ignore'))
            and p.name != 'test_layering_names.py']
    assert hits == []
```

- [ ] **Step 2: Run them to verify they fail.** Expected: `test_web` → `ImportError`. `test_no_stale_backend_references` → FAIL, listing roughly 100 files.
- [ ] **Step 3: Extract `shared/web.py` and `shared/kindle.py`.** Make `plainly`'s `app_base` (still `backend/` at this point) call `install_web_basics(app)`. Run `pytest tests/ -q` (green) and commit: `git commit -m "Extract web basics and Kindle detection into shared"`.
- [ ] **Step 4: Rename the package.**
  - `git mv backend plainly`.
  - Rewrite every hit from the guard test, including the string patch targets, `pyproject.toml`'s include list (`plainly*` replaces `backend*`) and the systemd unit's `ExecStart`.
  - Drop the `try/except ImportError` dual-import blocks in `plainly/*.py` in favour of `from plainly import ...`. Keep `python plainly/app.py` working by checking it once.
  - Move the Plainly test files into `tests/plainly/` (add `__init__.py`).
  - Run `venv/bin/pip install -e .`.
- [ ] **Step 5: Run everything.**
  - `venv/bin/pytest tests/ -q`. Expected: ≥ baseline + 7, guard green.
  - Then run `python plainly/app.py` in the background and `cd tests/e2e && node smoke.mjs && node kindle_mode.mjs`. Expected: both pass.
- [ ] **Step 6: Commit.** `git commit -m "Rename backend package to plainly"`

### Task 6: Move `frontend/` and `scripts/` under `plainly/`; docs

**Files:**
- Rename: `frontend/` → `plainly/frontend/`, `scripts/` → `plainly/scripts/`
- Modify:
  - `plainly/config.py`: `BASE_DIR` stays the repo root. `COVERS_DIR` and `ILLUSTRATIONS_DIR` move to `plainly/frontend/static/...`.
  - `plainly/app_base.py`: `static_folder='frontend/static'`, `template_folder='frontend/templates'`.
  - `package.json`: the esbuild paths.
  - `frontend/static/js/check-build-fresh.mjs` paths.
  - `deploy/apache/summra.conf`: the `Alias` and `<Directory>` lines become `/opt/summra/plainly/frontend/static/`.
  - `deploy/install.sh`, `.gitignore` entries mentioning `frontend/` or `scripts/`.
  - Every `scripts.` / `from scripts` import, which becomes `plainly.scripts`. Every `Path(__file__)` repo-root computation under the moved scripts.
- Docs: `CLAUDE.md`, `AGENTS.md`, `README.md`, `tests/e2e/README.md`, `deploy/DEPLOY.md`. Update operational commands (`PYTHONPATH=backend`, `scripts/content/...`, `python backend/app.py`) to the new paths. Do **not** rewrite historical entries in `WORK_LOG.md` or `docs/archive`.
- Test: `tests/plainly/test_layout_paths.py`. Extend the stale-name guard pattern with `\bfrom scripts\b|['\"]scripts\.|frontend/static` outside `plainly/`.

**Interfaces:**
- Consumes: the `plainly` package from Task 5.
- Produces:
  - Final layout `shared/`, `plainly/{frontend,scripts,...}`, `distill/`, `tests/{shared,plainly}`.
  - Script invocations become `venv/bin/python -m plainly.scripts.content.generate_summaries ...`, or the file path under `plainly/scripts/`. Pick one form and use it consistently in CLAUDE.md.

- [ ] **Step 1: Write the failing tests (Review Focus 2 and 3).**

```python
# tests/plainly/test_layout_paths.py
import re
from pathlib import Path
from plainly import config

ROOT = Path(__file__).resolve().parents[2]

def test_base_dir_is_repo_root():
    assert config.BASE_DIR == ROOT and (ROOT / 'pyproject.toml').is_file()

def test_covers_live_in_plainly_frontend():
    assert config.COVERS_DIR == ROOT / 'plainly' / 'frontend' / 'static' / 'covers'
    assert config.COVERS_DIR.is_dir()

def test_apache_static_alias_matches_flask_static_dir():
    conf = (ROOT / 'deploy' / 'apache' / 'summra.conf').read_text()
    alias = re.search(r'Alias \$\{SUMMRA_PREFIX\}/static/ (\S+)', conf)[1]
    assert alias == '/opt/summra/plainly/frontend/static/'
```

- [ ] **Step 2: Run them to verify they fail.** Expected: FAIL on the `COVERS_DIR` path and the Alias.
- [ ] **Step 3: Move the folders and update the paths.** For each moved script that uses `__file__` (`grep -rn "__file__" plainly/scripts`), recompute paths from `plainly.config.BASE_DIR`, or adjust the `parents[N]` index. Then run `npm run build && npm run build:check`.
- [ ] **Step 4: Run everything.**
  - `venv/bin/pytest tests/ -q`, ≥ baseline + 10.
  - `node smoke.mjs` with `PATHS=/,/book/104,/explore`.
  - `node kindle_mode.mjs`.
  - One dry run of a moved script: `venv/bin/python -m plainly.scripts.content.generate_summaries data/books/pg23.txt --dry-run | tail -5`. It should print a CHAPTER BREAKDOWN.
- [ ] **Step 5: Update the docs** listed above. Add the new layout to `docs/ERD.md` (code structure section), and log the task in `WORK_LOG.md`.
- [ ] **Step 6: Commit.** `git commit -m "Move Plainly frontend and scripts under plainly/; update docs"`

### Task 7: Deploy the new layout to the VM

Identifiers come from `.prod-metadata.local.md`. Commands follow CLAUDE.md's deploy section, which Task 6 updated. **Ask the owner for a go-ahead in chat before step 2.**

**Files:**
- Modify (on the VM, not in the repo):
  - `/home/<SERVICE_USER>/.config/systemd/user/<SYSTEMD_UNIT>` (`ExecStart` → `plainly.app_prod:app`)
  - `<APACHE_PROXY_CONF>` (the Alias/Directory lines from `deploy/apache/summra.conf`)

- [ ] **Step 1: Push.** `git push origin main`. Confirm CI or a local full suite is green first.
- [ ] **Step 2: Pull on the VM** with CLAUDE.md step 1's guarded fast-forward command. Then run `venv/bin/pip install -e .` in `<REMOTE_REPO_PATH>` as `<VM_USER>`. Expected: `Successfully installed summra`.
- [ ] **Step 3: Update and restart the unit.**
  - `sed -i 's/backend\.app_prod:app/plainly.app_prod:app/'` on the unit file.
  - `systemctl --user daemon-reload`, then `restart` (as `<SERVICE_USER>`).
  - Expected: `is-active` → `active`, local `curl http://127.0.0.1:<GUNICORN_PORT>/` → `200`, no tracebacks in `journalctl --since '1 minute ago'`.
- [ ] **Step 4: Update Apache.** Copy the repo's `deploy/apache/summra.conf` over `<APACHE_PROXY_CONF>` (after `diff` shows only the Alias/Directory change), then run `sudo apachectl configtest && sudo systemctl reload apache2`. Expected: `Syntax OK`.
- [ ] **Step 5: Verify publicly (Review Focus 1 and 2).**
  - CLAUDE.md step 3's three curls → 200.
  - `curl -sSI https://<PROD_DOMAIN>/static/css/style.css` → 200.
  - One cover image URL taken from `/api/books` → 200.
  - `BASE_URL=https://<PROD_DOMAIN> node kindle_mode.mjs` passes, with sync checks skipped.
- [ ] **Step 6: Log it.** Add the deploy result to `WORK_LOG.md`, then `git commit -m "Record repo split production deployment" && git push`.
