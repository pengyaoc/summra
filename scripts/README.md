# scripts/

One-shot CLI tools, batch jobs, and data-maintenance scripts. Grouped by purpose, not by book or chronology. Each subfolder is a Python package (`__init__.py`) so tests can import from them as `scripts.<group>.<module>`.

## Layout

| Subfolder | What lives here |
|-----------|------|
| `content/` | Summary generation, modern-English rewrite, chapter-text cleanup, slug generation, author bios. **`generate_summaries.py` is the main ingestion script.** |
| `audio/` | TTS generation (offline Gemini, batch concise/medium, single-chapter), audio-metadata backfill, audio-filename migration. |
| `images/` | Book covers, chapter illustrations (Gemini batch + sync), hero images, app icons, guide images, generic resize/recompress. |
| `categorization/` | Book-category assignment (single, batch, bulk-backfill) and master-category generation. |
| `migrations/` | One-shot schema or filename migrations (books, authors, covers, titles, JSON migration). Audio migration lives in `audio/`. |
| `backfills/` | Backfill existing rows after a schema or field change (slugs, chapter title case, chapter title normalization). |
| `audits/` | Read-only inspections: chapter-text audits, name analyses, book-list checks, duplicate finders. Safe to run anytime. |
| `book_fixes/` | Per-book one-shot fixes (Huck Finn chapters, Invisible Man titles, Time Machine chapters, Roman-numeral normalization). Most are historical. |
| `blog/` | Blog-post management — adding/updating the Frankenstein AI article and assigning header images. |
| `archive/` | Dead-end or superseded scripts (debug helpers, one-shot test-fixers, destructive cleanup like `delete_test_books.py`). Do not run without re-reading first. |

## Cross-listed scripts (single home, mentioned in multiple categories)

- `audio/migrate_audio_filenames.py` — audio-only migration, kept with audio scripts.
- `blog/assign_blog_header_images.py` — touches images but is blog-scoped.

## Destructive / one-shot — read before running

- `archive/delete_test_books.py` — removes test-book rows from the DB.
- `book_fixes/*` — most assume the database is in a specific historical state.
- `migrations/*` — already applied to production; only re-run on a fresh database.
- `backfills/*` — idempotent in principle, but verify the current schema first.

## How tests import these

`tests/conftest.py` adds every `scripts/<group>/` folder to `sys.path` at collection time, so tests can write either:

```python
from generate_summaries import SummaryGenerator                 # bare-module style
from scripts.content.generate_summaries import SummaryGenerator  # package style
```

Both work. New tests should prefer the package style (`scripts.content.generate_summaries`) — it's explicit about which group the script belongs to.
