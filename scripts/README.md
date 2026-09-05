# scripts/

One-shot CLI tools, batch jobs, and data-maintenance scripts. Grouped by purpose, not by book or chronology. Each subfolder is a Python package (`__init__.py`) so tests can import from them as `scripts.<group>.<module>`.

## Layout

| Subfolder | What lives here |
|-----------|------|
| `content/` | Summary generation, modern-English rewrite, chapter-text cleanup, slug generation, author bios. **`generate_summaries.py` is the main ingestion script.** |
| `audio/` | TTS generation (offline Gemini, batch concise/medium, single-chapter), audio-metadata backfill, audio-filename migration. |
| `images/` | Book covers, chapter illustrations (Gemini batch + sync), hero images, app icons, guide images, generic resize/recompress. |
| `categorization/` | Book-category assignment (single, batch, bulk-backfill) and master-category generation. |
| `migrations/` | One-shot schema or filename migrations (books, authors, covers, titles, JSON migration, blog-post import). Audio migration lives in `audio/`. |
| `backfills/` | Backfill existing rows after a schema or field change (slugs, chapter title case, chapter title normalization). |
| `audits/` | Mostly read-only inspections (chapter-text audits, name analyses, book-list checks, duplicate finders, blog-link validation), but **not all** — `reformat_paragraphs.py`, `strip_decorative_dividers.py`, `split_modern_paragraphs.py`, `strip_illustration_captions.py`, and `prepend_missing_titles.py` write to the DB. Read the script before assuming it's safe to run. |
| `book_fixes/` | Per-book one-shot fixes (Huck Finn chapters, Invisible Man titles, Time Machine chapters, Roman-numeral normalization). Most are historical. |
| `blog/` | Blog-post management — updating the Frankenstein AI article (`update_frankenstein_article_v3.py` is the current version; v1/v2 were superseded and deleted) and assigning header images. |
| `archive/` | Dead-end or superseded scripts (debug helpers, one-shot test-fixers, destructive cleanup like `delete_test_books.py`). Do not run without re-reading first. |

## Cross-listed scripts (single home, mentioned in multiple categories)

- `audio/migrate_audio_filenames.py` — audio-only migration, kept with audio scripts.
- `blog/assign_blog_header_images.py` — touches images but is blog-scoped.

## Destructive / one-shot — read before running

- `archive/delete_test_books.py` — removes test-book rows from the DB.
- `book_fixes/*` — most assume the database is in a specific historical state.
- `migrations/*` — already applied to production; only re-run on a fresh database.
- `backfills/*` — idempotent in principle, but verify the current schema first.

## How tests (and scripts) import these

`backend` and `scripts` are installed as real, editable packages (see the repo-root
`pyproject.toml`; `pip install -e .`), so every script and test imports the package style:

```python
from scripts.content.generate_summaries import SummaryGenerator
```

There is no `sys.path` manipulation anywhere in `scripts/`, `backend/`, or `tests/conftest.py` —
if you find yourself reaching for `sys.path.insert`, that's a sign the import should be
`from scripts.<group>.<module> import ...` or `from backend import <module>` instead.
