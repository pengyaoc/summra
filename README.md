# Summra — Read the Classics in Plain English

Summra is a web app that makes public-domain classics easier to read. Every book is paired with two AI-generated summaries (a short overview and a fuller summary), chapter-by-chapter summaries, AI-generated chapter illustrations, optional audio narration, and — most importantly — a **sentence-by-sentence rewrite of the original text in modern English**, viewable side-by-side with the original.

Currently ships with ~90 books from Project Gutenberg covering Dickens, Austen, Doyle, Tolstoy, Twain, Hardy, Dostoyevsky, the Greek classics, philosophy, and more.

## What it does

- **Two summary lengths per book:** a ~500-word short summary (spoiler-free for fiction) and a ~2,000–3,000-word full summary.
- **Per-chapter summaries** with optional spoiler-protected reveal, plus the full original chapter text.
- **Plain English rewrites** of every chapter, rendered side-by-side with the original on desktop or stand-alone on mobile.
- **AI-generated chapter illustrations** with a click-to-zoom lightbox.
- **Text-to-speech** for summaries (and chapters where pre-generated), via the Google Gemini 2.5 Flash TTS API.
- **Kindle-style reading UI:** page-based pagination, font/size/theme settings (light/dark/sepia), progress indicator, sticky chapter header.
- **Discovery:** home page with curated carousels (Popular, Easy to Read, Read in a Day, by category, by author), a full categories page, an authors hub, and a related-books carousel on each book.
- **PWA:** installable on iOS/Android/desktop, offline-cached pages, offline fallback page.
- **Optional auth + reading progress** (behind a feature flag — see below).
- **Optional editorial blog** (behind a feature flag).

## Project layout

```
summra/
├── backend/
│   ├── app_base.py          # Shared Flask routes (used by dev + prod)
│   ├── app.py               # Dev entry point — registers live Gemini TTS generation
│   ├── app_prod.py          # Prod entry point — TTS serves pre-generated files only
│   ├── config.py            # Models, rate limits, feature flags, paths
│   ├── models.py            # Content DB (books, chapters, summaries, categories, authors, blog…)
│   ├── user_models.py       # User DB (users, reading_progress, chapter_completion)
│   ├── auth_routes.py       # Auth blueprint (gated by FEATURE_AUTH)
│   ├── progress_routes.py   # Reading-progress blueprint (gated by FEATURE_AUTH)
│   ├── gemini_tts_handler.py# Gemini 2.5 Flash TTS client
│   └── tts_utils.py         # Provider-agnostic chunking, stitching, cache lookup
├── frontend/
│   ├── templates/           # index.html (SPA shell), offline.html, sitemap.xml
│   └── static/              # css/, js/, covers/, illustrations/, audio/, guides/, images/, manifest.json, service-worker.js
├── scripts/
│   ├── content/             # generate_summaries.py (main ingestion), modern-English rewrite, slugs, chapter cleanup, author bios
│   ├── audio/               # Offline TTS batches, audio backfill, filename migration
│   ├── images/              # Cover download, chapter illustrations, hero images, app icon, resize helpers
│   ├── categorization/      # Category assignment + master-category generation
│   ├── migrations/          # One-shot schema migrations
│   ├── backfills/           # Idempotent backfills after schema/field changes
│   ├── audits/              # Read-only inspections (chapter-text audit, validate_chapter_split, etc.)
│   ├── book_fixes/          # Per-book one-shot fixes (mostly historical)
│   ├── blog/                # Blog import + Unsplash header-image assignment
│   ├── archive/             # Dead-end or destructive scripts — read before running
│   └── README.md            # Per-folder index
├── data/
│   ├── books/               # Source .txt files (Project Gutenberg)
│   ├── character_briefs/    # Per-book character/style briefs for illustration consistency
│   └── database.db          # Content SQLite database (gitignored)
├── summra.db                # User SQLite database (gitignored, project root)
├── deploy/                  # nginx, systemd, gunicorn, GCP setup scripts (e2-micro + e2-small)
├── docs/                    # PRD.md, ERD.md, USAGE.md, marketing/, archive/
├── tests/                   # pytest unit suite + e2e/ Playwright harness
├── CLAUDE.md                # Instructions for Claude Code sessions (work log, TDD, parser quirks)
├── WORK_LOG.md              # Append-only log of completed and in-progress work
├── requirements-prod.txt    # Prod deps (no TTS model)
├── backend/requirements.txt # Dev deps
└── .env.example
```

Two databases are intentional: content lives in `data/database.db` (large, regeneratable from `data/books/`); user accounts and reading progress live in `summra.db` at the project root (small, irreplaceable).

## Getting started

### Prerequisites

- Python 3.8+
- A Google Gemini API key — https://aistudio.google.com/app/apikey (free tier is enough to run the app; ingesting new books burns through the free quota quickly)
- Optional: an Unsplash access key (`UNSPLASH_ACCESS_KEY`) if you want to use `scripts/blog/assign_blog_header_images.py`

### Install

```bash
git clone <repo>
cd summra
./setup.sh                     # creates venv, installs deps, copies .env.example
# then edit .env and set GEMINI_API_KEY
```

Or manually:

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env           # then add GEMINI_API_KEY
```

### Run the app

```bash
python backend/app.py
```

The server binds **`http://localhost:5001`** (port 5000 is reserved by macOS ControlCenter). Override with `PORT=5002 python backend/app.py` if needed.

The repository ships without `data/database.db` (it's gitignored). To get a working app, either restore your own DB or ingest books — see below.

## Ingesting a book

```bash
PYTHONPATH=backend venv/bin/python scripts/content/generate_summaries.py data/books/your_book.txt
```

Common options:

```bash
# Just parse chapters, no LLM calls (free, fast — useful for verifying chapter detection):
... generate_summaries.py data/books/pg1342.txt --parse-only

# Inspect detected chapter boundaries without writing to the DB:
... generate_summaries.py data/books/pg1342.txt --dry-run

# Batch a directory:
... generate_summaries.py data/books/ --batch

# Override metadata:
... generate_summaries.py data/books/pg1342.txt --title "Pride and Prejudice" --author "Jane Austen"
```

The script auto-detects chapters, generates a combined short + full summary in a single Gemini call, optionally generates per-chapter summaries, and persists raw LLM responses to `data/llm_responses/` so a parser bug doesn't force a re-call.

**Always dry-run first.** The chapter parser is tuned for prose novels with `CHAPTER I/II/III` style markers (and the two-level `PART I → CHAPTER I` variant). It does **not** handle anthologies, aphoristic non-chaptered works, or non-English structural conventions — see `CLAUDE.md` "Book Ingestion Workflow" for the dry-run / validate workflow and the canonical list of known-bad book classes.

### Generating audio (offline batches)

Real-time TTS via the dev server (`backend/app.py`) uses the **Gemini 2.5 Flash TTS** API and caches the resulting WAV files under `frontend/static/audio/`. For pre-generating audio in bulk:

```bash
# All concise summaries in the DB:
venv/bin/python scripts/audio/batch_generate_concise_audio.py

# All medium summaries:
venv/bin/python scripts/audio/batch_generate_medium_audio.py

# Per-chapter audio for a specific book:
venv/bin/python scripts/audio/generate_gemini_audio_batch_offline.py --book-id 47
```

Production (`backend/app_prod.py`) does **not** generate TTS on demand — it only serves files pre-generated by these scripts. The TTS pipeline is split this way so the production VM can stay small (e2-small or even e2-micro).

## Configuration

`backend/config.py` is the single source of truth:

- **`DATABASE_PATH`** — `data/database.db`
- **`GEMINI_API_KEY`** — read from env
- **`SUMMARY_CONFIGS`** — model + word-count target per summary type
- **`PLAIN_TEXT_MODEL`** — model used for modern-English rewrites (currently `gemini-3.1-flash-lite`)
- **`GEMINI_TTS_MODEL`**, **`GEMINI_TTS_VOICE`** — TTS model + voice (Kore by default; options: Puck, Charon, Kore, Fenrir, Aoede, Sulafat)
- **`MAX_REQUESTS_PER_MINUTE`** / **`MAX_TOKENS_PER_MINUTE`** — Gemini rate-limiter caps
- **`FLASK_HOST`**, **`FLASK_PORT`**, **`FLASK_DEBUG`**
- **`FEATURE_AUTH`** — gate auth, reading-progress, active Save-for-Offline (default `False`)
- **`FEATURE_BLOG`** — gate the editorial blog (default `False`)

Both feature flags default off so the routes return clean 404s and the relevant frontend buttons are server-stripped from the SPA shell.

## Tests

### Backend (pytest)

```bash
PYTHONPATH=backend venv/bin/python -m pytest tests/ -v
```

40+ test files cover chapter detection, the LLM client + rate limiter, the bulk-summary parser, validators, the database layer, and several specific historical bugs (preface detection, two-level TOC, multi-line titles, dotted abbreviations).

### Frontend (headless Chromium)

```bash
cd tests/e2e && npm install && npx playwright install chromium     # one-time
python backend/app.py &                                              # in another terminal
cd tests/e2e && node smoke.mjs
```

`smoke.mjs` visits a configurable set of routes (override with `PATHS=/,/book/104,/explore`), screenshots each one, and exits non-zero on any non-200, console error, or failed first-party request. See `tests/e2e/README.md` for the full flag set.

### Post-ingest validation

```bash
PYTHONPATH=backend venv/bin/python scripts/audits/validate_chapter_split.py --book-id <id> --llm-digest
```

Deterministic checks (chapter count, monotonic numbering, coverage) plus an optional LLM digest spot-check.

## Parallel sessions (git worktrees)

If you run multiple Claude Code sessions on this repo simultaneously, give each its own worktree — never share a working directory.

```bash
git worktree add .claude/worktrees/<name> -b <branch>
git worktree list
git worktree remove .claude/worktrees/<name>
```

Per-session isolation requirements (Flask port, `venv/`, `tests/e2e/node_modules/`, `data/database.db`) are documented in detail in `CLAUDE.md` under "Parallel Sessions".

## API endpoints (selected)

Page routes (server-rendered shell + hash-based SPA):

- `GET /` — Home (Discover carousels)
- `GET /discover` — Discover page
- `GET /books` — All books grid
- `GET /books/<slug>` — Book detail
- `GET /books/<slug>/summary` — Full summary page
- `GET /books/<slug>/chapters/<n>` — Chapter page
- `GET /categories`, `GET /categories/<id>` — Category index + detail
- `GET /authors/<author_slug>` — Author hub
- `GET /blog`, `GET /blog/<slug>` — Blog (FEATURE_BLOG)
- `GET /offline`, `GET /service-worker.js`, `GET /robots.txt`, `GET /sitemap.xml` — PWA + SEO

JSON API:

- `GET /api/books` — List books
- `GET /api/books/<id>` — Book detail
- `GET /api/books/<id>/summary/<type>` — Summary (concise | medium | comprehensive)
- `GET /api/books/<id>/chapters` — Chapter list
- `GET /api/books/<id>/chapters/<n>` — Single chapter (incl. modern-English text, illustration URL)
- `GET /api/books/<id>/categories`, `GET /api/books/<id>/related`
- `GET /api/categories`, `GET /api/categories/<id>`, `GET /api/categories/<id>/books`
- `GET /api/authors/<slug>`, `GET /api/authors/<slug>/books`
- `GET /api/books/by-author/<name>`
- `GET /api/discover/carousels` — Curated carousels for the Discover page
- `GET /api/summary-configs` — Summary config for the frontend
- `POST /api/tts/generate` — Generate (dev) or fetch (prod) TTS audio for a given text id

Auth + progress endpoints register under blueprints when `FEATURE_AUTH=True` — see `backend/auth_routes.py` and `backend/progress_routes.py`.

## Deployment

`deploy/DEPLOY.md` walks through the GCP path: e2-micro (free tier, no on-demand TTS) or e2-small (~$13/mo, full TTS). The directory ships nginx configs, systemd unit files, gunicorn configs, and a `setup-e2small.sh` automation script.

## Troubleshooting

**"no such table: books"** — `data/database.db` is empty or missing. Either restore a database, or ingest at least one book with `scripts/content/generate_summaries.py`.

**Port 5000 already in use** — That's macOS ControlCenter (AirPlay Receiver). Use 5001 (the default) or pick another with `PORT=`.

**Gemini rate-limit errors** — The rate limiter caps at `MAX_REQUESTS_PER_MINUTE` (10) and `MAX_TOKENS_PER_MINUTE` (250 000). Ingesting many books in parallel will hit these. The script pauses automatically; if you hit a hard 429 you may need a paid tier.

**Chapter detection looks wrong** — Run `generate_summaries.py … --dry-run` and read the `CHAPTER BREAKDOWN` block. The parser handles standard prose novels; see `CLAUDE.md` for known-bad book classes (anthologies, aphoristic works) that should be skipped.

**TTS isn't generating in production** — That's by design. `app_prod.py` only serves pre-generated audio. Run the offline batch scripts (`scripts/audio/`) and deploy the resulting WAV files.

## Acknowledgments

- **Project Gutenberg** for the source texts and cover images
- **Google Gemini** for summaries, modern-English rewrites, chapter illustrations, and TTS
- **Unsplash** for blog header images
- **Flask**, **Workbox**, **Playwright** for the underlying machinery

## License

For personal and educational use. Source texts must be in the public domain or you must hold appropriate rights.
