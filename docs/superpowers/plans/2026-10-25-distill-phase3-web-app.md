# Distill Phase 3 — Shared Reader Extraction and Distill Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Plainly's web reader, its reader CSS and templates, and its Kindle reader into `shared/` without changing Plainly's behaviour. Then build the signed-in Distill app at `/distill` (library, book page, reader, saved place, progress, Kindle mode) on top of those same pieces.

**Architecture:**
- **Reader code stays Plainly's code, moved as it is.** The reader mixins (`pagination.js` and `settings.js` whole, plus the continuous-reader half of `reader.js`) move to `shared/static/js/`. Each one stays a plain object of methods with no `import`, so a host class can `Object.assign` it. That is how `app.js` already works.
- **Each app is a host.** The host supplies a short list of methods (the host contract, Task 3). Plainly's host is its existing `SummraApp`. Distill's host is a class of about 40 lines in `distill/static/js/distill_reader.js`.
- **Distill bends its data to fit the reader.** Each segment unit already carries the block JSON, and Distill adds the block's server-rendered HTML to it. One Python renderer (`distill/render.py`) produces that HTML for both the web reader and the Kindle pages. The reader core needs no Distill branches.
- **How shared static files and templates are served.** Each app's static folder gets a committed symlink, `static/shared → <repo>/shared/static`. The files are then at `/static/shared/...` under each app's own prefix, so relative ES-module imports work in dev and esbuild bundles them for Plainly's `app.min.js`. Shared templates live under `shared/templates/shared/` and reach each app's Jinja through a `ChoiceLoader`.
- **Distill** is a small Flask app factory (`distill/app_base.py:create_app`). It uses pchauth with prefix `DISTILL`, `shared.progress` with `data/distill_user.db`, the shared reader-API blueprint factory and the shared Kindle helpers.

**Tech Stack:** Python 3.11, Flask, Jinja2, SQLite, vanilla ES modules (esbuild bundle for Plainly only), ES5 for Kindle, pytest, Playwright (`tests/e2e/*.mjs`), `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-24-distill-design.md`: §5.7 (web app, shared reader, sign-in), §5.2 and §5.3 (blocks, units), §5.8 (deploy shape only) and §5.9 (phase 3). Phase 2 is done: `distill/models.py` (`DistillDatabase`) and `distill/book_format.py`. Local `data/distill.db` holds 4 real books (`atomic-habits`, `the-goal`, `guns-germs-and-steel`, `quanqiutongshi`).

## Global Constraints

- **Plainly behaviour must not change.** Before and after every task in Tasks 1–5:
  - the full pytest suite is green (902 tests collected at plan time)
  - `npm run build:check` passes
  - the Plainly e2e set is green: `smoke`, `kindle_mode`, `reader_progress`, `reader_themes`, `reader_last_line_visible`, `reader_opens_at_chapter`, `reader_segments_fast_open`, `reader_illustrations`, `reader_font_figtree`, `reader_nav_mouse`, `sxs_row_split`, `text_size_adjust`, `redesign_home`, `redesign_reader`
  - the reader style snapshot (Task 1) compares equal
- **Moved code stays as it is.** Only the named parameterisations are allowed. Do not write a new reader, pagination, position, settings or page-turn logic for Distill.
- **Moving a test.** When a test only moves because the file it reads moved, copy its assertions word for word and change only the path. Say so in the commit body.
- `shared/` imports nothing from `plainly` or `distill`. The guard is `tests/shared/test_layering.py`. Files under `shared/static` and `shared/templates` contain neither the word "Plainly" nor "Distill".
- Shared JS mixin files have no `import`/`export` other than their exported objects and functions, because tests load them from a `data:` URL.
- Distill serves at `/distill` behind Apache OIDC.
  - Env prefix `DISTILL_`: `DISTILL_AUTH_MODE`, `DISTILL_ALLOWED_EMAILS`.
  - Local dev defaults to pchauth mode `off`, like Plainly.
  - `distill.app_prod` refuses to start unless `DISTILL_AUTH_MODE=required`.
- **Distill content is private.** No route, static path or cache header may make book text or images publicly cacheable. Reader API responses use `Cache-Control: private`.
- Distill's dev server runs on port **5003** (`PORT` env). In this worktree, Plainly runs on **5002**.
- Kindle pages are server-rendered. `kindle.js` stays ES5.
- Day-one features only: library (with Reading now), book page, reader, saved place, progress and Kindle mode. No search, no mode switch, no audio.
- No VM, Apache-on-VM or systemd work (that is phase 4). `distill.app_prod:app` must import cleanly, and `deploy/gunicorn_config.py` (already driven by env vars) is its gunicorn config.
- TDD: write the failing test first. A pure move instead gets a characterization test that is written first and is green before and after. Each commit body carries the pytest pass count. Each task adds its `WORK_LOG.md` entry in its own commit.

## Review Focus

1. **Two apps on one origin share browser storage.** IndexedDB `summra-reader-v2` caches manifests and segments by `book_id`, and Distill's ids collide with Plainly's. A Distill reader offline could then render a Plainly book.
   - Task 3 adds a `window.READER_CACHE_DB` parameter.
   - Task 8's e2e asserts Distill opens `distill-reader-v1` and never `summra-reader-v2`.
2. **Private content gets cached as public.** Plainly's reader routes send `public, immutable`.
   - Task 2's factory takes `cache_visibility`.
   - Task 7 asserts that every Distill manifest, segment and image response says `private`.
3. **Prod starts without auth, or a signed-in stranger reads.**
   - Task 7 tests that `app_prod` raises without `DISTILL_AUTH_MODE=required`.
   - It also tests that an email not on the allow-list gets 403 on `/`, on a book image and on a segment.
4. **A table, figure or list taller than a page.** The web paginator only splits `<p>`, and Kindle columns can cut a row.
   - Task 8's e2e asserts that no anchored block overflows its page, except a table, which scrolls inside itself.
   - Task 9's e2e asserts that no `tr` or `figure` spans two Kindle columns.
5. **The rendered DOM text drifts from `block_text`.** Missing whitespace between `<li>`/`<td>`, markup leftovers or CJK would break quote recovery after a re-import.
   - Task 6 asserts, for every block type including CJK, that the whitespace-normalised text of the rendered HTML equals the normalised `block_text`.
   - Task 8's e2e asserts that a reload restores the same anchor.

---

## File map

**shared/** (new unless noted)
- `static/js/base_path.js`: `summraBasePath`, `withBasePath`, moved out of `plainly/.../route_utils.js`
- `static/js/reader_utils.js`: `readerUtilsMixin = { escapeHtml }`, moved out of `app.js`
- `static/js/pagination.js`: moved whole, adds `createPaginationState()`
- `static/js/settings.js`: moved whole
- `static/js/continuous_reader.js`: the continuous-reader methods moved out of `plainly/.../reader.js`
- `static/js/reader_state.js`: the reader-state half of `plainly/.../auth.js`
- `static/js/kindle.js`: moved
- `static/css/base.css`, `static/css/reader.css`, `static/css/kindle.css` (moved), `static/fonts/figtree-*.woff2` (moved)
- `templates/shared/reader/_continuous_reader.html` and `_settings_panel.html`
- `templates/shared/_library_card.html`
- `templates/shared/kindle/{base,_masthead,_pager,_account,not_found,reader_base}.html`
- `reader/routes.py`, plus `kindle/__init__.py` (was `shared/kindle.py`), `kindle/pages.py` and `kindle/progress.py`
- `web.py` (modify): `install_shared_ui(app)`

**plainly/** (modify): `frontend/static/shared` (new symlink), the JS files `app.js`, `reader.js`, `auth.js`, `route_utils.js` and `app.min.js`, `css/style.css`, `templates/index.html`, `_book_card.html`, `templates/kindle/{library,book,reader}.html` (the other Kindle templates are deleted), `routes/books.py`, `routes/kindle.py`, `app_base.py`.

**distill/** (new): `render.py`, `app_base.py`, `app.py`, `app_prod.py`, `routes.py`, `kindle_routes.py`, `templates/{base,library,book,reader,not_found}.html`, `templates/kindle/{library,book,reader}.html`, `static/shared` (symlink), `static/css/distill.css`, `static/css/distill_kindle.css`, `static/js/distill_reader.js`. Modify: `config.py`, `models.py`.

**tests/**:
- `tests/shared/`: `test_shared_ui.py`, `test_reader_routes.py`, `test_shared_js.py`, `test_kindle_shared.py`
- `tests/plainly/`: `test_reader_shell_markup.py` plus golden files
- `tests/distill/`: `test_render.py`, `test_app.py`, `test_pages.py`, `test_kindle.py`
- `tests/js/`: `base_path.test.mjs`, `mixins_disjoint.test.mjs`
- `tests/e2e/`: `reader_style_snapshot.mjs`, `distill.mjs`

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

### Task 2: Shared reader API blueprint

**Files:**
- Create: `shared/reader/routes.py`, `tests/shared/test_reader_routes.py`
- Modify: `plainly/routes/books.py` (delete the four `/api/reader/books/...` handlers), `plainly/app_base.py`

**Interfaces:**
- Produces: `make_reader_blueprint(get_content_db: Callable[[], Any], cache_visibility: str = 'public') -> Blueprint`. It registers:
  - `GET /api/reader/books/<int:book_id>/manifest`
  - `GET /api/reader/books/<int:book_id>/segments/<segment_id>`
  - `POST /api/reader/books/<int:book_id>/map`
  - `POST /api/reader/books/<int:book_id>/recover`

  The bodies, ETags and error JSON are moved verbatim. The manifest's `Cache-Control` is `f'{cache_visibility}, max-age=300, must-revalidate'` and the segment's is `f'{cache_visibility}, max-age=31536000, immutable'`. The content DB is looked up per request through `get_content_db()`, so tests that monkeypatch `plainly.routes.common.db` keep working.
- Plainly: `app.register_blueprint(make_reader_blueprint(lambda: common.db))`.

- [ ] **Step 1: Write the failing tests.** Use a fake content DB with `get_reader_manifest`, `get_reader_segment`, `map_reader_marker` and `recover_reader_marker`:
  - `test_manifest_etag_and_public_cache_by_default`
  - `test_private_visibility_marks_manifest_and_segment_private`, which asserts `'private' in cache_control` and `'public' not in`
  - `test_segment_404_json_on_unknown`
  - `test_map_requires_marker_400`
  - `test_recover_404_when_unrecoverable`
  - `test_db_resolved_per_request`, which swaps the getter's target between two requests
- [ ] **Step 2: Run them and confirm they fail** (ModuleNotFoundError).
- [ ] **Step 3: Implement. Run the full suite.** `tests/plainly/test_api_routes_characterization.py` must stay green.
- [ ] **Step 4: Commit** "Move reader API routes into shared.reader blueprint factory".

### Task 3: Shared web reader JS (Plainly moves onto it)

**Files:**
- Create the following under `shared/static/js/`:
  - `base_path.js`: `summraBasePath` and `withBasePath`, cut from `route_utils.js`. It is a classic script setting `window.*`, wrapped in the same IIFE.
  - `reader_utils.js`: `export const readerUtilsMixin = { escapeHtml }`, cut from `app.js`.
  - `pagination.js`: `git mv` from Plainly. It adds `export function createPaginationState()`, which returns the exact object literal now in `SummraApp`'s constructor (`enabled: true, currentPage: 0, totalPages: 0, pages: [], containerHeight: 0, isNavigating: false, currentViewMode: 'original'`).
  - `settings.js`: `git mv`.
  - `continuous_reader.js`: `export const continuousReaderMixin`, holding these methods cut from `plainly/.../reader.js`, unchanged:
    - `showContinuousReader`, `readerSkeletonHtml`, `resolveReaderChapter`
    - `isContinuousReaderModeAvailable`, `switchContinuousReaderMode`, `enforceContinuousReaderViewport`
    - `loadContinuousReaderAt`, `findContinuousSegmentForChapter`, `fetchContinuousSegment`
    - `illustrationSources`, `continuousIllustrationHtml`
    - `renderContinuousSegments`, `findContinuousPageForChapter`, `findContinuousPageForMarker`
    - `settleContinuousReaderMarker`, `continuousMarkerOffset`, `continuousMarkerWordPosition`
    - `setupContinuousReaderChrome`, `setupContinuousReaderLifecycle`, `toggleContinuousPanel`
    - `mapContinuousMarker`, `recoverContinuousMarker`, `onContinuousPageDisplayed`
    - `saveContinuousReader`, `updateContinuousReaderProgress`, `setContinuousReaderStatus`, `navigateContinuousSegment`
  - `reader_state.js`: these functions, cut from `auth.js`, set `window.readerState`:
    - `randomId`, `requestPromise`, `transactionPromise`, `readerDb`
    - `queueReaderMutation`, `getReaderState`, `getLibrary`
    - the four cache functions
    - `checkAuthStatus`, `hintSeen`, `markHintSeen`
    - `currentUser()`, `wrongAccountEmail()`

    `readerDb()` opens `window.READER_CACHE_DB || 'summra-reader-v2'`.
- Modify `plainly/frontend/static/js/`:
  - `app.js`: imports from `'../shared/js/…'`; `this.pagination = createPaginationState()`; `escapeHtml` removed; `Object.assign(SummraApp.prototype, readerUtilsMixin, paginationMixin, settingsMixin, continuousReaderMixin, breadcrumbsMixin, audioMixin, readerMixin)`.
  - `reader.js`: keeps the legacy chapter and medium pages, `renderMarkdown`, `formatChapterText`, `formatSideBySideText`, `renderLibraryCards`, `showLibrary`, `markReaderBookUnfinished`, `loadContinuousAbout`, `formatContinuousReaderText` and `continuousReaderBlock`.
  - `auth.js`: keeps the modal and UI. `initAuth` = `readerState.checkAuthStatus()` plus its listeners and `updateAuthUI`. `window.authModule = { ...window.readerState, initAuth, trackChapterView, trackPageChange, onChapterComplete }`.
  - `route_utils.js`: rebuild `app.min.js`.
- Modify: `plainly/frontend/templates/index.html`. Load `shared/js/base_path.js` before `route_utils.js`, and `shared/js/reader_state.js` before `auth.js`.
- Tests:
  - Create `tests/shared/test_shared_js.py`. It receives the moved `test_continuation_segments_do_not_repeat_chapter_heading`, pointed at `shared/static/js/continuous_reader.js` and importing `continuousReaderMixin`.
  - Create `tests/js/base_path.test.mjs`, which receives `route_utils.test.mjs`'s `withBasePath`/`summraBasePath` tests word for word.
  - Create `tests/js/mixins_disjoint.test.mjs`.

**Interfaces:**
- Produces the **host contract**. A host class must provide these. Plainly already has all of them.
  - `this.apiBase: string` (`withBasePath('/api')`)
  - `this.pagination` (`createPaginationState()`)
  - `continuousReaderBlock(text: string) -> {tag: string, className: string, content: string}`: the unit body renderer. The content must not contain an element matched by the paginator's block selector.
  - `selectBook(book)`: the back button target
  - `showOnlySections(id)`
  - `paginationExtraBlocks: string`, a CSS selector list appended to the regular-mode block selector in `calculatePages`. The default is `''`. This is the only edit to pagination logic.
  - Globals: `window.withBasePath` and `window.authModule` (the `readerState` surface)
- Produces: `window.readerState = { checkAuthStatus, currentUser, wrongAccountEmail, queueReaderMutation, getReaderState, getLibrary, hintSeen, markHintSeen, cacheReaderManifest, getCachedReaderManifest, cacheReaderSegment, getCachedReaderSegment }`.

- [ ] **Step 1: Write the failing tests.**
  - `mixins_disjoint.test.mjs`: imports `readerUtilsMixin`, `paginationMixin`, `settingsMixin` and `continuousReaderMixin` from `shared/static/js`, and `readerMixin` from Plainly. It asserts there are no shared keys between any two of them.
  - `test_shared_js.py::test_reader_state_cache_db_name_is_parameterised`: runs Node with a stub `indexedDB.open` that records the name. Loading `reader_state.js` with `READER_CACHE_DB='distill-reader-v1'` and calling `getCachedReaderManifest(1)` records `'distill-reader-v1'`; without it, `'summra-reader-v2'`.
  - `test_shared_js.py::test_pagination_extra_blocks_selector`: in Node, a stub container's `querySelectorAll` receives a selector ending in `, table` when `paginationExtraBlocks = 'table'`, and the original selector exactly when it is `''`.
  - The moved tests above.
- [ ] **Step 2: Run them and confirm they fail.** Command: `node --test tests/js/ && venv/bin/pytest tests/shared/test_shared_js.py -v`. Expect missing modules.
- [ ] **Step 3: Move and wire.** Use `git mv` for whole files and plain cut/paste for the method moves. Make the `paginationExtraBlocks` and `READER_CACHE_DB` edits. Then run `npm run build`.
- [ ] **Step 4: Verify.**
  - `node --test tests/js/` passes.
  - `venv/bin/pytest tests/ -q` is green.
  - `npm run build:check` passes.
  - `MODE=compare` reports no differences.
  - The Global Constraints e2e set is green against `:5002`.
- [ ] **Step 5: Commit** "Extract web reader mixins into shared/static/js; Plainly hosts them".

### Task 4: Shared reader CSS and templates (Plainly moves onto them)

**Files:**
- Create the following under `shared/static/css/`, cut from `plainly/.../style.css` by section-comment boundaries:
  - `base.css`: everything before `/* Header */`, which is the Figtree `@font-face`, the reset and `:root` tokens. Font URLs point to `../fonts/`, and the fonts move with `git mv` to `shared/static/fonts/`.
  - `reader.css`: the sections `Reading Settings Panel`, `Font Selection`, `Text Size Control`, `Theme Selection`, `Font family for pagination containers`, and everything from `PAGINATION SYSTEM FOR CHAPTER READING` through the end of `Continuous Reader and Library` (just before `===== User Account Modal =====`).
- Create these partials under `shared/templates/shared/`, cut from `index.html`:
  - `reader/_continuous_reader.html`: the `#continuous-reader-section` markup. It takes `reader_hidden: bool`.
  - `reader/_settings_panel.html`: `#reading-settings-panel`. It takes `reader_modes: list[tuple[str, str]]`, and the mode section renders only if that list is non-empty.
  - `_library_card.html`: the macro `library_card(book, cover_html, mode_label=None, read_href=None)`. With `read_href` set, the action is an `<a class="library-read-action" href>`; otherwise it is today's `<button data-library-read>`.
- Modify:
  - `plainly/frontend/templates/index.html`: link `shared/css/base.css` before `style.css` and `shared/css/reader.css` after it; include the partials, passing Plainly's four modes.
  - `plainly/frontend/templates/_book_card.html`: `library_card(book)` wraps the shared macro with `book_cover(book)` and the mode label map.
  - `plainly/frontend/static/css/style.css`

**Interfaces:**
- Produces: the partial names and parameters above, and the CSS files `shared/css/{base,reader}.css`.

- [ ] **Step 1: Confirm the baselines are green on the current code.** Run `test_reader_shell_markup.py` and `MODE=compare`. These are the characterization tests for this move.
- [ ] **Step 2: Move the CSS and markup.**
- [ ] **Step 3: Verify.**
  - `MODE=compare` shows no differences. If a value changed, a later rule in `style.css` used to override a moved rule, so move that overriding rule into `reader.css` after the rule it overrides, then run `compare` again.
  - `test_reader_shell_markup.py` is green.
  - The full pytest suite is green.
  - The e2e set is green.
  - `test_response_compression`'s `/static/css/style.css` still gzips.
- [ ] **Step 4: Commit** "Extract reader CSS, fonts and reader templates into shared".

### Task 5: Shared Kindle reader (Plainly moves onto it)

**Files:**
- Create:
  - `shared/kindle/__init__.py`: the old contents of `shared/kindle.py`, with `is_kindle_user_agent` still importable from `shared.kindle`.
  - `shared/kindle/pages.py`
  - `shared/kindle/progress.py`
  - `shared/templates/shared/kindle/`:
    - `base.html`: has `{% block head_extra %}`; the default title is `{{ app_name }}`; CSS comes from `shared/css/kindle.css`.
    - `_masthead.html`: the wordmark is `{{ app_name }}`.
    - `_pager.html`, `_account.html` and `not_found.html`: moved.
    - `reader_base.html`: runhead, viewport, flow, chapter-end, foot and menu. Its blocks are `flow_class`, `flow_body` and `menu_text_row`.
  - `git mv` `kindle.js` and `kindle.css` into `shared/static/`.
- Modify:
  - `plainly/routes/kindle.py`: keeps `LIBRARY_PAGE_SIZE`, `_signed_in_user_id` and its page functions, because tests monkeypatch them, and calls the shared helpers.
  - `plainly/frontend/templates/kindle/{library,book,reader}.html`: these now extend the shared templates. Delete the moved partials.
- Modify `shared/static/js/kindle.js` only as follows:
  - Units are the descendants of `#flow` with a `data-i` attribute, collected in an ES5 loop over `flow.getElementsByTagName('*')`, instead of every `<p>`.
  - `lineHeight()` keeps reading `flow.getElementsByTagName('p')[0]`.
- Tests: create `tests/shared/test_kindle_shared.py`, and move `test_kindle_script_is_es5` out of `tests/plainly/test_kindle_mode.py`, with its path changed to `shared/static/js/kindle.js`.

**Interfaces:**
- Produces in `shared.kindle.pages`:
  - `kindle_mode() -> bool`
  - `register_kindle_pages(bp: Blueprint, handlers: Dict[str, Callable[..., Any]]) -> None`. It installs the `before_app_request` dispatch, which remembers the `?kindle=` cookie and calls `handlers[endpoint](**view_args)` when `kindle_mode()`. It also installs the `after_app_request` `Vary: User-Agent, Cookie`. Both are moved from Plainly.
  - `cookie_path() -> str`, `url(path, **params) -> str`, `page_number() -> int`, `paginate(items, size, page) -> (items, page, pages)`, `font_size() -> int` (`FONT_SIZES = range(1, 6)`, `DEFAULT_FONT_SIZE = 3`)
  - `account_context(user_db, user_id) -> dict`
  - `render(template: str, user_db, user_id, **context) -> (html, 200, headers)`
  - `saved_marker(user_db, content_db, user_id, book_id, modes: tuple[str, ...]) -> Optional[tuple[int, int, str]]` returns `(chapter_id, index, mode)` from the account projection's last mode, recovered through `recover_reader_marker`.
- Produces in `shared.kindle.progress`:
  - `record_page(user_db, content_db, user_id, book_id, mode, paragraph_id, quote, forward: bool, seconds, finished: bool) -> tuple[dict, int]`. This is the mutation-payload and `apply_mutation` body moved from Plainly's `save_progress`, unchanged, and it returns `({'success': True, 'result': ...}, 200|409)`.

- [ ] **Step 1: Write the failing tests** in `test_kindle_shared.py`, against a tiny Flask app with a fake content and user DB:
  - `test_register_kindle_pages_dispatches_only_in_kindle_mode`
  - `test_kindle_query_sets_cookie_on_app_path`
  - `test_vary_headers_on_kindle_endpoints`
  - `test_paginate_clamps_page`
  - `test_record_page_completion_only_on_terminal_forward`
  - `test_saved_marker_ignores_modes_not_listed`
  - `test_kindle_js_collects_data_i_units`, a static check that the source no longer assigns `getElementsByTagName('p')` to the unit list
  - the moved ES5 test
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement and move. Rewire Plainly.**
- [ ] **Step 4: Verify.**
  - All 35 `tests/plainly/test_kindle_mode.py` tests pass (34 there plus the moved one).
  - `test_kindle_pages_markup_unchanged` is green.
  - The full suite is green.
  - `BASE_URL=http://localhost:5002 node kindle_mode.mjs` passes.
- [ ] **Step 5: Commit** "Extract Kindle pages, progress and assets into shared.kindle".

### Task 6: Distill block renderer, the one renderer for web and Kindle

**Files:**
- Create: `distill/render.py`, `tests/distill/test_render.py`
- Modify: `distill/models.py`, where `_reader_chapter_units` and `_reader_source_checksum` change and `get_book` gains `cover_image`

**Interfaces:**
- Produces in `distill.render`:
  - `RENDER_VERSION = 1`
  - `inline(text: str) -> Markup`: escape, then `**x**` → `<strong>x</strong>` and `*x*` → `<em>x</em>`.
  - `render_block(block: dict) -> tuple[str, str, Markup]`, returning `(tag, class_name, inner_html)`:
    - `p` → `('p', '', …)`
    - `h` → `('h3', 'reader-section-heading', …)`
    - `quote` → `('blockquote', 'reader-quote', …)`
    - `ul`/`ol` → `('ul'|'ol', 'reader-list', '<li>…</li>\n<li>…</li>')`
    - `keypoints` → `('ul', 'reader-keypoints', items as for ul)`. The "Key points" label is CSS `::before` text keyed by `:lang()`, never DOM text.
    - `table` → `('table', 'reader-table', '<thead><tr><th>…</th> <th>…</th></tr></thead> <tbody><tr><td>…</td> …</tr>\n…</tbody>')`
    - `image` → `('figure', 'reader-figure', '<img src="images/<name>" alt=""> <figcaption>…</figcaption>')`. The figcaption is left out when there is no caption. The `src` is relative and resolves against `/books/<slug>/read` to the image route. `<name>` is `src` without the `images/` prefix, URL-quoted.
  - `block_element(block: dict, index: int) -> Markup` returns `<tag class="…" data-i="index">inner</tag>`, for Kindle.
- Changes to `DistillDatabase`:
  - `_reader_chapter_units` emits `json.dumps({**block, '_render': [tag, cls, str(inner)]}, ensure_ascii=False, sort_keys=True)`.
  - `_reader_source_checksum` adds `RENDER_VERSION` to the hashed source, so a renderer change bumps the reader version and invalidates cached segments.
  - `_unit_visible_text` keeps using `block_text`, which ignores `_render`.
  - `get_book` returns `cover_image: Optional[str]`, the image name of `cover_image_id`.

- [ ] **Step 1: Write the failing tests.**
  - `test_dom_text_matches_block_text`, parametrised over every block type in `tests/distill/conftest.py:SAMPLE_BOOK`, plus a CJK `p`, a CJK table and a keypoints block with markup. For each: strip the tags from `inner`, `html.unescape`, collapse whitespace, lowercase. The result must equal `ReaderIndexMixin._reader_normalize_quote(block_text(block))`.
  - `test_inner_has_no_paginated_block_elements`: no `<p`, `<h`, `<ul`, `<ol`, `<blockquote`, `<pre`, `<table`, `<figure` inside `inner`, except the list tag for its own items.
  - `test_inline_escapes_html_then_applies_markup` (`'<b>x</b> **y**'`)
  - `test_image_src_is_relative_and_quoted`
  - `test_block_element_sets_data_i`
  - `test_units_carry_render_and_counts_unchanged`: the word counts from Phase 2's tests are unchanged.
  - `test_render_version_changes_checksum`
  - `test_get_book_cover_image_name`
- [ ] **Step 2: Run them and confirm they fail.** Command: `venv/bin/pytest tests/distill/test_render.py -v`.
- [ ] **Step 3: Implement. Run the full suite**, including the Phase 2 `tests/distill/test_models.py` tests.
- [ ] **Step 4: Commit** "Add Distill block renderer and render-carrying reader units".

### Task 7: Distill app core: factory, sign-in, allow-list, API and images

**Files:**
- Create: `distill/app_base.py`, `distill/app.py`, `distill/app_prod.py`, `distill/routes.py` (the image route here; pages come in Task 8), `distill/static/shared` (symlink to `../../shared/static`), `tests/distill/test_app.py`
- Modify: `distill/config.py`. It adds `DATABASE_PATH` and `USER_DATABASE_PATH` overrides from the `DISTILL_DB` and `DISTILL_USER_DB` env vars, `PORT = int(os.environ.get('PORT', 5003))`, and `READER_CACHE_DB = 'distill-reader-v1'`.

**Interfaces:**
- Produces: `create_app(content_db: Optional[DistillDatabase] = None, user_db: Optional[UserDatabase] = None, auth_config: Optional[AuthConfig] = None) -> Flask`. It:
  - sets `static_folder='static'`, `template_folder='templates'`
  - calls `install_web_basics(app, 'DISTILL_STATIC_DIR_OVERRIDE')` and `install_shared_ui(app)`
  - uses `auth_config`, defaulting to `load_config(os.environ, prefix='DISTILL')` when `DISTILL_AUTH_MODE` is set and `AuthConfig(mode='off')` otherwise
  - calls `init_pchauth(app, auth_config, upsert_user=…)`
  - sets `progress_routes.user_db` and `progress_routes.content_db`, plus `whoami.user_db`
  - registers `progress_bp`, `whoami_bp`, `make_reader_blueprint(lambda: app.config['CONTENT_DB'], cache_visibility='private')` and `distill.routes.bp`
  - adds an `after_request` that sets `Cache-Control: private, no-cache` on every non-`/static/` response that has no Cache-Control yet
  - adds a context processor providing `app_name='Distill'`, `base_path`, `reader_cache_db` and `is_development`
- Produces: `distill.routes.bp = Blueprint('distill', __name__)`. Its view functions are named `library`, `book_page`, `reader` (Task 8) and `book_image`, so the endpoints are `distill.library`, `distill.book_page`, `distill.reader` and `distill.book_image`.
- Produces: `GET /books/<slug>/images/<name>` (`book_image`) → `send` bytes with `mimetype`. Headers are `Cache-Control: private, max-age=3600` and an ETag over the bytes, so `If-None-Match` gets a 304. Unknown → 404.
- `distill.app.main()` runs the dev server on `config.PORT`, with `IS_DEVELOPMENT=True`.
- `distill.app_prod.app = create_app()`. It raises `RuntimeError` unless `os.environ.get('DISTILL_AUTH_MODE') == 'required'`.
- **Test fixture rule:** `create_app` writes into module globals (`progress_routes`, `whoami`). The `tests/distill` `app` fixture must first `monkeypatch.setattr` each of those globals to its current value, so Plainly tests in the same pytest run see their own values again afterwards.

- [ ] **Step 1: Write the failing tests.** Build the book from `write_book(sample_book)` in a temporary DB.
  - `test_unknown_email_gets_403_on_pages_images_and_api`: mode required, allowed `owner@example.com`, header `X-Remote-Email: other@example.com`. Paths: `/`, `/books/my-book/images/cover.jpg` and `/api/reader/books/<id>/manifest`.
  - `test_no_identity_gets_401_in_required_mode`
  - `test_allowed_email_reads_image_private_cache_and_304`
  - `test_reader_api_responses_are_private` (manifest and segment)
  - `test_progress_round_trip_into_distill_user_db`: POST `/api/progress/v2/mutations` with a summary-mode marker, GET `/api/progress/v2/books/<id>`, and assert the row is in the user DB file passed to `create_app`.
  - `test_app_prod_refuses_without_required_mode`: import in a subprocess with a clean env; it should exit non-zero with "DISTILL_AUTH_MODE".
  - `test_app_prod_imports_with_required_mode` (subprocess, with env set and `DISTILL_DB` pointed at a temp DB)
  - `test_progress_globals_restored_for_plainly`: after the fixture, `shared.progress.routes.content_db` is the object it was before.
- [ ] **Step 2: Run them and confirm they fail.** **Step 3: Implement.** **Step 4: Run the full suite.**
- [ ] **Step 5: Commit** "Add Distill app factory with allow-listed sign-in, private reader API and image route".

### Task 8: Distill web pages and reader host, plus the e2e web scenario

**Files:**
- Modify: `distill/routes.py`
- Create:
  - `distill/templates/base.html`: links `shared/css/base.css`, `shared/css/reader.css` and `css/distill.css`, and has a masthead with the "Distill" wordmark.
  - `distill/templates/library.html`, `book.html`, `reader.html` and `not_found.html`
  - `distill/static/css/distill.css`
  - `distill/static/js/distill_reader.js`
  - `tests/distill/test_pages.py`, `tests/e2e/distill.mjs`

**Interfaces:**
- Consumes: Task 3's host contract and mixins, Task 4's partials, Task 6's `_render` units, Task 7's `create_app`, and `shared.progress.routes.library_cards`.
- Produces these routes:
  - `GET /` → `library.html`. "Reading now" lists `library_cards(user_id)['continue_reading']` as `library_card(book, cover_html, mode_label=None, read_href=<base>/books/<slug>/read)`, with the location line from `progress_label`. Below that, "All books" comes from `list_books()` (newest import first), each linking `/books/<slug>`. Both sections show the cover image when there is one.
  - `GET /books/<slug>` → `book.html` shows:
    - title, author and cover
    - progress (`progress_label` plus the percentage, when the book is in `library_cards`)
    - a primary link, "Continue reading" or "Start reading", to `/books/<slug>/read`
    - a table of contents grouped by `part_title`, with each chapter linking `/books/<slug>/read?chapter=<chapter_id>` (the Overview first, with no part)
    - sources rendered with `render_block`

    An unknown slug gives 404 with `not_found.html`.
  - `GET /books/<slug>/read` → `reader.html`:
    - `<html lang="{{ book.lang }}">`
    - `<body class="on-chapter-page on-reader-page">`
    - the shared continuous-reader partial with `reader_hidden=False`, and the settings partial with `reader_modes=[]`
    - inline `window.APP_BASE_PATH`, `window.READER_CACHE_DB` and `window.DISTILL_BOOK = {{ {id, slug, title, author}|tojson }}`
    - scripts `shared/js/base_path.js`, `shared/js/reader_state.js` and `<script type="module" src="js/distill_reader.js">`. Distill ships native ES modules with no bundle; the Kindle path is separate.
  - `progress_label(card: Optional[dict], chapter_count: int) -> str`, in `distill/routes.py`:
    - `'Overview'` when `card.current_chapter.chapter_number == 0`
    - otherwise `f'Chapter {n} of {chapter_count}'`, where `chapter_count` excludes the Overview
    - `''` with no card
- Produces in `distill_reader.js`: a `DistillReader` host. Its constructor sets `apiBase`, `pagination = createPaginationState()` and `paginationExtraBlocks = 'table, figure.reader-figure'`. Its methods:
  - `continuousReaderBlock(text)`: `const [tag, className, content] = JSON.parse(text)._render; return {tag, className, content};`
  - `selectBook(book)`: `location.assign(withBasePath('/books/' + book.slug))`
  - `showOnlySections() {}`

  The mixins applied are readerUtils, pagination, settings and continuousReader. On boot it calls `setupReadingSettings`, `loadReadingPreferences` and `setupPagination`, sets `window.authModule = window.readerState`, awaits `checkAuthStatus()`, then calls `showContinuousReader(window.DISTILL_BOOK, {chapter: new URLSearchParams(location.search).get('chapter')})`.

  It contains no other logic.
- `distill.css` holds:
  - the library and book page layout
  - `.reader-keypoints::before { content: "Key points" }`, with `:lang(zh)` set to `"要点"`
  - `.reader-figure img { display:block; width:100%; height: 40vh; object-fit: contain }`, a fixed box so pagination measures it before load
  - `.reader-table { display:block; overflow:auto; max-height: calc(100dvh - 180px) }`
  - quote and list styling with Plainly's tokens

- [ ] **Step 1: Write the failing tests.** `test_pages.py`:
  - `test_library_lists_books_newest_first`
  - `test_library_reading_now_shows_progress_label`: start reading by POSTing a mutation, then expect `Chapter 1 of 3` or `Overview`.
  - `test_book_page_toc_grouped_by_part_and_overview_first`
  - `test_book_page_sources_rendered`
  - `test_reader_shell_has_shared_partials_and_no_mode_choices`: `id="continuous-reader-section"` is present and `data-reader-settings-mode` is not.
  - `test_reader_shell_sets_cache_db_and_lang`
  - `test_unknown_slug_404_page`
  - `test_progress_label_cases`
- [ ] **Step 2: Write the e2e scenario** `tests/e2e/distill.mjs`. Defaults: `BASE_URL` `http://localhost:5003`, `DISTILL_SLUG` `atomic-habits`, `DISTILL_ZH_SLUG` `quanqiutongshi`. It exits 1 on any FAIL or console error. Desktop checks at 1280×900:
  - The library shows the book, then clicking it gives a book page with `h1` and part headings.
  - "Start/Continue reading" opens the reader, with `[data-reader-anchor]` visible.
  - Find a chapter with an image and a table through the manifest and segment API, open `?chapter=<id>`, and page forward to them. The figure `img.naturalWidth > 0`. For every `[data-reader-anchor]` on each visited page, its bottom is ≤ the page container's bottom + 1, except for `table.reader-table` (Review Focus 4). `.reader-keypoints` has non-empty `::before` content.
  - Press ArrowRight 3 times, wait 1.5 s and read the first anchor id. Reload, and the first anchor id is the same (saved place, Review Focus 5).
  - `/` now lists the book under Reading now.
  - `(await indexedDB.databases()).map(d => d.name)` includes `distill-reader-v1` and not `summra-reader-v2` (Review Focus 1).
  - The zh book's reader opens with anchors.
- [ ] **Step 3: Run them and confirm they fail.** Run pytest. For the e2e, start `DISTILL_USER_DB=$TMPDIR/distill_user_e2e.db PORT=5003 venv/bin/python -m distill.app` and run `node distill.mjs`; it fails at the library.
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Verify.** The full pytest suite is green. `node distill.mjs` passes. Read the screenshots `screenshots/distill_*.png`. The Plainly e2e set is still green.
- [ ] **Step 6: Commit** "Add Distill library, book page and shared-reader host".

### Task 9: Distill Kindle mode, plus the e2e Kindle scenario

**Files:**
- Create: `distill/kindle_routes.py`, `distill/templates/kindle/{library,book,reader}.html`, `distill/static/css/distill_kindle.css`, `tests/distill/test_kindle.py`
- Modify: `distill/app_base.py` (register the blueprint), `tests/e2e/distill.mjs` (Kindle section)

**Interfaces:**
- Consumes: Task 5's `shared.kindle.pages` and `shared.kindle.progress`, Task 6's `block_element` and `block_text`.
- Produces: `distill.kindle_routes.bp`, with `register_kindle_pages(bp, {'distill.library': library_page, 'distill.book_page': book_page, 'distill.reader': reader_page})`. These are the endpoints Task 7 fixes.
  - `library_page()`: "Reading now" (all in-progress books, paginated at `LIBRARY_PAGE_SIZE = 7`), then all books paginated, extending `shared/kindle/base.html` with `head_extra` linking `distill_kindle.css`. No search and no tabs.
  - `book_page(slug)`: contents as one list of part headings (`li.part`, not links) and chapter links `read?ch=<ordinal>`, paginated at `CONTENTS_PAGE_SIZE = 8`. It has a Continue link when `saved_marker` finds one, and "You are here" on that chapter.
  - `reader_page(slug)`:
    - Picks the chapter from `?ch=<ordinal>`, otherwise from the saved chapter (`saved_marker(..., modes=('summary',))`), otherwise ordinal 0.
    - Starts at the saved index when it is in this chapter.
    - Extends `shared/kindle/reader_base.html`, with `flow_body` = `{% for i, b in blocks %}{{ block_element(b, i) }}{% endfor %}` and an empty `menu_text_row`.
    - Sets `data-text="summary"`, with `data-before`, `data-chars` and `data-total` computed from `len(block_text)` sums.
    - The `<html>` carries `lang`.
  - `POST /api/kindle/progress`: JSON `{book_id, ch (ordinal), p (block index), text: 'summary', forward, seconds, finished}`. It validates as Plainly does; `text` must be `'summary'`. It resolves the chapter id by ordinal, sets `paragraph_id = _reader_unit_id(chapter_id, p)` and `quote = normalize(block_text(blocks[p]))[:180]`, then returns `record_page(...)`.
- `distill_kindle.css`: `.flow table, .flow tr, .flow figure { -webkit-column-break-inside: avoid; break-inside: avoid; }`, `.flow figure img { max-width: 100%; max-height: 540px; }`, keypoints label via `::before`, and table borders sized for e-ink. No new JS.

- [ ] **Step 1: Write the failing tests.** In `test_kindle.py`, each request sends the Paperwhite UA from `tests/plainly/test_kindle_mode.py`:
  - `test_kindle_library_reading_now_and_all_books`
  - `test_kindle_book_contents_has_part_headings_and_paginates`
  - `test_kindle_reader_renders_blocks_with_data_i`, covering a table, a list and a figure
  - `test_kindle_reader_resumes_saved_chapter_and_index`
  - `test_kindle_progress_records_summary_marker_with_quote`
  - `test_kindle_progress_rejects_other_text_modes`
  - `test_kindle_progress_completion_on_last_block_forward_only`
  - `test_kindle_off_switch_serves_web_pages`
- [ ] **Step 2: Extend `distill.mjs` with a Kindle section.** It uses the Kindle UA from `kindle_mode.mjs` at 758×950.
  - On `/`, `html.kindle` is present and there is no `script[type=module]`.
  - The book page lists contents.
  - `read?ch=<ordinal with table and image>` loads `kindle.js`.
  - For every `#flow tr` and `#flow figure`, all `getClientRects()` share one column index, `Math.floor((rect.left - flowLeft) / step)` (Review Focus 4).
  - Clicking at x=700 changes `#right`.
  - No console errors.
- [ ] **Step 3: Run them and confirm they fail.** **Step 4: Implement.** **Step 5: Verify.** The full pytest suite is green, `node distill.mjs` passes, and `kindle_mode.mjs` against Plainly is still green.
- [ ] **Step 6: Commit** "Add Distill Kindle mode on shared Kindle pages".

### Task 10: Docs and work log

**Files:**
- Modify: `docs/PRD.md`, `docs/ERD.md`, `WORK_LOG.md`, `CLAUDE.md` (Frontend Test Loop: the Distill dev server and e2e), `tests/e2e/README.md`

- [ ] **Step 1: PRD.** Add a "Distill" section covering:
  - the owner-only access model and the allow-list
  - the library with Reading now, the book page, the reader with no modes, saved place and progress ("Chapter n of m", with "Overview")
  - Kindle mode
  - the explicit non-goals from spec §3
- [ ] **Step 2: ERD.** Add a "Shared reader" section covering:
  - the host contract
  - the files in `shared/static/js` and which app supplies which hook
  - the symlink serving scheme, and the Apache `+FollowSymLinks` requirement (Plainly's next deploy must reinstall `deploy/apache/summra.conf`)
  - the esbuild bundling of shared modules into Plainly's `app.min.js`
  - the `reader_cache_db` per app
  - `make_reader_blueprint`
  - `shared.kindle`

  Add a "Distill app" section covering routes, auth env, DBs, the renderer, `_render` units and `RENDER_VERSION`. It must include this note: **re-import keeps chapter ids by ordinal, so a chapter inserted mid-book shifts content under existing ids.** A saved place in a later chapter then points at different text, and quote recovery runs only within the marker's chapter.
- [ ] **Step 3: WORK_LOG.** Add the phase 3 summary, with the final pytest count and the e2e scripts run.
- [ ] **Step 4: Run the full verification once more.** That is pytest, `node --test tests/js/`, `npm run build:check`, the Plainly e2e set on :5002, and `distill.mjs` on :5003.
- [ ] **Step 5: Commit** "Document Distill web app and shared reader".
