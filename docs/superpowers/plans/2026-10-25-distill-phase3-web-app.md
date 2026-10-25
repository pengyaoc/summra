# Distill Phase 3 — Shared Reader Platform and Distill Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Plainly's web reader, reader CSS and templates, and Kindle reader into a shared reader platform that each app configures, without changing Plainly's behaviour. Then build the signed-in Distill app at `/distill` (library, book page, reader, saved place, progress, Kindle mode) as a second app on that platform.

**Architecture:**
- **One config per app.** Each app declares one `ReaderConfig` (`shared/reader/config.py`), with modes, features, settings controls, Kindle text modes, cache name and cache visibility. That single declaration drives:
  - the shared templates (the mode selector, the settings panel and feature sections)
  - the reader API blueprint
  - the Kindle pages
  - the JS, which receives it as `window.READER_CONFIG`

  Plainly's four modes and its side-by-side layout become entries in Plainly's config instead of literals in code.
- **The reader logic stays Plainly's code, moved as it is.** `pagination.js` and `settings.js` move whole, along with the continuous-reader half of `reader.js`. Where they name a specific mode or a Plainly constant, only the input changes, to a config lookup. The control flow is untouched. Generic layout code keyed by CSS class (`chapter-side-by-side`, `.side-by-side-row`) stays as it is.
- **Each app plugs in with its config and two JS hooks:** the unit renderer and the back target. Everything else has a platform default (see "Plug-in surface").
- **Distill bends its data to fit the reader.** Segment units carry the block's server-rendered HTML. One Python renderer (`distill/render.py`) produces that HTML for the web reader and for Kindle.
- **Serving.** Shared static files are reached through a committed `static/shared` symlink in each app, served at `/static/shared/...` under each app's prefix. esbuild bundles them into Plainly's `app.min.js`. Shared templates sit under `shared/templates/shared/` and reach each app through a `ChoiceLoader`. Both are done in Task 1.

**Tech Stack:** Python 3.11, Flask, Jinja2, SQLite, vanilla ES modules (esbuild bundle for Plainly only), ES5 for Kindle, pytest, Playwright (`tests/e2e/*.mjs`), `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-24-distill-design.md`: §5.7 (web app, shared reader, sign-in), §5.2 and §5.3 (blocks, units), §5.8 (deploy shape only) and §5.9 (phase 3). Owner direction (2026-10-25):
- "share the reader view as much as possible with Plainly … Don't reinvent it."
- "a reusable platform that each app plugs into with a configuration that enables/disables certain features … generalize the multi-reader selector."

Phase 2 is done (`distill/models.py`, `distill/book_format.py`). Local `data/distill.db` holds 4 books (`atomic-habits`, `the-goal`, `guns-germs-and-steel`, `quanqiutongshi`).

## Plug-in surface (the whole contract an app implements)

**Python**
- `ReaderConfig`, declared once in `<app>/reader_config.py`.
- `install_reader_platform(app, config, get_content_db, user_db)`.
- A content DB implementing the existing `ReaderIndexMixin` hooks and the `shared.progress` library hooks. These are unchanged from phases 1–2.
- Kindle page handlers, registered through `register_kindle_pages(bp, handlers, config)`. Only when `config.features.kindle` is on.

**JS hooks**, on the host class passed to `applyReaderPlatform(Host)`:
- `continuousReaderBlock(text) -> {tag, className, content}`: renders one unit's body.
- `selectBook(book)`: where the reader's back button goes.

**Platform defaults**, applied only when the host lacks them:
- `showOnlySections()` (no-op)
- `initReaderPlatform()`, which sets `apiBase` from `withBasePath(config.api_base)` and `pagination` from `createPaginationState()`

## Global Constraints

- **Plainly behaviour must not change.** Before and after every task in Tasks 2–5:
  - the full pytest suite is green (924 passed after Task 1)
  - `npm run build:check` passes
  - the Plainly e2e set is green: `smoke`, `kindle_mode`, `reader_progress`, `reader_themes`, `reader_last_line_visible`, `reader_opens_at_chapter`, `reader_segments_fast_open`, `reader_illustrations`, `reader_font_figtree`, `reader_nav_mouse`, `sxs_row_split`, `text_size_adjust`, `redesign_home`, `redesign_reader`
  - the reader style snapshot (Task 1) compares equal
  - the golden markup tests (Task 1) are green
- **Make inputs data-driven; don't refactor logic.** Where a shared method names a mode, a label or a Plainly constant, replace that literal with a config lookup that produces the same value for Plainly's config. Leave control flow alone. Do not write new reader, pagination, position, settings or page-turn logic.
- **Mode ids are storage vocabulary.** `ALL_MODES = ('summary', 'original', 'plain', 'side_by_side')` in `shared/reader/modes.py` is the one registry. Config mode ids must come from it. The stored schema (SQL `CHECK` strings, `reader_unit` rows) stays byte-identical.
- **Moving a test.** When a test only moves because the file it reads moved, copy its assertions word for word, change only the path and say so in the commit body.
- `shared/` imports nothing from `plainly` or `distill`. The guard is `tests/shared/test_layering.py`. Files under `shared/static` and `shared/templates` never contain "Plainly" or "Distill". App names, labels and copy that differ between apps come from config.
- Shared JS mixin files contain no `import`, because tests load them from a `data:` URL. Only `shared/static/js/platform.js` imports.
- Distill serves at `/distill` behind Apache OIDC.
  - Env vars: `DISTILL_AUTH_MODE`, `DISTILL_ALLOWED_EMAILS`.
  - Local dev defaults to pchauth mode `off`.
  - `distill.app_prod` refuses to start unless `DISTILL_AUTH_MODE=required`.
- Distill content is private. Its config has `cache_visibility='private'`, and no route or header may make text or images publicly cacheable.
- Ports: Distill dev on **5003** (`PORT` env). Plainly in this worktree on **5002**.
- Kindle pages are server-rendered. `kindle.js` stays ES5.
- Day-one Distill features only: library (with Reading now), book page, reader, saved place, progress, Kindle mode.
- No VM, Apache-on-VM or systemd work (phase 4). `distill.app_prod:app` must import cleanly. `deploy/gunicorn_config.py` (env-driven) is its gunicorn config.
- TDD: write the failing test first. A pure move instead gets a characterization test that is green before and after. Every commit body carries the pytest pass count and a `WORK_LOG.md` entry.

## Review Focus

1. **Two apps on one origin share browser state.** IndexedDB caches segments by `book_id`, and the ids collide between apps.
   - Task 3 takes the cache name from `config.cache_db_name`.
   - Task 8's e2e asserts Distill opens `distill-reader-v1` and never `summra-reader-v2`.
2. **Private content gets exposed:** a public cache header, prod running without auth, or a stranger signing in.
   - Task 2: the blueprint takes `cache_visibility` from config.
   - Task 7: Distill's manifest, segment and image responses are `private`; `app_prod` raises without `required`; a non-allow-listed email gets 403 on a page, an image and a segment.
3. **A configured mode is unavailable in a book's manifest, or a saved `last_mode` is not configured.**
   - Task 3 node tests cover these cases:
     - the selector shows only modes that are both configured and available in the manifest
     - a mode the manifest offers but config omits is never chosen
     - the selector is hidden when the app configures fewer than two modes (Distill); a Plainly book with fewer than two available modes keeps today's selector
     - a saved `last_mode` outside config falls through to `default_modes`
   - Task 2 adds a config validation test.
4. **A feature disabled in config while its DOM or API is still reachable.**
   - Task 2: `features.progress=False` leaves `/api/progress/*` and `/api/auth/check` as 404.
   - Task 3: `illustrations=False` renders no figure; `page_turn_hint=False` shows no hint.
   - Task 5: with `kindle=False`, a Kindle user agent gets the web page and `/api/kindle/progress` returns 404.
   - Task 4: the template renders no section for a disabled control.
5. **Distill blocks in the paginated reader.**
   - Rendered DOM text must equal `block_text`, or quote recovery breaks. Task 6 checks every block type including CJK; Task 8's e2e checks that a reload restores the same anchor.
   - Tables and figures taller than a page: Task 8's e2e asserts no anchored block overflows its page, except a scrolling table. Task 9's e2e asserts no `tr` or `figure` spans two Kindle columns.

---

## File map

**shared/** (new unless noted)
- **`reader/`:** `modes.py`, `config.py`, `platform.py`, `routes.py`; `index.py` (modify)
- **`auth/user_models.py`** (modify): `VALID_MODES` comes from `modes.py`
- **`static/js/`:**
  - `base_path.js`, `reader_utils.js`
  - `pagination.js`, `settings.js` (moved)
  - `continuous_reader.js`, `reader_state.js`
  - `platform.js`
  - `kindle.js` (moved)
- **`static/css/`:** `base.css`, `reader.css`, `kindle.css` (moved). Plus `static/fonts/` (moved).
- **`templates/shared/`:**
  - `reader/{_config_script,_continuous_reader,_settings_panel}.html`
  - `_library_card.html`
  - `kindle/{base,_masthead,_pager,_account,not_found,reader_base}.html`
- **`kindle/`:** `__init__.py` (was `shared/kindle.py`), `pages.py`, `progress.py`

**plainly/** (modify)
- New: `reader_config.py`
- JS: `app.js`, `reader.js`, `auth.js`, `route_utils.js`, `app.min.js`
- `css/style.css`
- Templates: `index.html`, `_book_card.html`, `kindle/{library,book,reader}.html`. The other Kindle templates are deleted.
- `routes/books.py`, `routes/kindle.py`, `app_base.py`

**distill/** (new unless noted)
- Python: `reader_config.py`, `render.py`, `app_base.py`, `app.py`, `app_prod.py`, `routes.py`, `kindle_routes.py`
- Templates: `{base,library,book,reader,not_found}.html` and `kindle/{library,book,reader}.html`
- Static: `static/shared` (symlink), `static/css/{distill,distill_kindle}.css`, `static/js/distill_reader.js`
- Modify: `config.py`, `models.py`

**tests/**
- `shared/`: `test_reader_config.py`, `test_reader_routes.py`, `test_shared_js.py`, `test_kindle_shared.py`
- `distill/`: `test_render.py`, `test_app.py`, `test_pages.py`, `test_kindle.py`
- `js/`: `base_path.test.mjs`, `mixins_disjoint.test.mjs`, `reader_modes.test.mjs`
- `e2e/`: `distill.mjs`

---

### Task 1: Shared static and template plumbing, plus Plainly baselines

**Files:**
- Create: `shared/static/.gitkeep`, `shared/templates/shared/.gitkeep`, the symlink `plainly/frontend/static/shared` → `../../../shared/static`
- Modify: `shared/web.py`, `plainly/app_base.py`, `deploy/apache/summra.conf` (`Options -Indexes +FollowSymLinks` in the static `<Directory>`)
- Create: `tests/shared/test_shared_ui.py`, `tests/e2e/reader_style_snapshot.mjs`, `tests/plainly/test_reader_shell_markup.py` and `tests/plainly/golden/{reader_shell.html,kindle_library.html,kindle_book.html,kindle_reader.html}`

**Interfaces:**
- Produces:
  - `shared.web.SHARED_TEMPLATES: Path`
  - `shared.web.install_shared_ui(app: Flask) -> None`, which sets `app.jinja_loader = ChoiceLoader([app.jinja_loader, FileSystemLoader(SHARED_TEMPLATES)])`
  - Plainly's context processor adds `app_name='Plainly'`
  - The snapshot script `MODE=record|compare node reader_style_snapshot.mjs`, which writes and reads `tests/e2e/screenshots/reader_styles.json`

- [ ] **Step 1: Record the baselines on unchanged code.**
  - Start Plainly with `PORT=5002 venv/bin/python plainly/app.py`, then run `BASE_URL=http://localhost:5002 MODE=record node reader_style_snapshot.mjs`. The script opens `/books/pride-and-prejudice/read` at 1280×900 and 390×844, in the light and dark themes. For each selector in a fixed list it records `getComputedStyle` (font, size, line-height, colour, background, margin, padding, width, height, display, position) as JSON. Selectors: `.continuous-reader-chrome`, `.reader-toolbar-btn`, `.continuous-reader-content`, `.pagination-page-container`, `.pagination-page-container p`, `.reader-chapter-heading`, `.continuous-reader-footer`, `#reader-progress-fill`, `.reading-settings-panel`, `.font-choice`, `.size-btn`, `.theme-choice`, `.reader-panel`, `.library-card`. Open the settings panel and the table of contents before measuring the panels. `MODE=compare` exits 1 on any difference and prints it.
  - In `test_reader_shell_markup.py`, write the characterization tests `test_reader_shell_markup_unchanged` and `test_kindle_pages_markup_unchanged`. They render `/books/<slug>/read`, plus the Kindle library, book and reader pages, using the fixture book from `tests/plainly/test_kindle_mode.py`. They cut out `#continuous-reader-section` through the end of `#reading-settings-panel`, and the Kindle `<body>`, collapse whitespace, and compare against the golden files. A test-only `UPDATE_GOLDEN=1` writes the golden files; this step uses it once.
- [ ] **Step 2: Write the failing tests** in `tests/shared/test_shared_ui.py`:
  - `test_install_shared_ui_resolves_shared_templates`: on a bare Flask app, after `install_shared_ui`, `render_template_string("{% include 'shared/probe.html' %}")` works with a probe file placed in `tmp_path` and `SHARED_TEMPLATES` monkeypatched.
  - `test_app_templates_win_over_shared`
  - `test_plainly_serves_shared_static`: `client.get('/static/shared/.gitkeep').status_code == 200`.
  - `test_static_shared_is_symlink_to_shared_static`: `Path('plainly/frontend/static/shared').resolve() == Path('shared/static').resolve()`.
  - `test_shared_assets_are_app_neutral`: no `Plainly`/`Distill` (case-insensitive) in any file under `shared/static` (skip fonts) or `shared/templates`.
  - Extend `tests/plainly/test_apache_conf.py` with `test_static_directory_follows_symlinks`.
- [ ] **Step 3: Run the new tests and confirm they fail.** Command: `venv/bin/pytest tests/shared/test_shared_ui.py tests/plainly/test_apache_conf.py -v`. Expect an ImportError for `install_shared_ui` and the symlink assertion to fail.
- [ ] **Step 4: Implement.** Call `install_shared_ui(app)` in `plainly/app_base.py` next to `install_web_basics`. Add the symlink with `ln -s ../../../shared/static plainly/frontend/static/shared` and commit it as a symlink.
- [ ] **Step 5: Verify.** Run `venv/bin/pytest tests/ -q`; everything should be green. Then run `MODE=compare` and expect "no differences".
- [ ] **Step 6: Commit** "Add shared static/template plumbing and Plainly reader baselines". The commit includes the golden files. The style JSON is not committed (screenshots/ is gitignored), so record it again on `main` if it is lost.

### Task 2: Reader platform config, mode registry and the reader API blueprint

**Files:**
- Create: `shared/reader/modes.py`, `shared/reader/config.py`, `shared/reader/platform.py`, `shared/reader/routes.py`, `plainly/reader_config.py`
- Create the shared partial `shared/templates/shared/reader/_config_script.html`: `<script>window.READER_CONFIG = {{ reader_config.to_client()|tojson }};</script>`
- Modify:
  - `shared/reader/index.py`: `_READER_MODES = ALL_MODES`. The literal tuples `('summary', 'original', 'plain')` and `('original', 'plain')` become `SINGLE_MODES` and `SIDE_BY_SIDE_MEMBERS`.
  - `shared/auth/user_models.py`: `VALID_MODES = set(ALL_MODES)`.
  - `plainly/routes/books.py`: delete the four reader handlers.
  - `plainly/app_base.py`
- Tests: `tests/shared/test_reader_config.py`, `tests/shared/test_reader_routes.py`

**Interfaces:**
- **`shared.reader.modes`:**
  - `ALL_MODES = ('summary', 'original', 'plain', 'side_by_side')`
  - `SINGLE_MODES = ('summary', 'original', 'plain')`
  - `SIDE_BY_SIDE_MEMBERS = ('original', 'plain')`
- **`shared.reader.config`**, all frozen dataclasses:
  - `ReaderMember(id: str, label: str, cell_class: str)`
  - `ReaderMode(id: str, label: str, layout: str = 'single', members: tuple[ReaderMember, ...] = (), library_label: Optional[str] = None, min_width: Optional[int] = None, narrow_fallback: tuple[str, ...] = ())`. `layout` is `'single'` or `'side_by_side'`. `min_width` hides the mode below that viewport width, and `narrow_fallback` is the preference order used then.
  - `ReaderFeatures(progress: bool = True, illustrations: bool = False, page_turn_hint: bool = True, kindle: bool = True)`. The code survey found only these four platform features. Audio/TTS, study cues, the blog and the install prompt are Plainly SPA code outside the reader, so they get no flag. The "about" panel (`loadContinuousAbout`) has no DOM target in `index.html`; it is dead and stays in Plainly's `reader.js`. Offline save does not exist; segment caching is always on.
  - `ReaderSettings(fonts: tuple[tuple[str, str], ...], font_default: str, size_min: int, size_max: int, size_default: int, themes: tuple[tuple[str, str], ...], theme_default: str)`.
  - `DEFAULT_SETTINGS = ReaderSettings((('georgia', 'Reader Serif'), ('system', 'System'), ('figtree', 'Figtree')), 'georgia', 12, 24, 16, (('light', 'Light'), ('dark', 'Dark')), 'light')`. These are today's values.
  - `KindleOptions(text_modes: tuple[tuple[str, str], ...], default_text: str)`.
  - `ReaderConfig(app_name: str, cache_db_name: str, cache_visibility: str, modes: tuple[ReaderMode, ...], default_modes: tuple[str, ...], features: ReaderFeatures, settings: ReaderSettings = DEFAULT_SETTINGS, kindle: Optional[KindleOptions] = None, api_base: str = '/api', extra_page_blocks: str = '', hint_keys: frozenset[str] = frozenset())`.
    - `__post_init__` raises `ValueError` when:
      - a mode id is not in `ALL_MODES`, or ids are duplicated
      - `layout` is unknown
      - a `side_by_side` layout's member ids are not `SIDE_BY_SIDE_MEMBERS`
      - `default_modes`, `narrow_fallback` or the Kindle `text_modes` name a mode that is not configured
      - `cache_visibility` is not in `{'public', 'private'}`
      - `features.kindle` is set but `kindle` is `None`
      - a settings default is not among its choices
    - `mode(id) -> Optional[ReaderMode]`
    - `to_client() -> dict`: a JSON-safe dict of everything except `kindle` and `hint_keys`. `library_label` falls back to `label`.
- **`plainly/reader_config.py: PLAINLY_READER`:**
  - `app_name='Plainly'`, `cache_db_name='summra-reader-v2'`, `cache_visibility='public'`
  - `modes`, in today's button order:
    - `summary` "Summary"
    - `original` "Original"
    - `plain` "Plain English"
    - `side_by_side` "Side-by-Side", with `layout='side_by_side'`, members `(original, "Original", "original")` and `(plain, "Plain English", "modern")`, `library_label='Side by side'`, `min_width=1024` and `narrow_fallback=('plain', 'original')`
  - `default_modes=('plain', 'original')`
  - `features=ReaderFeatures(progress=config.FEATURE_AUTH, illustrations=True, page_turn_hint=True, kindle=True)`
  - `kindle=KindleOptions((('plain', 'Plain English'), ('original', 'Original')), 'plain')`
  - `hint_keys=config.READER_HINTS`
- **`shared.reader.routes.make_reader_blueprint(get_content_db: Callable[[], Any], cache_visibility: str) -> Blueprint`** has the four `/api/reader/books/<int:book_id>/{manifest, segments/<segment_id>, map, recover}` handlers, moved verbatim. The manifest's Cache-Control is `f'{cache_visibility}, max-age=300, must-revalidate'` and the segment's is `f'{cache_visibility}, max-age=31536000, immutable'`. The DB is looked up per request.
- **`shared.reader.platform.install_reader_platform(app: Flask, config: ReaderConfig, get_content_db: Callable[[], Any], user_db: Optional[UserDatabase]) -> None`.** It:
  - stores `app.extensions['reader_config'] = config`
  - adds a context processor providing `reader_config` and `app_name`
  - registers the reader blueprint with `config.cache_visibility`
  - when `user_db` is given, sets `progress_routes.user_db` and `progress_routes.content_db = get_content_db()`, plus `whoami.user_db`
  - only when `config.features.progress` is on, registers `progress_bp` and `whoami_bp`

  This is the same split Plainly has today: the globals are always set, and the blueprints are registered under `FEATURE_AUTH`. Plainly still runs `init_pchauth` itself, before this call.

- [ ] **Step 1: Write the failing tests.** In `test_reader_config.py`:
  - `test_plainly_config_matches_todays_literals`: the mode ids and labels, `min_width`, the members' `cell_class`, `cache_db_name` and the settings defaults.
  - `test_unknown_mode_id_rejected`
  - `test_side_by_side_members_must_match_storage`
  - `test_default_and_fallback_modes_must_be_configured`
  - `test_kindle_feature_requires_kindle_options`
  - `test_to_client_is_json_and_omits_kindle`
  - `test_registry_matches_schema_checks`: read `sqlite_master.sql` for `reader_unit`, `reader_book_state` and `reader_mode_state` from fresh databases. The `CHECK(mode IN (...))` lists must equal `ALL_MODES`, so the schema text is pinned, not generated.

  In `test_reader_routes.py`, use a fake content DB:
  - `test_manifest_public_by_default_config`
  - `test_private_visibility_marks_manifest_and_segment_private`
  - `test_segment_404_json_on_unknown`
  - `test_map_requires_marker_400`
  - `test_db_resolved_per_request`
  - `test_progress_feature_off_leaves_progress_and_auth_check_404` (Review Focus 4)
  - `test_platform_sets_progress_globals_even_when_feature_off`
- [ ] **Step 2: Run them and confirm they fail** (ModuleNotFoundError).
- [ ] **Step 3: Implement.** Plainly's `app_base.py` replaces its progress/whoami registration and reader routes with `install_reader_platform(app, PLAINLY_READER, lambda: common.db, user_db)`. It also includes `_config_script.html` in `index.html`'s `<head>`, which is outside the golden region.
- [ ] **Step 4: Verify.** The full suite is green, including `test_api_routes_characterization.py`, `test_reader_index.py`, `test_user_models.py` and the goldens.
- [ ] **Step 5: Commit** "Add reader platform config, mode registry and shared reader API blueprint".

### Task 3: Shared web reader JS, driven by `READER_CONFIG` (Plainly moves onto it)

**Files:**
- Create the following under `shared/static/js/`:
  - **`base_path.js`:** `summraBasePath` and `withBasePath`, cut from `route_utils.js`, as a classic script in the same IIFE.
  - **`reader_utils.js`:** `readerUtilsMixin`, which holds:
    - `escapeHtml`, cut from `app.js`
    - `readerConfig()`, returning `window.READER_CONFIG`
    - `readerMode(id)`
    - `readerLayout(id)`, returning `'single'` or `'side_by_side'`
    - `readerAvailableModes(manifest)`: the configured modes, in config order, that the manifest lists with `availability !== 'unavailable'` and that pass `isContinuousReaderModeAvailable`
  - **`pagination.js` and `settings.js`:** `git mv`.
    - `pagination.js` adds `export function createPaginationState()`, which returns today's constructor literal.
  - **`continuous_reader.js`:** `continuousReaderMixin`, made of the continuous-reader methods cut from `plainly/.../reader.js`:
    - `showContinuousReader`, `readerSkeletonHtml`, `resolveReaderChapter`
    - `isContinuousReaderModeAvailable`, `switchContinuousReaderMode`, `enforceContinuousReaderViewport`
    - `loadContinuousReaderAt`, `findContinuousSegmentForChapter`, `fetchContinuousSegment`
    - `illustrationSources`, `continuousIllustrationHtml`
    - `renderContinuousSegments`, `findContinuousPageForChapter`, `findContinuousPageForMarker`
    - `settleContinuousReaderMarker`, `continuousMarkerOffset`, `continuousMarkerWordPosition`
    - `setupContinuousReaderChrome`, `setupContinuousReaderLifecycle`, `toggleContinuousPanel`
    - `mapContinuousMarker`, `recoverContinuousMarker`, `onContinuousPageDisplayed`
    - `saveContinuousReader`, `updateContinuousReaderProgress`, `setContinuousReaderStatus`, `navigateContinuousSegment`
  - **`reader_state.js`:** the reader-state half of `auth.js`, which sets `window.readerState`:
    - `readerDb`, `queueReaderMutation`, `getReaderState`, `getLibrary`
    - the four cache functions
    - `checkAuthStatus`, `hintSeen`, `markHintSeen`
    - `currentUser()`, `wrongAccountEmail()`
  - **`platform.js`:**
    - `export function applyReaderPlatform(Host)` does `Object.assign(Host.prototype, readerUtilsMixin, paginationMixin, settingsMixin, continuousReaderMixin)`. It then adds `readerPlatformDefaults` (`showOnlySections() {}` and `initReaderPlatform()`) only for keys that `Host.prototype` lacks.
    - It also re-exports `createPaginationState`.
- Modify `plainly/frontend/static/js/`:
  - **`app.js`:** imports `../shared/js/platform.js` and calls `applyReaderPlatform(SummraApp)` before the remaining `Object.assign` calls (breadcrumbs, audio, reader). Its constructor keeps `this.apiBase` and uses `createPaginationState()`.
  - **`reader.js`:**
    - Keeps the legacy chapter and medium pages, `renderLibraryCards`, `showLibrary`, `markReaderBookUnfinished`, `loadContinuousAbout`, `formatContinuousReaderText` and `continuousReaderBlock`. `continuousReaderBlock` is a hook.
    - `LIBRARY_MODE_LABELS` becomes a lookup of `library_label` in `readerConfig()`, defaulting to `default_modes[0]`.
  - **`auth.js`:** keeps the modal UI. `window.authModule = { ...window.readerState, initAuth, trackChapterView, trackPageChange, onChapterComplete }`.
  - **`route_utils.js`** loses the base-path functions. Then rebuild `app.min.js`.
- Modify `index.html`: load `shared/js/base_path.js` before `route_utils.js`, and `shared/js/reader_state.js` before `auth.js`.
- Tests:
  - `tests/shared/test_shared_js.py` receives the moved `test_continuation_segments_do_not_repeat_chapter_heading`, retargeted at `continuous_reader.js`.
  - `tests/js/base_path.test.mjs` receives the moved base-path tests from `route_utils.test.mjs`.
  - Create `tests/js/mixins_disjoint.test.mjs` and `tests/js/reader_modes.test.mjs`.

**Mode-name occurrences found in the moved code, and how each is handled.** No other moved line changes.

| Place (method) | Literal today | Becomes |
|---|---|---|
| `showContinuousReader`, the default mode | `'plain'`, then `'original'`, then `available[0]` | the first of `config.default_modes` in `readerAvailableModes(manifest)`, then `available[0]`. `available` is now limited to configured modes. |
| `isContinuousReaderModeAvailable` | `mode !== 'side_by_side' \|\| matchMedia('(min-width: 1024px)')` | `!m.min_width \|\| matchMedia(`(min-width: ${m.min_width}px)`)` |
| `setupContinuousReaderLifecycle` | `'(max-width: 1023px)'` | one listener per mode with `min_width`, on `(max-width: ${min_width - 1}px)` |
| `enforceContinuousReaderViewport` | `reader.mode !== 'side_by_side'`; fallback is `'plain'` if available, else `'original'` | `readerMode(reader.mode).min_width`; fallback is the first available entry of `narrow_fallback`, else its last entry. The status copy is `${label} is available on screens ${min_width}px wide or larger.` |
| `renderContinuousSegments` | `reader.mode === 'side_by_side'`; `members.original`/`.plain`; header copy and gap copy "Original" / "Plain English"; single-mode gap copy "Plain English unavailable for this section." | `readerLayout(mode) === 'side_by_side'`; `mode.members[i].id`; each member's `label` and `cell_class`; single-mode gap copy `${mode.label} unavailable for this section.` |
| `findContinuousPageForMarker`, `continuousMarkerOffset` | `.side-by-side-cell.original` | `.side-by-side-cell.${members[0].cell_class}` |
| `setupContinuousReaderChrome`, the selector | always unhides `#reader-mode-settings`; "Side-by-Side is unavailable for this book." / "… 1024px …" | hides `#reader-mode-settings` when `READER_CONFIG.modes.length < 2` (an app-level setting, so Plainly is unchanged for every book), otherwise as today. The help copy comes from the first mode with `min_width`: `${label} is unavailable for this book.` / `${label} is available on screens ${min_width}px wide or larger.` |
| `continuousIllustrationHtml` | n/a | first line: `if (!readerConfig().features.illustrations) return '';` |
| `pagination.js`, `showPageTurnHintOnce` | n/a | first line: return when `!features.page_turn_hint` |
| `pagination.js`, `calculatePages`, the regular block selector | fixed list | the fixed list plus `config.extra_page_blocks` when non-empty |
| `settings.js`, `loadReadingPreferences` | `'georgia'`, `'16'`, `'light'` | `settings.font_default`, `String(settings.size_default)`, `settings.theme_default` |
| `reader_state.js`, `readerDb` | `'summra-reader-v2'` | `READER_CONFIG.cache_db_name` |
| `pagination.js` and `settings.js` legacy chapter-page branches; `'side-by-side'` and `chapter-side-by-side` class checks | layout and CSS class names, plus Plainly's legacy chapter page | unchanged: generic layout code, or Plainly-only DOM that Distill never renders |
| Plainly app code outside the platform: the `book-sxs-link` `?mode=side_by_side`, the legacy chapter-page view modes, `formatSideBySideText` | Plainly's own UI | unchanged |

- [ ] **Step 1: Write the failing tests.**
  - `mixins_disjoint.test.mjs`: no key overlap between any two of `readerUtilsMixin`, `paginationMixin`, `settingsMixin`, `continuousReaderMixin` and Plainly's `readerMixin`. Also, `applyReaderPlatform` does not overwrite a method the host already defines.
  - `reader_modes.test.mjs`: stub `window.READER_CONFIG` and the DOM, then call the mixin methods directly. Review Focus 3 cases:
    - `test_available_modes_intersect_config_and_manifest`: config `[summary]` with a manifest offering `original` gives `['summary']`.
    - `test_default_mode_follows_config_preference`: Plainly's config with `plain` unavailable gives `original`.
    - `test_saved_mode_outside_config_falls_through`
    - `test_selector_hidden_when_one_mode_configured`
    - `test_selector_shown_for_plainly_book_with_one_available_mode`
    - `test_side_by_side_min_width_from_config`
    - `test_narrow_fallback_first_available`
    - `test_gap_copy_uses_mode_label`
    - `test_sxs_cells_use_member_cell_class`
    - `test_illustrations_off_renders_no_figure`
  - `test_shared_js.py`:
    - `test_reader_state_cache_db_from_config`, with a stub `indexedDB.open`
    - `test_extra_page_blocks_appended_only_when_configured`
    - the moved test
- [ ] **Step 2: Run them and confirm they fail.** Command: `node --test tests/js/ && venv/bin/pytest tests/shared/test_shared_js.py -v`.
- [ ] **Step 3: Move, wire and parameterise exactly the rows above.** Then run `npm run build`.
- [ ] **Step 4: Verify.** Node tests, pytest, `build:check`, `MODE=compare`, the goldens and the Plainly e2e set all pass. Plainly shows no visible change for any book.
- [ ] **Step 5: Commit** "Extract web reader into config-driven shared platform; Plainly plugs in".

### Task 4: Shared reader CSS and config-rendered templates (Plainly moves onto them)

**Files:**
- Create under `shared/static/css/`, cut from `style.css` by section-comment boundaries:
  - `base.css`: everything before `/* Header */`, which is the Figtree `@font-face`, the reset and `:root` tokens. The fonts `git mv` to `shared/static/fonts/`.
  - `reader.css`: the sections `Reading Settings Panel`, `Font Selection`, `Text Size Control`, `Theme Selection`, `Font family for pagination containers`, and everything from `PAGINATION SYSTEM FOR CHAPTER READING` through the end of `Continuous Reader and Library`.
- Create under `shared/templates/shared/`, rendered from `reader_config`:
  - `reader/_continuous_reader.html`: the reader section. It takes `reader_hidden`.
  - `reader/_settings_panel.html`:
    - The mode section renders when `reader_config.modes|length > 1`, with one `data-reader-settings-mode` button per configured mode, using `label`.
    - Font, size and theme controls come from `reader_config.settings`. The default choice gets `active`; the slider `min`, `max` and `value` and the `size-value` text come from the size fields.
  - `_library_card.html`: the macro `library_card(book, cover_html, read_href=None)`. Its mode label is `reader_config.mode(book.last_mode or default).library_label`, and it is omitted when `reader_config.modes|length == 1`. With `read_href`, the action is an `<a class="library-read-action">`; otherwise it is today's `<button data-library-read>`.
- Modify:
  - `index.html`: links `shared/css/base.css` before `style.css` and `shared/css/reader.css` after it, and includes the partials.
  - `_book_card.html`: `library_card(book)` wraps the shared macro with `book_cover(book)`.
  - `style.css`

**Interfaces:**
- Produces: the partials above, which read only `reader_config` and their own named parameters, and `shared/css/{base,reader}.css`.

- [ ] **Step 1: Write the failing tests.** Add to `test_reader_config.py`, rendering through a bare Flask app with `install_shared_ui`:
  - `test_settings_panel_single_mode_renders_no_selector`
  - `test_settings_panel_renders_configured_fonts_and_size_range`
  - `test_library_card_hides_mode_label_for_single_mode_app`

  The Plainly goldens are the characterization tests and are already green.
- [ ] **Step 2: Run the new tests and confirm they fail** (template not found).
- [ ] **Step 3: Move the CSS and markup.**
- [ ] **Step 4: Verify.**
  - `MODE=compare` shows no differences. If a later `style.css` rule overrode a moved rule, move that rule into `reader.css` after it.
  - The goldens and the full pytest suite are green, and the e2e set passes.
- [ ] **Step 5: Commit** "Extract reader CSS and config-rendered reader templates into shared".

### Task 5: Shared Kindle reader, driven by config (Plainly moves onto it)

**Files:**
- Create `shared/kindle/__init__.py` (the old `shared/kindle.py`, with the import path kept), `shared/kindle/pages.py` and `shared/kindle/progress.py`.
- Create under `shared/templates/shared/kindle/`:
  - `base.html`: title `{{ app_name }}`, with `{% block head_extra %}`
  - `_masthead.html`: the wordmark is `{{ app_name }}`
  - `_pager.html`, `_account.html` and `not_found.html`
  - `reader_base.html`: its blocks are `flow_class` and `flow_body`.
    - The menu's "Text" row renders only when `reader_config.kindle.text_modes|length > 1`. Its buttons come from `text_modes` that are in `text_urls`, a dict of mode → URL supplied by the app. The current one gets `on`.
- `git mv` `kindle.js` and `kindle.css` into `shared/static/`. The only edit to `kindle.js` is that units are the `#flow` descendants carrying `data-i`, collected in an ES5 loop; `lineHeight()` still reads the first `<p>`.
- Modify:
  - `plainly/routes/kindle.py`: keeps `LIBRARY_PAGE_SIZE`, `_signed_in_user_id` and the page functions, which tests monkeypatch. The `text`/`ktext` validation and default come from `PLAINLY_READER.kindle`. `text_urls` includes `plain` only when the chapter `has_plain`, so the markup matches today's.
  - `plainly/frontend/templates/kindle/{library,book,reader}.html`
- Tests: create `tests/shared/test_kindle_shared.py`, and move `test_kindle_script_is_es5` there, retargeted at `shared/static/js/kindle.js`.

**Interfaces:**
- `shared.kindle.pages`:
  - `kindle_mode() -> bool`
  - `register_kindle_pages(bp: Blueprint, handlers: Dict[str, Callable[..., Any]], config: ReaderConfig) -> None`. It is a no-op when `not config.features.kindle`. Otherwise it installs the moved `before_app_request` dispatch (cookie remember, `handlers[endpoint](**view_args)`) and the `Vary: User-Agent, Cookie` hook.
  - `cookie_path()`, `url(path, **params)`, `page_number()`, `paginate(items, size, page) -> (items, page, pages)`, `font_size()`
  - `account_context(user_db, user_id) -> dict`
  - `render(template, user_db, user_id, **context)`
  - `saved_marker(user_db, content_db, user_id, book_id, modes: tuple[str, ...]) -> Optional[tuple[int, int, str]]`
- `shared.kindle.progress.record_page(user_db, content_db, user_id, book_id, mode, paragraph_id, quote, forward, seconds, finished) -> tuple[dict, int]`: the payload and `apply_mutation` body moved from Plainly's `save_progress`.

- [ ] **Step 1: Write the failing tests.**
  - `test_register_kindle_pages_noop_when_feature_off`: a Kindle user agent gets the web view (Review Focus 4).
  - `test_dispatches_only_in_kindle_mode`
  - `test_kindle_query_sets_cookie_on_app_path`
  - `test_vary_headers_on_kindle_endpoints`
  - `test_text_row_hidden_for_single_text_mode`
  - `test_record_page_completion_only_on_terminal_forward`
  - `test_saved_marker_ignores_unlisted_modes`
  - `test_kindle_js_collects_data_i_units`
  - the moved ES5 test
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement and rewire Plainly.**
- [ ] **Step 4: Verify.**
  - `tests/plainly/test_kindle_mode.py` is green.
  - The Kindle goldens are green.
  - The full suite is green.
  - `node kindle_mode.mjs` passes on :5002.
- [ ] **Step 5: Commit** "Extract config-driven Kindle pages, progress and assets into shared.kindle".

### Task 6: Distill block renderer, the one renderer for web and Kindle

**Files:**
- Create: `distill/render.py`, `tests/distill/test_render.py`
- Modify `distill/models.py`:
  - `_reader_chapter_units`
  - `_reader_source_checksum`
  - `get_book`, which gains `cover_image`

**Interfaces:**
- `RENDER_VERSION = 1`.
- `inline(text) -> Markup`: escape, then `**x**` → `<strong>`, `*x*` → `<em>`.
- `render_block(block) -> tuple[str, str, Markup]`, returning `(tag, class, inner)`:
  - `p` → `('p', '', …)`
  - `h` → `('h3', 'reader-section-heading', …)`
  - `quote` → `('blockquote', 'reader-quote', …)`
  - `ul`/`ol` → `('ul'|'ol', 'reader-list', '<li>…</li>\n<li>…</li>')`
  - `keypoints` → `('ul', 'reader-keypoints', …)`. The label is CSS `::before` by `:lang()`, never DOM text.
  - `table` → `('table', 'reader-table', '<thead><tr><th>…</th> <th>…</th></tr></thead> <tbody><tr><td>…</td> …</tr>\n…</tbody>')`
  - `image` → `('figure', 'reader-figure', '<img src="images/<quoted name>" alt=""> <figcaption>…</figcaption>')`. The figcaption is left out when there is no caption. The `src` is relative and resolves against `/books/<slug>/read`.
- `block_element(block, index) -> Markup`: `<tag class="…" data-i="index">inner</tag>`, used by Kindle.
- `DistillDatabase`:
  - units become `json.dumps({**block, '_render': [tag, cls, str(inner)]}, ensure_ascii=False, sort_keys=True)`
  - the checksum hashes in `RENDER_VERSION`
  - `get_book` adds `cover_image: Optional[str]`

- [ ] **Step 1: Write the failing tests.**
  - `test_dom_text_matches_block_text`, parametrised over every type in `SAMPLE_BOOK`, plus CJK `p`, a CJK table and keypoints with markup. Strip tags, unescape and normalise; the result must equal `ReaderIndexMixin._reader_normalize_quote(block_text(block))`.
  - `test_inner_has_no_paginated_block_elements`
  - `test_inline_escapes_html_then_applies_markup`
  - `test_image_src_is_relative_and_quoted`
  - `test_block_element_sets_data_i`
  - `test_units_carry_render_and_counts_unchanged`
  - `test_render_version_changes_checksum`
  - `test_get_book_cover_image_name`
- [ ] **Step 2: Run them and confirm they fail. Step 3: Implement. Step 4: Run the full suite** (with the phase 2 `test_models.py`). **Step 5: Commit** "Add Distill block renderer and render-carrying reader units".

### Task 7: Distill app core: config, factory, sign-in, allow-list and images

**Files:**
- Create: `distill/reader_config.py`, `distill/app_base.py`, `distill/app.py`, `distill/app_prod.py`, `distill/routes.py`, `distill/static/shared` (symlink to `../../shared/static`), `tests/distill/test_app.py`
- Modify `distill/config.py`:
  - env overrides `DISTILL_DB` and `DISTILL_USER_DB`
  - `PORT = int(os.environ.get('PORT', 5003))`

**Interfaces:**
- `distill/reader_config.py: DISTILL_READER = ReaderConfig(...)` with:
  - `app_name='Distill'`, `cache_db_name='distill-reader-v1'`, `cache_visibility='private'`
  - `modes=(ReaderMode('summary', 'Summary'),)`, `default_modes=('summary',)`
  - `features=ReaderFeatures(progress=True, illustrations=False, page_turn_hint=True, kindle=True)`
  - `kindle=KindleOptions((('summary', 'Summary'),), 'summary')`
  - `extra_page_blocks='table, figure.reader-figure'`
  - `hint_keys=frozenset({'reader_swipe_mobile', 'reader_nav_desktop'})`, the keys `pagination.js` uses
- `create_app(content_db=None, user_db=None, auth_config=None) -> Flask`:
  - `install_web_basics(app, 'DISTILL_STATIC_DIR_OVERRIDE')` and `install_shared_ui(app)`
  - pchauth with `auth_config` or `load_config(os.environ, prefix='DISTILL')`, or `AuthConfig(mode='off')` when `DISTILL_AUTH_MODE` is unset
  - `UserDatabase(config.USER_DATABASE_PATH, valid_hints=DISTILL_READER.hint_keys)`
  - `install_reader_platform(app, DISTILL_READER, lambda: app.config['CONTENT_DB'], user_db)`
  - registers `distill.routes.bp`
  - an `after_request` that sets `Cache-Control: private, no-cache` on every non-`/static/` response that has none yet
  - a context processor providing `base_path` and `is_development`
- `distill.routes.bp = Blueprint('distill', __name__)` with the view functions `library`, `book_page`, `reader` (Task 8) and `book_image`.
  - `GET /books/<slug>/images/<name>` (`book_image`) returns the bytes with `Cache-Control: private, max-age=3600` and an ETag (304 on a match); unknown → 404.
- `distill.app.main()` runs the dev server on `config.PORT`.
- `distill.app_prod.app` raises `RuntimeError` unless `DISTILL_AUTH_MODE == 'required'`.
- **Test fixture rule:** the `tests/distill` app fixture first monkeypatches `progress_routes.user_db`, `progress_routes.content_db` and `whoami.user_db` to their current values, so Plainly tests in the same run get them back.

- [ ] **Step 1: Write the failing tests.**
  - `test_unknown_email_gets_403_on_pages_images_and_api` (`/`, an image, a manifest)
  - `test_no_identity_gets_401_in_required_mode`
  - `test_allowed_email_reads_image_private_cache_and_304`
  - `test_reader_api_responses_are_private`
  - `test_progress_round_trip_into_distill_user_db`, with a summary-mode mutation
  - `test_page_turn_hint_key_accepted`: POST `/api/hints/reader_nav_desktop/seen` returns 200
  - `test_app_prod_refuses_without_required_mode` (subprocess)
  - `test_app_prod_imports_with_required_mode` (subprocess)
  - `test_progress_globals_restored_for_plainly`
- [ ] **Step 2: Run them and confirm they fail. Step 3: Implement. Step 4: Run the full suite. Step 5: Commit** "Add Distill app on the reader platform with allow-listed sign-in and private image route".

### Task 8: Distill web pages and reader host, plus the e2e web scenario

**Files:**
- Modify: `distill/routes.py`
- Create:
  - `distill/templates/base.html`: links `shared/css/base.css`, `shared/css/reader.css` and `css/distill.css`, has the "Distill" wordmark, and includes `_config_script.html`.
  - `distill/templates/{library,book,reader,not_found}.html`
  - `distill/static/css/distill.css`
  - `distill/static/js/distill_reader.js`
  - `tests/distill/test_pages.py`
  - `tests/e2e/distill.mjs`

**Interfaces:**
- **`GET /` → `library.html`.**
  - "Reading now" is `library_cards(user_id)['continue_reading']`, rendered with `library_card(book, cover_html, read_href=<base>/books/<slug>/read)` and the location line from `progress_label`.
  - Then "All books" from `list_books()`, newest import first, linking `/books/<slug>`.
- **`GET /books/<slug>` → `book.html`.** It shows:
  - title, author and cover
  - `progress_label` plus the percentage when the book is in progress
  - "Continue reading" or "Start reading"
  - the table of contents grouped by `part_title`, with the Overview first; links are `read?chapter=<chapter_id>`
  - sources rendered with `render_block`

  Unknown slug → 404 `not_found.html`.
- **`GET /books/<slug>/read` → `reader.html`.** It has:
  - `<html lang="{{ book.lang }}">` and `<body class="on-chapter-page on-reader-page">`
  - `_continuous_reader.html` with `reader_hidden=False`, and `_settings_panel.html`, which renders no mode section from the config
  - `window.APP_BASE_PATH` and `window.DISTILL_BOOK = {{ {id, slug, title, author}|tojson }}`
  - scripts `shared/js/base_path.js`, `shared/js/reader_state.js` and `<script type="module" src="js/distill_reader.js">`. Distill ships native ES modules with no bundle.
- **`progress_label(card, chapter_count) -> str`:**
  - `'Overview'` when `current_chapter.chapter_number == 0`
  - otherwise `f'Chapter {n} of {chapter_count}'`, where the count excludes the Overview
  - `''` with no card
- **`distill_reader.js`, the whole Distill client.** It is the two hooks and a boot:

  ```js
  import { applyReaderPlatform } from '../shared/js/platform.js';
  class DistillReader {
      continuousReaderBlock(text) { const [tag, className, content] = JSON.parse(text)._render; return { tag, className, content }; }
      selectBook(book) { location.assign(withBasePath(`/books/${book.slug}`)); }
  }
  applyReaderPlatform(DistillReader);
  ```

  Boot does: `initReaderPlatform()`, `setupReadingSettings()`, `loadReadingPreferences()`, `setupPagination()`, `window.authModule = window.readerState`, `await checkAuthStatus()`, then `showContinuousReader(window.DISTILL_BOOK, { chapter: new URLSearchParams(location.search).get('chapter') })`.
- **`distill.css`:**
  - library and book page layout
  - `.reader-keypoints::before { content: "Key points" }`, with `:lang(zh)` set to `"要点"`
  - `.reader-figure img { display: block; width: 100%; height: 40vh; object-fit: contain }`
  - `.reader-table { display: block; overflow: auto; max-height: calc(100dvh - 180px) }`
  - quote and list styling with the shared tokens

- [ ] **Step 1: Write the failing tests.** In `test_pages.py`:
  - `test_library_lists_books_newest_first`
  - `test_library_reading_now_shows_progress_label`
  - `test_book_page_toc_grouped_by_part_and_overview_first`
  - `test_book_page_sources_rendered`
  - `test_reader_shell_has_platform_partials_and_no_mode_selector`
  - `test_reader_shell_serialises_distill_config` (`"cache_db_name": "distill-reader-v1"`, one mode)
  - `test_unknown_slug_404_page`
  - `test_progress_label_cases`
- [ ] **Step 2: Write `tests/e2e/distill.mjs`.** Defaults: `BASE_URL=http://localhost:5003`, `DISTILL_SLUG=atomic-habits`, `DISTILL_ZH_SLUG=quanqiutongshi`. It exits 1 on any FAIL or console error. Desktop at 1280×900:
  - The library leads to the book page (`h1` and part headings), and the read link opens the reader with anchors visible.
  - `#reader-mode-settings` is absent or hidden.
  - Find a chapter with an image and a table through the manifest and segment API, then open `?chapter=<id>`. The `img.naturalWidth > 0`. Every `[data-reader-anchor]`'s bottom is ≤ the page bottom + 1, except `table.reader-table` (Review Focus 5). `.reader-keypoints::before` is non-empty.
  - Press ArrowRight 3 times and wait 1.5 s, note the first anchor, reload, and the first anchor is the same.
  - `/` lists the book under Reading now.
  - `indexedDB.databases()` includes `distill-reader-v1` and not `summra-reader-v2` (Review Focus 1).
  - The zh book's reader opens.
- [ ] **Step 3: Run them and confirm they fail.** Start the server with `DISTILL_USER_DB=$TMPDIR/distill_user_e2e.db PORT=5003 venv/bin/python -m distill.app`.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Verify.** pytest is green, `node distill.mjs` passes, the `screenshots/distill_*.png` look right, and the Plainly e2e set is still green.
- [ ] **Step 6: Commit** "Add Distill library, book page and reader on the shared platform".

### Task 9: Distill Kindle mode, plus the e2e Kindle scenario

**Files:**
- Create: `distill/kindle_routes.py`, `distill/templates/kindle/{library,book,reader}.html`, `distill/static/css/distill_kindle.css`, `tests/distill/test_kindle.py`
- Modify: `distill/app_base.py`, `tests/e2e/distill.mjs`

**Interfaces:**
- `register_kindle_pages(bp, {'distill.library': library_page, 'distill.book_page': book_page, 'distill.reader': reader_page}, DISTILL_READER)`.
- `library_page()`: Reading now (paginated, `LIBRARY_PAGE_SIZE = 7`), then all books paginated. No search and no tabs.
- `book_page(slug)`: part headings (`li.part`) and chapter links `read?ch=<ordinal>`, paginated at `CONTENTS_PAGE_SIZE = 8`, with Continue and "You are here" from `saved_marker(..., modes=('summary',))`.
- `reader_page(slug)`:
  - Picks the chapter from `?ch=`, otherwise the saved chapter, otherwise ordinal 0, and starts at the saved index.
  - Extends `shared/kindle/reader_base.html`, with `flow_body` = `block_element(b, i)` for each block and `text_urls={'summary': …}`, so the Text row is hidden by config.
  - Sets `data-text="summary"`, with the char counts from `block_text`, and `lang` on `<html>`.
- `POST /api/kindle/progress`: the payload is `{book_id, ch (ordinal), p, text, forward, seconds, finished}`.
  - `text` must be in `DISTILL_READER.kindle.text_modes`.
  - The handler resolves the chapter by ordinal and sets `paragraph_id = _reader_unit_id(chapter_id, p)` and `quote = normalize(block_text)[:180]`, then calls `record_page(...)`.
- `distill_kindle.css`:
  - `.flow table, .flow tr, .flow figure { -webkit-column-break-inside: avoid; break-inside: avoid }`
  - `.flow figure img { max-width: 100%; max-height: 540px }`
  - keypoints `::before`, and table borders sized for e-ink
  - No new JS.

- [ ] **Step 1: Write the failing tests** (Paperwhite user agent):
  - `test_kindle_library_reading_now_and_all_books`
  - `test_kindle_book_contents_has_part_headings_and_paginates`
  - `test_kindle_reader_renders_blocks_with_data_i`
  - `test_kindle_reader_has_no_text_row`
  - `test_kindle_reader_resumes_saved_chapter_and_index`
  - `test_kindle_progress_records_summary_marker_with_quote`
  - `test_kindle_progress_rejects_unconfigured_text`
  - `test_kindle_progress_completion_on_last_block_forward_only`
  - `test_kindle_off_switch_serves_web_pages`
- [ ] **Step 2: Extend `distill.mjs` with the Kindle UA at 758×950.**
  - `html.kindle` is present and there is no module script.
  - The contents are listed.
  - `read?ch=<ordinal with table and image>` loads `kindle.js`.
  - Every `#flow tr` and `#flow figure` has all of its client rects in one column (Review Focus 5).
  - A tap at x=700 changes `#right`.
  - No console errors.
- [ ] **Step 3: Run them and confirm they fail. Step 4: Implement. Step 5: Verify.** pytest, `distill.mjs` and Plainly's `kindle_mode.mjs` all pass.
- [ ] **Step 6: Commit** "Add Distill Kindle mode on the shared platform".

### Task 10: Docs and work log

**Files:**
- Modify: `docs/PRD.md`, `docs/ERD.md`, `WORK_LOG.md`, `CLAUDE.md` (Frontend Test Loop: the Distill server on 5003 and `distill.mjs`), `tests/e2e/README.md`

- [ ] **Step 1: PRD.** Add a "Distill" section covering:
  - owner-only access through the allow-list
  - library with Reading now, book page
  - the single-mode reader, with no selector
  - saved place, and progress as "Chapter n of m" or "Overview"
  - Kindle mode
  - the spec §3 non-goals
- [ ] **Step 2: ERD, "Reader platform".** Cover:
  - **Config fields:** every `ReaderConfig`, `ReaderMode`, `ReaderMember`, `ReaderFeatures`, `ReaderSettings` and `KindleOptions` field and what it drives (templates, blueprint, JS, Kindle).
  - **The mode registry:** `ALL_MODES` as storage vocabulary, pinned to the schema `CHECK`s.
  - **Plug-in surface:** the two JS hooks and the platform defaults.
  - **Serving:** the symlink scheme, with the Apache `+FollowSymLinks` requirement (Plainly's next deploy must reinstall `deploy/apache/summra.conf`), and esbuild bundling.
  - **"Adding a third app":**
    1. Write the content DB with the `ReaderIndexMixin` and library hooks.
    2. Declare a `ReaderConfig` with a unique `cache_db_name`.
    3. Call `install_reader_platform`.
    4. Add the `static/shared` symlink.
    5. Write the host class with the two hooks.
    6. Add the Kindle handlers, if Kindle is enabled.
    7. Add an e2e script.
  - **The Plainly-only reader code left in shared:** the legacy chapter-page branches in `pagination.js` and `settings.js`.
- [ ] **Step 3: ERD, "Distill app".** Cover routes, auth env, the two DBs, the renderer, `_render` units and `RENDER_VERSION`. Include this note: **re-import keeps chapter ids by ordinal, so a chapter inserted mid-book shifts content under existing ids.** Quote recovery runs only within the marker's chapter.
- [ ] **Step 4: WORK_LOG.** Add the phase 3 summary, the final pytest count, the e2e scripts run and the single-mode-book count from Task 3.
- [ ] **Step 5: Run the full verification once more, then commit** "Document the reader platform and Distill web app".
