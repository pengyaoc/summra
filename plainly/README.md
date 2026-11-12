# Plainly

Plainly makes public-domain classics easier to read. It is one of the two apps on the Summra platform ([root README](../README.md)). The reader, progress sync, Kindle mode and audio playback come from [`shared/`](../shared/README.md); this folder holds Plainly's content, pages and tooling.

Every book has:

- **A Plain English rewrite** of each chapter, shown beside the original (desktop) or on its own (mobile and Kindle).
- **Two book summaries.** A ~500-word short one (spoiler-free for fiction) and a 2,000–3,000-word full one.
- **Chapter summaries**, with an optional spoiler-protected reveal.
- **Illustrations** for each chapter, with a lightbox.
- **Audio** for summaries, recorded ahead of time.
- **Discovery:** curated home carousels, categories, author hubs and related books.

The library has about 90 Project Gutenberg books, 70+ of them with full Plain English text. It installs as a PWA. Sign-in and reading progress are optional, and the blog is off by default.

## Layout

```
plainly/
├── app_base.py        App factory: registers blueprints and plugs into the shared reader platform
├── app.py             Dev entry point (python plainly/app.py → :5001)
├── app_prod.py        Prod entry point (gunicorn plainly.app_prod:app); adds /health
├── config.py          Paths, models, rate limits, feature flags
├── models.py          Content DB (data/database.db): books, chapters, summaries, categories, authors…
├── reader_config.py   Plainly's ReaderConfig: modes (original / Plain English / side by side), labels
├── audio_app.py       Plainly's description for shared/audio's recorder
├── routes/            Page and JSON API blueprints
├── frontend/
│   ├── templates/     SPA shell, manifest, sitemap
│   └── static/        css/, js/ (app.min.js is built by esbuild), covers/, illustrations/, audio/
│                      static/shared → ../../../shared/static (symlink)
└── scripts/           Run as python -m plainly.scripts.<group>.<name>; index in scripts/README.md
    ├── content/       generate_summaries (ingestion), generate_modern_english, verse passages
    ├── audits/        validate_chapter_split, reformat_paragraphs, split_modern_paragraphs…
    ├── audio/         record_summaries
    ├── images/        covers, chapter illustrations, hero images, app icons
    └── …              categorization/, migrations/, backfills/, book_fixes/, blog/, archive/
```

Plainly uses two databases. Content is in `data/database.db`: it is large and can be rebuilt from `data/books/`. Users and reading progress are in `data/summra.db`: it is small and can't be replaced.

## Run

```bash
python plainly/app.py                 # http://localhost:5001  (5000 is taken by macOS ControlCenter)
```

```bash
PORT=5002 python plainly/app.py       # a second session or worktree
```

After changing JS under `frontend/static/js/` or `shared/static/js/`, rebuild the bundle with `npm run build`. CI checks that it is fresh.

## Add a book

Always dry-run first. The parser is tuned for prose novels with `CHAPTER` markers, and the two-level `PART → CHAPTER` variant. It doesn't handle anthologies or aphoristic works.

```bash
venv/bin/python -m plainly.scripts.content.generate_summaries data/books/<file>.txt --dry-run
```

```bash
venv/bin/python -m plainly.scripts.content.generate_summaries data/books/<file>.txt --parse-only
```

```bash
venv/bin/python -m plainly.scripts.audits.validate_chapter_split --book-id <id> --llm-digest
```

The full checklist and the known-bad book types are in [`docs/plainly/ingestion_workflow.md`](../docs/plainly/ingestion_workflow.md). The Plain English process is in [`docs/plainly/agent_plain_english_workflow.md`](../docs/plainly/agent_plain_english_workflow.md) and [`docs/plainly/plain_english_checklist.md`](../docs/plainly/plain_english_checklist.md).

## Audio

Summaries are recorded on the owner's Mac with macOS voices, never on the server:

```bash
venv/bin/python -m plainly.scripts.audio.record_summaries --book <slug> --dry-run
```

Chapter audio uses the shared recorder: `python -m shared.audio.make_audio --app plainly …`. The server only plays recordings that already exist.

## Configuration

`config.py` holds the settings:

- `DATABASE_PATH`, `USER_DATABASE_PATH`: `data/database.db` and `data/summra.db`.
- `GEMINI_API_KEY`: read from the environment. Used only by the ingestion and rewrite scripts.
- `SUMMARY_CONFIGS`, `PLAIN_TEXT_MODEL`, `MAX_REQUESTS_PER_MINUTE`, `MAX_TOKENS_PER_MINUTE`.
- `FEATURE_AUTH` (on) registers sign-in and progress. Whether anyone is actually signed in depends on `SUMMRA_AUTH_MODE` (`off` / `optional` / `required`), set per host.
- `FEATURE_BLOG` (off) turns on the editorial blog.

## Tests

```bash
venv/bin/python -m pytest tests/plainly tests/shared -v
```

```bash
cd tests/e2e && node smoke.mjs        # against a running server; see tests/e2e/README.md
```

## API (selected)

Pages: `/`, `/discover`, `/books`, `/books/<slug>`, `/books/<slug>/summary`, `/books/<slug>/chapters/<n>`, `/categories[/<id>]`, `/authors/<slug>`, `/blog[/<slug>]`, plus `manifest.json`, `robots.txt` and `sitemap.xml`.

JSON: `/api/books[/<id>]`, `/api/books/<id>/summary/<type>`, `/api/books/<id>/chapters[/<n>]`, `/api/books/<id>/categories`, `/api/books/<id>/related`, `/api/categories…`, `/api/authors/<slug>[/books]`, `/api/discover/carousels`. The reader, progress and audio APIs come from `shared/`.

## Troubleshooting

- **"no such table: books".** `data/database.db` is missing or empty. Restore one, or ingest a book.
- **Gemini rate limits.** The script pauses automatically. A hard 429 usually means you need a paid tier.
- **Chapter detection looks wrong.** Read the `CHAPTER BREAKDOWN` block printed by `--dry-run`, and check the known-bad book types in `docs/plainly/ingestion_workflow.md`.

## Docs

[`docs/plainly/PRD.md`](../docs/plainly/PRD.md) (product), [`docs/plainly/ERD.md`](../docs/plainly/ERD.md) (engineering), and the workflows in [`docs/plainly/`](../docs/plainly/).

## Acknowledgments

Project Gutenberg (texts and covers), Google Gemini (summaries, rewrites, illustrations), Unsplash (blog images), Flask, Workbox and Playwright.
