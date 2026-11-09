# Shared Audio Player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One audio player shared by Distill and Plainly, with audio that keeps playing while browsing, and a reader whose text never moves because of audio.

**Architecture:** `AudioPlayer` owns playback and knows nothing about pages. `ReaderAudioLink` ties it to the shared continuous reader. Shared templates draw the mini and full players. Distill moves to in-place page loading, so like Plainly it keeps one page alive. Recordings, API and pipeline move to `shared/audio/`.

**Tech Stack:** Flask, SQLite, vanilla ES modules, Playwright (WebKit for audio), pytest, esbuild (Plainly bundle).

**Spec:** `docs/superpowers/specs/2026-11-09-shared-audio-player-design.md`

## Global Constraints

- Work only in worktree `.claude/worktrees/distill-player`, branch `feat/distill-player`. Before each commit, run `pwd && git branch --show-current`.
- TDD: every behaviour change starts with a failing test. Never edit a test to make it pass; flag it instead. A test that asserts the old player's markup or layout may be replaced only in the task that replaces that feature, and the task must say so.
- Scratch servers: Distill `DISTILL_USER_DB=$TMPDIR/du_player.db PORT=5006 venv/bin/python -m distill.app`; Plainly `PORT=5007 venv/bin/python plainly/app.py`. Worktree needs its own `venv` (symlink is fine) and `tests/e2e/node_modules`.
- Never push `distill_user.db`. Deploy only with `distill.scripts.deploy_code` and `deploy_db`.
- Highlight and automatic page turns only when the book and page on screen match the audio.
- Back 15 seconds, forward 30. Silent hold 30 minutes. Rates 1, 1.25, 1.5, 1.75, 2.
- Desktop full player: right-edge panel, no dimming, reader column slides left at the same width; below 1,060 px wide it lies over the page.
- Kindle: no audio, ordinary page loads, unchanged.
- After any change under `shared/` or `plainly/`: the 14 Plainly scripts in `CLAUDE.md`, plus `reader_style_snapshot.mjs` compare.
- Copy is sentence case. Exact label: "Listen from here instead".

## Review Focus

1. Sign-in expires during browsing: the in-place fetch gets 401 or a redirect. Expected: the audio's place is saved, then an ordinary load goes to sign-in. Test in Task 6.
2. Taps land quickly on two links. Expected: only the last page appears. Test in Task 6.
3. Audio is playing and the on-screen book has no recording. Expected: no "Listen from here instead", and the player still works. Test in Task 5.
4. Back and forward after in-place loads, including library filters and scroll position. Expected: same page, same filters, same scroll. Test in Task 6.
5. Places saved before this change under `distill-listen-<id>`. Expected: they still resume. Test in Task 3.

## File Structure

| File | Responsibility |
|---|---|
| `shared/static/js/audio_player.js` (new) | `AudioPlayer`: element, tracks, position, rate, silent hold, Media Session |
| `shared/static/js/audio_sources.js` (new) | `RecordedBookSource`, the source contract |
| `shared/static/js/reader_audio_link.js` (new) | `ReaderAudioLink`, `PlaceKeeper`, `unitAt`, `msFor` |
| `shared/static/js/player_ui.js` (new) | `PlayerUI`: mini and full players |
| `shared/templates/shared/reader/_player.html` (replaces `_listen_bar.html`) | Player markup |
| `shared/static/css/listen.css` | Player styles |
| `shared/static/js/page_swap.js` (new) | In-place navigation and page start/stop registry |
| `distill/static/js/{library_page,book_page}.js` (new) | Inline page scripts, moved with start/stop |
| `shared/audio/{store,routes,spoken,engines,assemble,pipeline}.py` (new) | Recordings, API, recording pipeline |
| `plainly/frontend/static/js/generated_speech_source.js` (new) | Plainly's summary speech source |

`shared/static/js/listen.js`, `distill/static/js/listen_page.js` and `distill/audio/` are deleted once replaced.

---

### Task 1: Baseline timings

**Files:** Create `tests/e2e/distill_page_timing.mjs`, `tests/e2e/perf/distill_baseline.json`.

**Interfaces:** Produces `MODE=record|compare` and JSON keys `home_ms`, `book_ms`, `reader_open_ms`, `page_turn_ms`.

- [ ] **Step 1:** Write the script. WebKit, 390×844, CDP-free throttling through `page.route` adding 150 ms per first-party request. Median of 7 runs of tap to content visible: home → book page (`main.distill-book` visible), book → reader (first `[data-reader-anchor]`), library link → home, ArrowRight page turn.
- [ ] **Step 2:** Run `MODE=record node distill_page_timing.mjs` against `main` code in this worktree. Expected: JSON written with four positive numbers.
- [ ] **Step 3:** Commit script and baseline.

### Task 2: Reader height never depends on the player

**Files:** Modify `shared/static/js/listen.js:103,170-176`, `shared/static/css/listen.css:2`. Test: `tests/e2e/reader_audio_stable.mjs`.

- [ ] **Step 1:** Write `reader_audio_stable.mjs`. Record `getBoundingClientRect()` of every visible `[data-reader-anchor]`, `reader.pagination.totalPages`, and the content box height. Assert all are identical after: start listening, pause, close the player. Run phone and desktop sizes.
- [ ] **Step 2:** Run it. Expected: FAIL on content height after close.
- [ ] **Step 3:** Remove the `prepend` into the footer, the footer `:has` rule, and the `resize` dispatch in `showBar`. Style the bar as a fixed overlay for now (replaced in Task 5).
- [ ] **Step 4:** Run the new test, `distill_listen.mjs` and `listen_follow.mjs`. Expected: all pass.
- [ ] **Step 5:** Commit.

### Task 3: Split `listen.js` with no visible change

**Files:** Create `audio_player.js`, `audio_sources.js`, `reader_audio_link.js`. Delete `listen.js`, `listen_page.js`. Modify `distill/static/js/distill_reader.js`, a new thin `distill/static/js/listen_home.js`, `_listen_scripts.html`.

**Interfaces (produces):**
- Source: `load() -> Promise<Track[]>`, where `Track = {id, bookId, bookTitle, author, title, urls: string[], durationMs?, timings?}`. `new RecordedBookSource({audioApi, book})`.
- `new AudioPlayer({rates, holdMs})` with `setSource(source)`, `load(index, ms)`, `resume()`, `pause()`, `stopSilence()`, `seekToMs(ms)`, `seekBy(s)`, `setRate(r)`, `nextTrack()`, `previousTrack()`, getters `playing`, `tracks`, `index`, `book`, `position() -> {trackId, ms}`, and `subscribe(fn) -> unsubscribe`, fired with `'state'|'time'|'track'|'error'`. A track with several `urls` plays them in order as one track.
- `new ReaderAudioLink(player, reader, {book, mode, storageKey, place})` with `attach()`, `detach()`, `listenFromReadingPosition()`, `following`, `setFollowing(bool)`.
- `new PlaceKeeper({bookId, mode, storageKey, manifest?})` with `save(position)`, `saved()`, `markerFor(position)`. Works with no reader on screen, using `/api/reader/books/<id>/manifest` and `/api/progress/v2/books/<id>`.
- `unitAt` and `msFor` exported from `reader_audio_link.js`.

`detach()` restores every reader method it wrapped and removes its listeners.

- [ ] **Step 1:** Add to `distill_listen.mjs`: seed `localStorage['distill-listen-<id>']` in the current format and assert the book page's "Resume listening" and the resume position still work. Run on current code. Expected: pass (it pins today's behaviour).
- [ ] **Step 2:** Add a failing check to `listen_follow.mjs`: after `link.detach()`, `reader.navigateToNextPage` is the original function and `.listen-current` is gone. Expected: FAIL, `detach` missing.
- [ ] **Step 3:** Move the code. Keep `window.distillListener` as a test handle exposing the old getters, until Task 5 changes the tests.
- [ ] **Step 4:** Run `distill_listen`, `distill_listen_home`, `listen_follow`, `reader_audio_stable`, `pytest tests/ -q`. Expected: all pass.
- [ ] **Step 5:** Commit.

### Task 4: Shared player UI

**Files:** Create `shared/templates/shared/reader/_player.html`, `player_ui.js`. Modify `listen.css`, `distill/templates/{_listen_player,reader}.html`, `distill.css:267-270`. Delete `_listen_bar.html`. Test: `tests/e2e/player_ui.mjs`, replacing the bar-markup checks in `distill_listen*.mjs`, as this task replaces that feature.

**Interfaces:** `new PlayerUI(player, {coverFor(track)})`, with `openFull()`, `closeFull()`, `setPageContext({bookId, canListenHere, label, onListenHere} | null)`. Element ids: `player-mini`, `player-full`, `player-full-close`, `player-play`, `player-back`, `player-fwd`, `player-prev`, `player-next`, `player-rate`, `player-chapters`, `player-seek`, `player-listen-here`.

- [ ] **Step 1:** Write `player_ui.mjs`, failing, with: mini visible at the bottom edge on a 390-px page and as a card under 370 px wide at bottom right at 1280 px; tapping it opens the full player; full player fills the phone screen; at 1280 px it is a right-edge panel with no scrim; at 1000 px it overlays; the down arrow closes it; back 15, forward 30, rate cycles; prev/next and Chapters are hidden for a one-track source; close stops audio and ends the hold.
- [ ] **Step 2:** Run. Expected: FAIL on missing `#player-mini`.
- [ ] **Step 3:** Build the template, styles and `PlayerUI` to match the reviewed mockups.
- [ ] **Step 4:** Run `player_ui.mjs`, read screenshots at both sizes, run the Listen tests. Expected: pass.
- [ ] **Step 5:** Commit.

### Task 5: Reader headphones and switching books

**Files:** Modify `reader_audio_link.js`, `distill_reader.js`, `listen.css`. Test: `tests/e2e/player_reader.mjs`.

- [ ] **Step 1:** Write `player_reader.mjs`, failing: no player visible in the reader; headphones plain when idle and start this book; accent when audio is going, in this book or another, and open the full player in both; highlight absent in another book and after turning away; no pull-back after turning away; "Listen from here instead" only for another book, and pressing it saves the first book's place on the server before the second starts; **no such button when the on-screen book has no recording, while the player still works**; desktop panel open leaves `.reader-page` width, `totalPages` and line breaks unchanged.
- [ ] **Step 2:** Run. Expected: FAIL on headphones opening the full player.
- [ ] **Step 3:** Implement. `Back to audio`/`Play from here` controls are removed, as the spec's player replaces them; update `listen_follow.mjs` for that in this task.
- [ ] **Step 4:** Run this test, Listen tests, `reader_audio_stable`. Expected: pass.
- [ ] **Step 5:** Commit.

### Task 6: Distill in-place page loading

**Files:** Create `shared/static/js/page_swap.js`, `distill/static/js/library_page.js`, `book_page.js`. Modify `distill/templates/{base,library,book,reader}.html`, `distill_reader.js`. Test: `tests/e2e/distill_in_place.mjs`.

**Interfaces:** `startPageSwap({root: '#page-root'})`; `registerPage(name, {start(root), stop()})`. Templates mark `<div id="page-root" data-page="library|book|reader" data-body-class="...">`. The shell `AudioPlayer` and `PlayerUI` are created once, outside `#page-root`. Kindle templates are not touched.

The fetch sends `X-Requested-With: page-swap` only as a cache-safe hint; the response is the normal full HTML, parsed with `DOMParser`, so a direct URL and a swap get the same page. Vary is unnecessary because the body doesn't change. Add one reader stop path that reuses Plainly's exit (`continuousReader = {active: false}` and the reader's exit handlers).

- [ ] **Step 1:** Write `distill_in_place.mjs`, failing: a `window.__stamp` survives home → book → reader → another book → Back; audio `currentTime` keeps rising across each; title and URL correct; filters and search work after returning; library filter submit swaps in place; **rapid taps on two links show only the last**; **Back and Forward restore filters and scroll**; **401 or redirect saves the audio place, then does a full load**; network failure does a full load; 20 reader open/close cycles do not grow reader listeners (count through a wrapped `addEventListener`); Kindle user agent gets ordinary loads and no `page_swap.js`.
- [ ] **Step 2:** Run. Expected: FAIL on `__stamp` lost.
- [ ] **Step 3:** Implement. Move inline scripts to page modules. Intercept same-origin GET links and forms in `#page-root` only, skipping downloads, new tabs and modified clicks. Fetch on `pointerdown`/hover, abort the previous fetch, keep the old page visible, show the progress line after 150 ms.
- [ ] **Step 4:** Run this test, `distill.mjs`, Listen tests.
- [ ] **Step 5:** Run `MODE=compare node distill_page_timing.mjs`. Expected: each metric at or below baseline. If not, stop and report the numbers.
- [ ] **Step 6:** Commit.
- [ ] **Step 7:** Owner waived the iPhone gate on 2026-11-09 (stepped away, asked for build and deploy). Record in `WORK_LOG.md` that iPhone behaviour is unverified.

### Task 7: Move recordings and API to `shared/audio/`

**Files:** Create `shared/audio/store.py`, `routes.py`. Move `distill/audio/*` to `shared/audio/`. Modify `distill/models.py:110-123,186-235`, `distill/routes.py:300-330`, `distill/scripts/{make_audio,db_patch,media_transfer}.py`. Tests: move `tests/distill/test_audio_*.py` to `tests/shared/`, add `tests/shared/test_audio_store.py`.

**Interfaces:**
- `create_audio_tables(conn)`, and `AudioStoreMixin` with `save_chapter_audio(chapter_id, mode, data, timings, duration_ms, checksum, voice, engine, rate)`, `set_deploy_audio(chapter_id, mode, data)`, `book_audio(book_id, mode) -> list[dict]`, `stale_or_missing_audio(book_id, mode)`, and the hook `audio_spoken_units(chapter, mode) -> list[(paragraph_id, text)]`.
- `audio_blueprint(get_db, access_check, audio_mode)`, serving `/api/books/<slug>/audio` and `/books/<slug>/audio/<int:chapter_id>.m4a`. `?mode=` selects a recording; the default comes from `audio_mode`.
- `chapter_audio` primary key `(chapter_id, mode)`, column `mode TEXT NOT NULL DEFAULT 'summary'`.

- [ ] **Step 1:** Write `test_audio_store.py`, failing: an old-schema DB migrates with every row kept and `mode='summary'`; migration is idempotent; two modes coexist for a chapter; stale text hides that mode only; a chapter delete cascades.
- [ ] **Step 2:** Add to `test_db_patch.py`, failing: a live DB and a local DB with the new key produce an empty patch when identical, and a one-mode change sends one row. Add to `test_deploy_db.py`: the snapshot still ships Opus keys.
- [ ] **Step 3:** Add to `test_audio_routes.py`: Distill still needs sign-in, URLs and JSON shape are unchanged, private cache headers kept.
- [ ] **Step 4:** Run. Expected: FAIL, `shared.audio.store` missing.
- [ ] **Step 5:** Implement. SQLite can't change a primary key in place: create, copy and rename in one transaction, guarded by `PRAGMA table_info`. Keep `make_audio`'s command line, passing `mode='summary'`.
- [ ] **Step 6:** Run `pytest tests/ -q` and `make_audio --book <slug> --dry-run` on a copy of the local DB. Expected: all pass; dry-run reports no chapters stale.
- [ ] **Step 7:** Commit. Note for deploy: run `deploy_code` before `deploy_db`, so the VM's table is migrated first.

### Task 8: Plainly on the shared player

**Files:** Create `generated_speech_source.js`. Modify `plainly/frontend/static/js/{audio,app,reader}.js`, `plainly/frontend/templates/index.html:725-740`, `plainly/models.py`, Plainly's app setup. Rebuild `app.min.js`. Test: `tests/e2e/plainly_player.mjs`, `tests/test_plainly_audio.py`.

**Interfaces:** `new GeneratedSpeechSource({urls, bookId, bookTitle, author, title, audioId})`, keeping `waitForChunk`'s retry. Plainly registers `audio_blueprint` with its own public access check and `AudioStoreMixin`, with `audio_spoken_units` drawn from `reader_unit` for the mode.

- [ ] **Step 1:** Write `test_plainly_audio.py`, failing: a chapter fixture saved through `AudioStoreMixin` appears in `/api/books/<slug>/audio?mode=plain`; a mode with no recording returns an empty list; an edited chapter hides its audio.
- [ ] **Step 2:** Write `plainly_player.mjs`, failing: **with only that fixture added, the reader shows headphones, highlight, automatic page turns and a saved place**; summary Listen still plays and the mini player appears with no chapter buttons or highlight; side-by-side plays Plain English, falling back to Original, and highlights the matching column; audio continues while navigating in Plainly.
- [ ] **Step 3:** Run. Expected: FAIL, no route.
- [ ] **Step 4:** Implement. Delete player logic from `audio.js`, keeping only speech generation and text clean-up. Grep confirms no `new MediaMetadata` outside `audio_player.js`.
- [ ] **Step 5:** Run `npm run build`, `npm run build:check`, this test, the 14 Plainly scripts, and `reader_style_snapshot.mjs` compare.
- [ ] **Step 6:** Commit.

### Task 9: Documents and full verification

**Files:** Modify `docs/PRD.md`, `docs/ERD.md`, `WORK_LOG.md`, the Distill audio paths in `CLAUDE.md` and `skills/distill-publish/SKILL.md`.

- [ ] **Step 1:** Update the documents, including the new `shared/audio/` paths and the deploy order note.
- [ ] **Step 2:** Run `pytest tests/ -q`, `distill.mjs`, all new e2e scripts, Listen tests, `distill_page_timing.mjs` compare, and the 14 Plainly scripts. Expected: all pass, with counts recorded in `WORK_LOG.md`.
- [ ] **Step 3:** Commit. Owner authorised push and deploy once done (2026-11-09): merge to `main`, push, `deploy_code`, then `deploy_db`.
