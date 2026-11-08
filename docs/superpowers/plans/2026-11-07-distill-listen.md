# Distill Listen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Listen to Distill summaries in the iOS PWA, sharing one position with reading, using chapter audio made on the Mac.

**Architecture:**
- **On the Mac:** a script turns each chapter's spoken reader units into one AAC file plus unit timings, and stores the file in the existing `MediaStore`. `say` is used for English and Siri Voice 4 for Chinese.
- **On the server:** Distill serves the audio with HTTP Range, plus a JSON timings endpoint.
- **In the browser:** a small player module drives one `<audio>` element and Media Session. It follows the text, and saves its position as the summary mode's `current_marker`, where `offset` is the fraction of the unit already played.

**Tech Stack:**
- Python 3 and Flask, with SQLite (`distill.db`).
- macOS `say`, `afconvert`, and PyObjC through InkChinese's `siri_tts.py`.
- Vanilla JS (ES modules).
- pytest and Playwright.

**Spec:** `docs/superpowers/specs/2026-11-07-distill-listen-design.md`

## Global Constraints

- **Chinese voice:** Siri Voice 4 `zh-CN-D`, rate **1.0**, through `../inkchinese/pipeline/siri_tts.py`. Not copied into this repo.
- **English voice:** `say -o` with no `-v` (the system voice, Siri Voice 2).
- **Never fall back to another voice silently.** Before rendering:
  - Siri must list `zh-CN-D` in `siri_tts.voices()`;
  - every engine must pass the reference-clip check (Task 2).
- **Encoding:** AAC-LC, mono, 32 kbps, `.m4a` (`afconvert -f m4af -d aac -b 32000`).
- **Silence:** 350 ms between units, 250 ms between items inside a list block, and 350 ms after the chapter title.
- **What's spoken:** the chapter title first, then the `p`, `h`, `quote`, `ul`, `ol` and `keypoints` blocks. `table` and `image` blocks are skipped (captions too). Text is plain, via `shared/reader/blocks.py: block_text`.
- **Unit ids:** `paragraph_id = f"{chapter_id}.{block_index}"`, where `block_index` is the 0-based index into `chapters.blocks`. This is the existing reader unit id.
- **Siri errors:** retry a failed unit up to 3 times, then stop that book with an error.
- **Sign-in:** expiry pauses playback and asks the owner to sign in again. No Apache session change.
- **Media storage:** audio goes in `MediaStore`, never as BLOBs in `distill.db`. Deploys upload only keys the VM lacks.
  - The spec also asked for streaming. That is dropped, because the owner confirmed the disk has room. The tar of missing keys is still built locally.
- **Shared-code rule:** after any change under `shared/`, run the 14 Plainly e2e scripts listed in CLAUDE.md.

## Review Focus

1. **A chapter with no spoken blocks** (only tables and images) still gets audio of its title, and its timings map the title to the first block's id. Test in Task 1.
2. **Stale audio after a text edit:** the chapter is left out of the timings API and its audio route returns 404, so the player skips to the next chapter with current audio. Tests in Tasks 3 and 5.
3. **Resuming exactly at a unit boundary or past the end of a file:** the seek is clamped to `[0, duration]`, and `offset` stays within `[0, 1]`. Test in Task 7.
4. **A sign-in redirect while loading the next chapter:** the response isn't audio. The player must pause, save the position, and show the sign-in/resume prompt, not loop or fail silently. Test in Task 7.
5. **A Range request past the end of the file** returns 416, not 500. Test in Task 5.

---

### Task 1: Spoken text and checksum

**Files:**
- Create: `distill/audio/__init__.py`, `distill/audio/spoken.py`
- Test: `tests/distill/test_audio_spoken.py`

**Interfaces:**
- Produces:
  - `SpokenUnit = NamedTuple('SpokenUnit', [('paragraph_id', str), ('parts', list[str])])`. `parts` holds one string per item for lists, and one string otherwise.
  - `spoken_units(chapter: dict) -> list[SpokenUnit]`. `chapter` has `id`, `title` and `blocks`, as in `DistillDatabase.get_chapters` rows with blocks parsed. The title is the first unit's first part. Its `paragraph_id` is the id of the first spoken block, or `f"{id}.0"` if there is none.
  - `spoken_checksum(units: list[SpokenUnit]) -> str`, a sha256 hex of the canonical JSON of `[(paragraph_id, parts)]`.

- [ ] **Step 1: Write failing tests**
  - `test_skips_table_and_image`: `SAMPLE_BOOK` chapter 1 from `tests/distill/conftest.py` gives ids `.0`, `.1` and `.3`.
  - `test_list_items_are_parts`: the `ul` block gives `parts == ['a', 'b']`.
  - `test_title_is_first_part`: `units[0].parts[0] == '1. First'`.
  - `test_markdown_stripped`: `'Hello **world**.'` gives `'Hello world.'`.
  - `test_only_tables_keeps_title`: a chapter with only a table gives one unit, `paragraph_id == f'{id}.0'`, `parts == [title]`.
  - `test_checksum_changes_with_text`: the checksum changes when one character changes and stays the same when nothing changes.
- [ ] **Step 2:** `venv/bin/pytest tests/distill/test_audio_spoken.py -v`. Expect FAIL (module missing).
- [ ] **Step 3:** Implement `spoken.py` using `block_text` for `p`, `h` and `quote`, and the raw items (each through `block_text({'type':'p','text':item})`) for `ul`, `ol` and `keypoints`.
- [ ] **Step 4:** Run the tests again. Expect PASS.
- [ ] **Step 5:** Commit: `feat(distill): spoken units and checksum for chapter audio`.

### Task 2: Voice engines and voice guard

**Files:**
- Create: `distill/audio/engines.py`
- Modify: `deploy/distill/deploy.local.env.example` (add `DISTILL_SIRI_TTS_PATH=../inkchinese/pipeline` and `DISTILL_SIRI_PYTHON=../inkchinese/pipeline/.venv/bin/python`)
- Test: `tests/distill/test_audio_engines.py`

**Interfaces:**
- Produces:
  - `Rendered = NamedTuple('Rendered', [('wav', Path), ('duration_ms', int), ('sample_rate', int)])`
  - `class Engine(Protocol)`: `name: str`, `voice_id() -> str`, `render(text: str, out_wav: Path) -> Rendered`.
  - `SayEngine()`:
    - `render` runs `say -o <aiff> -f <txtfile>`, then `afconvert -f WAVE -d LEI16 <aiff> <wav>`.
    - `voice_id()` returns `'say:system'` plus the sha256 of the reference clip.
  - `SiriEngine(tts_path: Path, python: Path, voice='zh-CN-D', rate=1.0)`:
    - `render` runs `python -c` in a subprocess against `siri_tts.synthesize(text, 'zh-CN', wav, rate=1.0)`. InkChinese's venv has PyObjC; Summra's doesn't.
    - It checks the voice list once per process and raises `VoiceUnavailable` unless `zh-CN-D` is listed.
    - Retries: 3 tries per unit, then `RenderFailed`.
  - `engine_for(lang: str, settings: dict) -> Engine`: `'zh'` gives `SiriEngine`, `'en'` gives `SayEngine`, anything else raises `ValueError`.
  - `check_reference(engine: Engine, ref_dir: Path, approve: bool = False) -> None`:
    - Renders `REFERENCE_TEXT = {'en': 'Reading is to the mind what exercise is to the body.', 'zh': '读书之于心灵，犹如运动之于身体。'}` and compares it with `ref_dir/<engine.name>.json` (`{sha256, duration_ms}`).
    - `approve=True` writes the file.
    - On a mismatch, or if the file is missing and `approve` is not set, it raises `VoiceMismatch`.
    - **Matching:** `say` must match the sha256 exactly (verified repeatable on 2026-11-07). If Siri's output turns out not to be byte-repeatable (Step 3 checks this), Siri matches on `duration_ms` within ±2%.

- [ ] **Step 1: Write failing tests**, with `subprocess.run` mocked at the boundary:
  - `test_engine_for_lang`
  - `test_siri_retries_then_fails`: 3 failing calls raise `RenderFailed`, and the call count is 3.
  - `test_siri_missing_voice_raises`: a voice list without `zh-CN-D` raises `VoiceUnavailable`.
  - `test_reference_mismatch_raises`
  - `test_reference_approve_writes_then_passes`
  - `test_reference_missing_without_approve_raises`
- [ ] **Step 2:** Run the tests. Expect FAIL.
- [ ] **Step 3:** Implement. Then, by hand on the Mac, render the zh reference twice and record in `WORK_LOG.md` whether the bytes match. Pick exact or ±2% matching for Siri accordingly.
- [ ] **Step 4:** Run the tests. Expect PASS. Then do a manual smoke run: `venv/bin/python -c "from distill.audio.engines import SayEngine; print(SayEngine().render('Hello there.', Path('/tmp/x.wav')))"` (use `$TMPDIR`) and check that `duration_ms` is above 0.
- [ ] **Step 5:** Commit: `feat(distill): say and Siri engines with voice guard`.

### Task 3: Assembly, encoding and schema

**Files:**
- Create: `distill/audio/assemble.py`
- Modify: `distill/models.py` (in `init_db`, add the table; in `media_keys`, add the union; add the methods listed below)
- Test: `tests/distill/test_audio_assemble.py`, `tests/distill/test_models.py` (add cases)

**Interfaces:**
- Consumes: `SpokenUnit` and `spoken_units` (Task 1), `Engine` and `Rendered` (Task 2).
- Produces:
  - `compute_timings(units: list[tuple[str, list[int]]], unit_gap_ms=350, part_gap_ms=250) -> list[dict]`
    - Input: `(paragraph_id, part_durations_ms)` per unit.
    - Output: `[{'paragraph_id', 'start_ms', 'end_ms'}]`.
    - The gap between the title and the rest of the first unit is `unit_gap_ms`; other gaps inside a unit are `part_gap_ms`. No gap after the last unit.
  - `render_chapter(chapter: dict, engine: Engine, work_dir: Path) -> tuple[bytes, list[dict], int, str]`, returning `(m4a_bytes, timings, duration_ms, checksum)`.
    - Renders each part, joins the WAVs with silence using the `wave` module (all parts share the engine's sample rate; raise if they differ), and encodes with `afconvert`.
  - `CREATE TABLE IF NOT EXISTS chapter_audio (chapter_id INTEGER PRIMARY KEY REFERENCES chapters(id) ON DELETE CASCADE, storage_key TEXT NOT NULL, text_checksum TEXT NOT NULL, duration_ms INTEGER NOT NULL, voice TEXT NOT NULL, engine TEXT NOT NULL, rate REAL, timings TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)`. `timings` is JSON. **It must not fire `reader_revision` triggers**; audio isn't reader content.
  - `DistillDatabase.save_chapter_audio(chapter_id: int, m4a: bytes, timings: list, duration_ms: int, checksum: str, voice: str, engine: str, rate: float | None) -> str`: calls `media.put`, upserts, and returns the key.
  - `DistillDatabase.book_audio(book_id: int) -> list[dict]`:
    - Returns the **current** chapters only, in chapter order: `{chapter_id, ordinal, title, storage_key, duration_ms, timings}`.
    - A chapter is current when the stored `text_checksum` equals `spoken_checksum(spoken_units(chapter))`.
  - `DistillDatabase.stale_or_missing_audio(book_id: int) -> list[int]`, the chapter ids that need rendering.
  - `media_keys()` adds `UNION SELECT storage_key FROM chapter_audio`.

- [ ] **Step 1: Write failing tests**
  - `test_compute_timings_gaps`:
    - Input: `[('5.0', [1000, 2000]), ('5.1', [500]), ('5.3', [300, 300])]` (title + p, then p, then a two-item list).
    - Expected: `5.0` → 0–3350, `5.1` → 3700–4200, `5.3` → 4550–5400.
  - `test_render_chapter_uses_fake_engine`:
    - A fake engine writes short silent WAVs of known length.
    - The timings match `compute_timings`.
    - `afconvert` is mocked, and its arguments are asserted to include `-b 32000`.
  - `test_render_chapter_rejects_mixed_rates`
  - `test_book_audio_hides_stale`: save audio, then edit the chapter's blocks; `book_audio` drops it and `stale_or_missing_audio` lists it.
  - `test_media_keys_include_audio`
  - `test_save_audio_does_not_bump_reader_revision`
- [ ] **Step 2:** Run them. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `venv/bin/pytest tests/distill -v`. All pass.
- [ ] **Step 5:** Commit: `feat(distill): chapter audio assembly and storage`.

### Task 4: Incremental media deploy

**Files:**
- Modify: `distill/scripts/media_transfer.py`, `distill/scripts/deploy_db.py`
- Test: `tests/distill/test_deploy_db.py`, `tests/distill/test_file_media.py`

**Interfaces:**
- Produces:
  - `media_transfer.list_keys(media_dir) -> list[str]`, plus a new CLI subcommand `list --media-dir DIR` that prints one key per line. The directory may be missing, in which case it prints nothing.
  - `media_archive(db_path, media_dir=None, exclude: frozenset = frozenset())` tars only `keys - exclude`, and yields `None` when nothing is left.
  - `_deploy_db` calls `{helper} list --media-dir <remote_media>` over ssh **before** building the archive, and passes the result as `exclude`. Build the archive inside `_deploy_db`, or pass a factory in `deploy_db` (builder's choice), so the remote listing comes first.

- [ ] **Step 1: Write failing tests**
  - `test_list_keys_empty_dir`, `test_list_keys_returns_stored`
  - `test_archive_excludes_present_keys`
  - `test_deploy_uploads_only_missing`, using the existing fake `run` in `test_deploy_db.py`:
    - the ssh `list` call returns one of two keys;
    - the uploaded tar contains only the other key;
    - when it returns both, no `scp` of the media tar happens.
- [ ] **Step 2:** Run them. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `venv/bin/pytest tests/distill -v`. All pass.
- [ ] **Step 5:** Commit: `feat(distill): deploy uploads only media the VM lacks`.

### Task 5: Audio routes

**Files:**
- Modify: `distill/routes.py`
- Test: `tests/distill/test_app.py` (or a new `tests/distill/test_audio_routes.py`)

**Interfaces:**
- Consumes: `book_audio` (Task 3).
- Produces:
  - `GET /books/<slug>/audio/<int:chapter_id>.m4a`, `@login_required`:
    - 404 unless the chapter is in `book_audio(book['id'])`.
    - Otherwise `send_file(media.path(key), mimetype='audio/mp4', conditional=True, etag=key, max_age=0)`.
    - Headers: `Cache-Control: private, max-age=31536000, immutable` (the key is content-addressed) and `X-Content-Type-Options: nosniff`.
  - `GET /api/books/<slug>/audio`, `@login_required`. Returns `{"book_id", "chapters": [{"chapter_id", "ordinal", "title", "url", "duration_ms", "timings"}]}`, with `url` built through `url_for` so the `/distill` prefix is right.

- [ ] **Step 1: Write failing tests**
  - `test_audio_range_206`: `Range: bytes=0-99` gives 206, `Content-Range: bytes 0-99/<size>` and 100 bytes.
  - `test_audio_full_200_has_accept_ranges`
  - `test_audio_requires_login`: the anonymous response matches the existing image route's (401).
  - `test_audio_stale_404`
  - `test_audio_range_past_end_416`
  - `test_audio_api_lists_current_only`
- [ ] **Step 2:** Run them. Expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `venv/bin/pytest tests/distill -v`. All pass.
- [ ] **Step 5:** Commit: `feat(distill): serve chapter audio with Range and timings API`.

### Task 6: `make_audio` command

**Files:**
- Create: `distill/scripts/make_audio.py`
- Test: `tests/distill/test_make_audio.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: the CLI `venv/bin/python -m distill.scripts.make_audio (--book SLUG | --all) [--dry-run] [--approve-voice] [--jobs N=2] [--db PATH] [--config PATH] [--deploy]`.
  - `--dry-run`: prints per-book chapter counts (total, current, to render) and the estimated audio hours (spoken characters ÷ 15 per second for en, ÷ 4.5 per second for zh). Renders nothing.
  - Calls `check_reference` once per engine before any rendering. Reference files go in `data/distill-voice-refs/` (gitignored).
  - Renders only `stale_or_missing_audio` chapters, so an interrupted run resumes.
  - Saves each chapter as soon as it's done.
  - `--jobs` runs that many chapters at once with a process pool. Each worker gets its own engine; Siri calls stay inside InkChinese's subprocess.
  - Stops a book on the first `RenderFailed` and moves on to the next book. Exits non-zero if any book stopped.
  - `--deploy` runs `deploy_db(db, settings)` after rendering. It refuses `--deploy --dry-run`, like `push_book`.

- [ ] **Step 1: Write failing tests** with a fake engine and a temporary DB:
  - `test_dry_run_writes_nothing`
  - `test_skips_current_chapters`
  - `test_voice_mismatch_aborts_before_render`
  - `test_render_failure_stops_book_continues_next`
  - `test_deploy_with_dry_run_rejected`
- [ ] **Step 2:** Run them. Expect FAIL.
- [ ] **Step 3:** Implement. Add `data/distill-voice-refs/` to `.gitignore`.
- [ ] **Step 4:** Run the tests. PASS.
- [ ] **Step 5: Real run on the Mac.**
  - `--approve-voice --book <one en slug>` and `--book <one zh slug>`, then play one chapter of each locally.
  - Record the measured render speed in `WORK_LOG.md`.
- [ ] **Step 6:** Commit: `feat(distill): make_audio command`.

### Task 7: Player, highlight-follow and saved position

**Files:**
- Create: `distill/static/js/listen.js`, `distill/templates/_listen_bar.html`
- Modify:
  - `distill/static/js/distill_reader.js` (boot the player after `showContinuousReader`)
  - `distill/templates/reader.html` (include the bar; pass `audio_api` in `DISTILL_BOOK`)
  - `distill/templates/book.html` (Listen action and the "Resume listening" line)
  - `distill/static/css/distill.css`
  - `shared/auth/user_models.py` (`VALID_CAUSES` += `'listen'`)
- Test: `tests/e2e/distill_listen.mjs` (new), `tests/test_*` for the cause (add a case where the existing user-model tests live)

**Interfaces:**
- Consumes: `/api/books/<slug>/audio` (Task 5); `reader.continuousReader.currentMarker`, `reader.loadContinuousReaderAt(marker)` and `window.authModule.queueReaderMutation(input)` (existing).
- Produces, in `listen.js`:
  - `export function unitAt(timings, ms) -> {index, paragraph_id, offset}`. `offset = (ms - start) / (end - start)`, clamped to [0, 1]. A time in a gap belongs to the unit before it.
  - `export function msFor(timings, paragraph_id, offset) -> number`, clamped to `[0, duration_ms]`.
  - `export class Listener`, with:
    - `constructor(reader, book)`;
    - `start({paragraph_id, offset})`;
    - `pause()`, `resume()`, `seekBy(sec)`, `setRate(r)`, `nextChapter()`.
  - localStorage key `distill-listen-<book_id>` holds `{chapter_id, paragraph_id, ms, rate, at}`.
- Behaviour, as in spec §5–6:
  - **The audio element:** one `<audio>` element, created on the first Listen tap. Set `navigator.audioSession.type = 'playback'` when it exists.
  - **Starting:** Listen starts at the unit currently at the top of the reading view, using the reader's `currentMarker`. If the saved local state has the same `paragraph_id`, it starts at the saved `ms`.
  - **Following the text:** on `timeupdate`, when the unit changes, call `loadContinuousReaderAt({mode:'summary', paragraph_id, offset:0, chapter_id})` while following, and toggle the `.listen-current` class.
    - Scrolling or paging by hand turns following off and shows a "Back to audio" chip.
  - **Saving locally:** every 5 s while playing, and on `pause`, `pagehide`, `visibilitychange`(hidden) and chapter change.
  - **Saving to the server** with `queueReaderMutation`:
    - `event_cause: 'listen'`, `mode: 'summary'`, `current_marker: {mode:'summary', chapter_id, paragraph_id, offset}`.
    - When the unit moved forward by one, set `sequential_boundaries_delta: 1` and `qualified_furthest_marker` = the current marker.
    - When: on pause, on chapter change, and every 30 s while playing.
    - **Finishing:** on the terminal unit, send `event_cause: 'completion'` with `terminal_dwell_ms: 2000` and `sequential_terminal_entry: true`, once ≥2 s of it have played.
  - **Media Session:** metadata (chapter title, book title, author, cover) and handlers for `play`, `pause`, `seekbackward`(15), `seekforward`(30), `seekto`, `previoustrack` and `nexttrack`.
  - **End of chapter:** on `ended`, set `src` to the next chapter in the timings API list on the same element, then play. After the last chapter, stop.
  - **Errors** (`error`/`stalled` past 10 s, or a fetch of the timings API that returns non-JSON or is redirected):
    - pause and save locally;
    - show the bar message "Paused — sign in again to keep listening" with a button that reloads the page. Reloading goes through Apache's sign-in.
  - **Bar controls:** play/pause, −15, +30, speed cycling 1×, 1.25×, 1.5×, 1.75×, 2×, the chapter title, and next.
  - The Listen button and bar are hidden when the timings API returns no chapters, and in Kindle mode.
  - **Book page:** if local state exists, show "Resume listening · <chapter title>, m:ss". It links to `/books/<slug>/read?listen=1`, which shows the bar ready on Play (iOS needs a tap to start audio).

- [ ] **Step 1: Write a failing pytest** `test_listen_is_valid_cause`, applying a `'listen'` mutation through `UserDatabase.apply_mutation`. Run it and expect FAIL. Add `'listen'` to `VALID_CAUSES` and expect PASS.
- [ ] **Step 2: Write the failing e2e `tests/e2e/distill_listen.mjs`.**
  - Fixture: a book with audio created by a fake engine (a seeded 3-second sine m4a per chapter, made in the test setup via a small Python helper using `afconvert`). Seed it into `DISTILL_DB` before starting the server.
  - Scenarios, each a `check()` with FAIL on mismatch:
    1. The Listen button is visible; tapping it plays from the unit at the top of the view.
    2. Seeking to 2.0 s highlights the unit whose timing contains 2000 ms.
    3. After pausing, localStorage holds that `paragraph_id` and a `ms` within ±300 ms.
    4. After a reload, the "Resume listening" label shows `0:02`.
    5. Dispatching `ended` loads chapter 2's URL into the same element.
    6. `navigator.mediaSession.metadata.title` equals the chapter title.
    7. A route intercept answers the timings API with a 302 to an HTML page, and the bar shows the sign-in message.
    8. Seeking past the end is clamped (no error).
- [ ] **Step 3:** Run `node distill_listen.mjs` against `PORT=5003` (CLAUDE.md "Distill" loop). Expect FAIL.
- [ ] **Step 4:** Implement `listen.js`, the bar, templates and CSS. Match the daylight typography; the bar sits above the iOS home indicator (`env(safe-area-inset-bottom)`).
- [ ] **Step 5:** Run `node distill_listen.mjs` and `node distill.mjs` (all three passes). Both exit 0.
- [ ] **Step 6:** Run the 14 Plainly e2e scripts (shared change). All pass.
- [ ] **Step 7:** Commit: `feat(distill): listen player synced with reading position`.

### Task 8: Docs, rollout and phone check

**Files:**
- Modify: `docs/PRD.md`, `docs/ERD.md`, `WORK_LOG.md`, `CLAUDE.md` (a short "Distill audio" note under Deploying Distill: `make_audio` usage and the voice references)

- [ ] **Step 1:** Update the PRD (the Listen user flows) and the ERD (the `chapter_audio` schema, engines, the incremental deploy and the player state).
- [ ] **Step 2: Deploy and listen.**
  - Only with the owner's go-ahead: `make_audio --book <en slug> --deploy`, then `--book <zh slug> --deploy`.
  - Then run CLAUDE.md's "Verify after deploy" for Distill, plus `curl` the audio route with a Range header on the VM loopback, using the owner email header. Expect 206.
- [ ] **Step 3: Owner phone check (manual).**
  - Lock-screen controls.
  - Playing on into the next chapter while locked.
  - Swiping the app away, then reopening to "Resume listening" at the same spot.
  - Opening the text at the spoken unit.
  - Record the results in `WORK_LOG.md`.
- [ ] **Step 4:** Commit: `docs: Distill Listen PRD/ERD and rollout notes`.
- [ ] **Step 5:** Once the owner approves the phone check, run `make_audio --all` overnight on the Mac, then `--deploy`.
