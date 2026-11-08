# Distill Listen: audio for book summaries

Status: draft for sign-off, 2026-11-07. Nothing built.

## Intent

The owner wants to **listen** to Distill summaries on an iPhone (installed PWA) and **move back and forth between listening and reading at the same spot**. Listening must survive iOS killing the app: after a kill, reopening Distill finds the exact place again.

Volume today: 64 books (56 English, 8 Chinese), 1,816 chapters, ~8M characters of block JSON → roughly 120–140 hours of speech. Live in-browser speech (`speechSynthesis`) is ruled out: on iOS it stops on screen lock, has no lock-screen controls and loses its place on kill.

## Goals

1. Pre-rendered audio for every chapter of every book's summary, generated on the owner's Mac, at no cost.
2. One shared position for reading and listening, so either one picks up where the other left off, across devices.
3. Background playback with lock-screen controls on an iOS PWA, continuing into the next chapter while locked.
4. Resume after app kill to within a sentence or two.

## Non-goals (first version)

- Offline listening (downloading audio into the PWA). iOS caching of large range-requested media is unreliable.
- Word-by-word karaoke highlighting.
- Audio in Plainly, or in Distill modes other than the summary.
- Generating audio on the VM. The VM has no macOS voices.

## Anti-goals

- **Silent voice fallback.** If the chosen voice is unavailable, generation fails loudly. It must never quietly produce audio in a different voice.
- Audio that drifts out of sync with the text after a book is edited (see "Staleness").
- Making the existing reader slower or heavier for someone who never presses Listen.

## Decided by the owner

- **Chinese voice:** Mandarin Siri Voice 4 (`zh-CN-D`), **rate 1.0**, using the private SiriTTSService exporter that InkChinese already uses (`../inkchinese/pipeline/siri_tts.py`). Rate 1.0 plays a test paragraph in 66s, against 73s at 0.9.
- **English voice:** macOS `say` with the Mac's system voice (`say -o`, no `-v`). The system voice is set to **Siri (Voice 2)** in Spoken Content.
  - Verified 2026-11-07: `say` renders this voice to a file at 22,050 Hz. It doesn't match any voice `say -v` can name (Samantha included), so it can't be pinned with `-v`.
  - The private Siri route can't reach it. Asking that route for "Nora" returns the same bytes as asking for a made-up name, so the route quietly falls back for unknown names.
  - `say` output is byte-for-byte repeatable, so the reference-clip check below can be an exact match.
  - Since `say` reports no timings, English timings are per unit only.
- **Sign-in expiry:** when the Google sign-in session expires mid-listen, pause and ask the owner to sign in again. No change to the Apache session length.
- **VM disk:** the owner confirms the VM has enough space for the audio.
- **In-app player synced with reading** (rather than a podcast feed).

## Design

### 1. What gets spoken

- The unit of audio is the **reader unit** that the shared reader index already assigns: `paragraph_id = "<chapter_id>.<chapter_ordinal>"` (`shared/reader/index.py: _reader_unit_id`). Progress is already stored against these ids (`mode_reading_state.current_paragraph_id`).
- **The chapter title is spoken first** (it's a column, not a block). It is mapped to the chapter's first unit for highlighting. *(Builder-check call, mine.)*
- **Block types** (`distill/book_format.py: BLOCK_TYPES`):
  - Spoken: `p`, `h`, `quote`, `ul`, `ol` and `keypoints`.
  - A list is one reader unit, so it is one timing entry. The whole list block highlights while it plays, with a short pause between items.
  - Skipped, with a short pause: `table` and `image`, including image captions.
  - *(Builder-check call, mine.)* Changing this rule later changes every checksum and means re-rendering the whole library, so it is settled here.
- Markdown markers (`*italic*`, links) are stripped to plain text before speaking. Use the existing `shared/reader/blocks.py: block_text` rather than writing a new stripper.

### 2. Generating the audio (Mac, offline)

- **New command:** `venv/bin/python -m distill.scripts.make_audio --book <slug> [--all] [--dry-run]`.
- **How it renders:** one unit at a time, choosing the engine by `books.lang`:
  - `zh`: Siri Voice 4 through the InkChinese exporter, at rate 1.0.
  - `en`: `say -o`.
- **Joining:** each chapter's units are joined in order into one file, with ~350 ms of silence between units. Encoding is AAC-LC, mono, 32 kbps, `.m4a` (`afconvert`). Expect ~1–2 GB for the whole library.
- **Timings:** start and end times for each unit come out of the join exactly, so there is no forced alignment step. Siri's within-unit range timings are also kept for Chinese, because they are free to store.
- **Siri errors:** the Siri helper sometimes returns "couldn't communicate with a helper application" (seen once during testing). Retry each unit up to 3 times, then stop the book with an error. Never switch voices.
- **Speed and resuming a batch:** the job is resumable and skips chapters whose audio is current. It may run several renders at once; the builder picks how many after measuring. One test ran Siri at about 5× real time and `say` at about 2×.
- **Recording the voice:** each chapter records the voice it was rendered with. For Siri that's the voice key; for `say`, the system voice identifier, read from macOS.
- **Checking the voice:** `say` can quietly use a different voice when it can't render the system voice to a file, and nothing in `say` reports it. So before every run, each engine renders a fixed reference sentence. Its duration and audio fingerprint are compared with a reference saved when the owner approved the voice; on a mismatch the run stops. *(Builder-check call, mine; this is what enforces the no-silent-fallback anti-goal for `say`.)*
- **Reusing InkChinese's exporter:** do not copy `siri_tts.py` into this repo. The builder chooses between importing it by path (configured in `deploy/distill/deploy.local.env` or similar) and moving it into a small shared package. Either way the voice name and rate are passed in as arguments: the current file hardcodes `zh-CN` + `zh-CN-D`, and has a default rate of 0.9.
- **Siri also falls back quietly:** for a voice name it doesn't know, the private route returns a default voice instead of an error. Before rendering, the exporter must confirm `zh-CN-D` appears in the route's own list of downloaded voices (`siri_tts.voices()`). The reference-clip check applies to Siri too.

### 3. Storage and deploy

- **Files:** audio lives in the existing content-addressed `MediaStore` (`distill/media.py`), not in `distill.db` as BLOBs.
- **Deploy changes:** today `media_archive()` tars and uploads *every* key the DB references on each push. With audio that would be 1–2 GB per push. The deploy is therefore changed to:
  - ask the VM which keys it already has;
  - upload only the missing ones;
  - stream them, so the VM never holds the tar and the unpacked copy at once.
  - Images benefit too. *(Builder-check call, mine.)*
- **New content table:** `chapter_audio(chapter_id PK, storage_key, text_checksum, duration_ms, voice, rate, engine, created_at)`.
- **Timings:** `chapter_audio_units(chapter_id, paragraph_id, start_ms, end_ms, marks_json NULL)`, or a JSON column on `chapter_audio`. The builder chooses.
- **Staleness:** `text_checksum` is a hash of the exact spoken text of the chapter's units, in order. If a chapter's text changes, its audio is stale. The server hides the Listen control for stale chapters, and `make_audio` regenerates them.

### 4. Serving

- **Route:** `GET /books/<slug>/audio/<chapter_id>.m4a`, `@login_required`. It must support HTTP Range (`206 Partial Content`); iOS will not play media without it. Use `Cache-Control: private` with an ETag from the storage key.
- **Timings endpoint:** `GET /api/books/<slug>/audio`. It lists, per chapter, the audio URL, duration and unit timings, with stale or missing chapters omitted.
- **Who sends the bytes:** gunicorn runs 1 worker × 4 threads (`deploy/gunicorn_config.py`), so long audio streams could block page requests.
  - **Preferred:** Flask checks auth, then hands the file to Apache via `X-Sendfile` (mod_xsendfile, path restricted to the media root).
  - **Acceptable first step:** Flask `send_file(conditional=True)` with a threads bump.
  - **Not allowed:** a bare Apache `Alias`. Distill's static files must not skip the app's allow-list (see CLAUDE.md, "Deploying Distill").

### 5. Player (PWA)

- **Audio element:** one long-lived `<audio>` element per page, created on first Listen tap so iOS's user-gesture rule is satisfied. Set `navigator.audioSession.type = 'playback'` where available. InkChinese's `app/src/speech.ts` is a working reference for iOS audio quirks.
- **Mini-player bar** at the bottom of the reader: play/pause, back 15s, forward 30s, speed (1×, 1.25×, 1.5×, 1.75×, 2×), current chapter title, and next chapter.
- **Media Session:** title, book, author and cover art; handlers for play, pause, seekbackward, seekforward, seekto, previoustrack and nexttrack.
- **End of chapter:** on `ended`, load the next chapter's audio into the same element and play it. This keeps playback going while the screen is locked. At the end of the book, stop.
- **Following the text while listening:** the reader scrolls (or pages) to the unit being spoken, and that unit gets a light highlight. If the owner scrolls away by hand, auto-follow pauses and a "Back to audio" chip appears.

### 6. Shared position and kill-safe resume

- **What's saved:** `{book_id, chapter_id, paragraph_id, seconds, rate}`, the position *within* the audio.
- **Saved locally:** to localStorage every 5s while playing, and on pause, `pagehide` and `visibilitychange` (hidden), and on chapter change. This is what survives an iOS kill.
- **Synced to the server:** through the existing progress mutation API (`shared/progress/routes.py`, `POST /progress/v2/mutations`), as the summary mode's `current` marker (`paragraph_id` + offset). Listening moves the same reading position, so no separate "listen mode" is needed. The exact seconds go into the marker so audio can resume mid-paragraph. The builder decides whether that's an existing field or a small schema addition. Mutations happen on pause, chapter change and every ~30s while playing. They go through the existing per-device sequence, so conflict handling is unchanged.
- **Which wins:** the most recent of reading or listening, by the existing rules. Listening also counts toward reading progress the way paging does. That includes the furthest position and sequential boundaries, so finishing a book by ear marks it finished.
- **Reopening Distill after a kill:**
  - If the last local event was audio, show a **"Resume listening · <chapter>, mm:ss"** control on the book page and in the reader. iOS will not autoplay, so resuming takes one tap.
  - **Reading → listening:** Listen starts at the start of the unit currently at the top of the reading view, unless that unit is the one the audio was last paused in. In that case it resumes at the saved second.
  - **Listening → reading:** the text opens at the unit being spoken.

### 7. Where to start

- **Reader:** a headphones button in the reader's top bar starts listening from the current spot.
- **Book page:** a "Listen" action beside "Read".
- **Library:** no change in the first version.

## Testing

Per CLAUDE.md, TDD:

- **Backend (pytest):**
  - spoken-text extraction per block type;
  - checksum and staleness;
  - computing unit timings when joining (feed fake per-unit durations, no real TTS);
  - the Range route (206, `Content-Range`, auth required, stale chapter → 404);
  - the timings API;
  - progress mutation accepting audio seconds.
  - The macOS voice engines sit behind one `render(text) -> (wav_path, marks)` boundary, so they can be mocked.
- **Frontend (Playwright `tests/e2e/distill.mjs`):**
  - a short fixture audio file;
  - Listen starts at the visible unit;
  - the highlight follows `timeupdate`;
  - position is in localStorage after pause;
  - reload → "Resume listening" at the saved time;
  - `ended` → next chapter loads;
  - the Media Session handlers are set.
- **Manual on an iPhone (can't be automated):**
  - lock-screen controls;
  - playing on into the next chapter while locked;
  - swiping the app away, reopening, and resuming.

## Rollout

1. Generate audio for one English and one Chinese book. Push them and test on the iPhone.
2. Then run the whole library overnight.
3. **New books publish text first.** `push_book --deploy` stays as fast as it is today. A separate `make_audio --book <slug> --deploy` renders the audio and pushes only the new audio keys and rows. The Listen control appears once audio exists. Changing the book-summary skill (outside this repo) to call it is a follow-up, not part of this build. *(Builder-check call, mine.)*

**Player errors (all cases):** any failed load or seek pauses playback and saves the position. That includes a sign-in redirect, which shows up as a non-audio response. The next time the app opens, it shows "Resume listening" along with any sign-in prompt the site needs. It never fails silently on the lock screen.

## Left to the builder

- The exact DB layout for timings.
- How to share the Siri exporter.
- How many renders to run at once.
- The X-Sendfile vs `send_file` first step.
- Mini-player visuals, matching Distill's daylight typography.
