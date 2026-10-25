# Distill Phase 2 — Book Format, Import and Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define Distill's `book.json` format, store books in `data/distill.db` (content, chapters, image BLOBs, reader index), provide a `push_book.py` import command, and convert the 54 existing HTML summaries into that format.

**Architecture:**
- `distill/` becomes a real package:
  - `book_format.py` validates a book folder.
  - `models.py` holds `DistillDatabase`, which owns the content DB and implements `shared.reader.index.ReaderIndexMixin`'s hooks over blocks, using reader mode `'summary'`.
  - `scripts/push_book.py` validates and imports.
  - `scripts/convert_html_summaries.py` turns the old tabbed HTML pages into book folders and writes a report.
- Each top-level block of a chapter is one reader unit. The unit's stored text is the block's JSON. `DistillDatabase` overrides the mixin's word-count and quote helpers so counting and recovery work on the block's visible text, not on JSON syntax.

**Tech Stack:** Python 3.11+, SQLite, Pillow (AVIF decode → JPEG/PNG), BeautifulSoup 4 (converter only, local tool), pytest.

**Spec:** `docs/superpowers/specs/2026-10-24-distill-design.md` §5.2–5.4 and §5.6. Phase 1 (the repo split) is done: `shared/reader/index.py` is the mixin, and `plainly/models.py` is the reference host.

## Global Constraints

- Format version is `1`. Block types are `p`, `h`, `ul`, `ol`, `quote`, `keypoints`, `table`, `image`, and no others. Inline markup is `**bold**` and `*italic*` only. No links and no raw HTML.
- Images are `images/<file>.(jpg|png)` only. No AVIF, WebP or SVG in a book folder.
- `sources` is stored, not read in the reader. Worklog is never imported.
- The Overview is reader chapter 0 with the title "Overview". It is stored as a chapter row with ordinal 0 and `part_title` NULL.
- The content DB path is `data/distill.db`. Converter output and work dirs live under `data/distill_import/`, which `data/**` in .gitignore already ignores. Nothing under `data/` is committed. The repo is public.
- `shared/` must not import `distill`. The layering guard stays green.
- Re-importing a slug replaces that book's chapters and images in one transaction and keeps its `books.id`. Reading progress is keyed by `book_id`, so the id must stay stable.
- No HTTP upload endpoint. `--deploy` is phase 4, not this plan.
- TDD: failing test first. Full suite green at each commit, with the pytest count in the commit body.

## Review Focus

1. **Re-import changing `books.id`.** Saved progress would orphan. Task 2 tests that re-import keeps the id and bumps the reader version.
2. **Blocks whose visible text is empty**, such as an image with no caption. Word count is 0, but the unit must still exist and a marker must still resolve. Task 2 tests it.
3. **Malformed inline markup** like `**unclosed` or `<b>`. Validation must reject it with the block's location, not crash. Task 1 tests it.
4. **Hotlinked images that 404 or rate-limit.** The converter must finish, list the failures and never hang. Task 4 tests that a fake fetcher raising, or returning 429 then 200, is handled with bounded retries.
5. **CJK book (`quanqiutongshi`).** The word count must not be ~0 for Chinese text. Task 2 counts CJK characters as words when `lang` is `zh`, matching the skill's "CJK chars" unit.

---

### Task 1: `distill/book_format.py` — validator

**Files:**
- Create: `distill/book_format.py`
- Create: `tests/distill/__init__.py`, `tests/distill/test_book_format.py`

**Interfaces:**
- Produces:
  - `FORMAT_VERSION = 1`
  - `BLOCK_TYPES = frozenset({'p','h','ul','ol','quote','keypoints','table','image'})`
  - `load_book(folder: Path) -> dict` reads `book.json`.
  - `validate_book(book: dict, folder: Path) -> list[str]`. Returns human-readable errors such as `"parts[1].chapters[3].blocks[2]: unknown block type 'div'"`. An empty list means valid.
  - `block_text(block: dict) -> str` returns the visible text with inline markers stripped:
    - `p`/`h`/`quote`: the text
    - `ul`/`ol`/`keypoints`: the items joined by `\n`
    - `table`: header and cells joined by spaces
    - `image`: the caption or `''`
  - `iter_chapters(book) -> list[tuple[Optional[str], str, list[dict]]]` yields `(part_title, chapter_title, blocks)` in reading order, with the Overview first as `(None, 'Overview', overview_blocks)` when the overview is non-empty.

- [ ] **Step 1: Write the failing tests.** Use a minimal valid book fixture built in `tmp_path`, with one JPEG written by Pillow. Tests:
  - `test_valid_book_has_no_errors`
  - `test_unknown_block_type_reported_with_path`
  - `test_missing_image_file_reported`
  - `test_webp_image_rejected`
  - `test_raw_html_and_links_rejected` (`'<b>x</b>'` and `'[a](http://x)'` in a `p`)
  - `test_unbalanced_bold_rejected` (`'**x'`)
  - `test_required_fields` (missing `slug`/`title`, or `format != 1`)
  - `test_block_text_strips_markup` (`'**a** *b*'` → `'a b'`)
  - `test_iter_chapters_overview_first`
- [ ] **Step 2: Run them to verify they fail.** `venv/bin/pytest tests/distill/test_book_format.py -v` should fail with ModuleNotFoundError.
- [ ] **Step 3: Implement.** Check the slug with `^[a-z0-9][a-z0-9-]*$` and `lang` with `^[a-z]{2}$`. Validate that tables have a list header and list rows. Check the image extension against the file's actual format, using Pillow `Image.open(...).format in {'JPEG','PNG'}`.
- [ ] **Step 4: Run the full suite. Commit** "Add Distill book format validator".

### Task 2: `distill/models.py` — `DistillDatabase` with import and reader hooks

**Files:**
- Create: `distill/config.py`. `BASE_DIR` is the repo root, `DATABASE_PATH = BASE_DIR/'data'/'distill.db'` and `USER_DATABASE_PATH = BASE_DIR/'data'/'distill_user.db'`.
- Create: `distill/models.py`
- Test: `tests/distill/test_models.py`

**Interfaces:**
- Consumes: `shared.reader.index.ReaderIndexMixin` and `create_reader_tables`, plus Task 1's `load_book`, `validate_book`, `iter_chapters` and `block_text`.
- Produces: `class DistillDatabase(ReaderIndexMixin)` with `__init__(db_path: Path)`. The schema is:
  - `books(id INTEGER PK, slug TEXT UNIQUE NOT NULL, title, author, lang, cover_image_id INTEGER NULL, sources TEXT /*JSON*/, imported_at TIMESTAMP, content_checksum TEXT)`
  - `chapters(id INTEGER PK, book_id REFERENCES books(id) ON DELETE CASCADE, ordinal INTEGER, part_title TEXT NULL, title TEXT, blocks TEXT /*JSON list*/)`
  - `images(id INTEGER PK, book_id REFERENCES books(id) ON DELETE CASCADE, name TEXT, mime TEXT, data BLOB, UNIQUE(book_id,name))`
  - `create_reader_tables(cursor)`

  Methods:
  - `import_book(folder: Path) -> int`. Validates first (raises `ValueError` with all errors joined), then upserts by slug, keeping the id. In one transaction it deletes and re-inserts that book's chapters and images, then returns the book id. Image blocks' `src` stays as the file name under `images/`.
  - `get_book(book_id) -> Optional[dict]` returns id, slug, title, author, lang, sources (parsed), cover_image_id and imported_at.
  - `get_book_by_slug(slug) -> Optional[dict]`
  - `list_books() -> list[dict]`, most recently imported first.
  - `get_chapters(book_id) -> list[dict]` returns id, ordinal, part_title, title and blocks (parsed).
  - `get_image(book_id, name) -> Optional[tuple[str, bytes]]` returns the mime and the data.
  - **Reader hooks:**
    - `_reader_load_book` returns `{'id','verse': False}`.
    - `_reader_load_chapters` maps rows to `{'id','chapter_number': ordinal,'chapter_title': title,'blocks': ...}`.
    - `_reader_chapter_units` returns `{'summary': [json.dumps(b, ensure_ascii=False, sort_keys=True) for b in blocks], 'original': [], 'plain': []}`.
    - `_reader_plain_coverage` returns `False`.
    - `_reader_source_checksum` is a sha256 over `(id, ordinal, title, part_title, blocks)`.
    - `_reader_structure` returns the same shape `plainly/models.py` returns, with parts as sections. Read Plainly's implementation and mirror the keys.
  - **Overrides:**
    - `_reader_word_count(text)` parses the unit JSON when it is a block (falling back to the raw text) and counts words in `block_text`. For `lang == 'zh'` content it counts CJK characters plus Latin words. Use a regex `[一-鿿]` count plus `\b\w+\b` on the rest. Because the mixin calls it as a static or class helper without a book, apply the CJK rule to any text that contains CJK characters.
    - `_reader_normalize_quote(text)` applies the same logic to the block's visible text.
  - Library hooks that `shared/progress/routes.py` documents: implement every method in its `content_db` surface docstring (`library_books`, `chapter_titles` and the rest). Read the docstring for the exact names and shapes.

- [ ] **Step 1: Write the failing tests.**
  - `test_import_round_trip`: chapters in order, the Overview at ordinal 0, the image retrievable with mime `image/jpeg`.
  - `test_reimport_keeps_book_id_and_bumps_reader_version` (Review Focus 1)
  - `test_invalid_book_is_not_imported` (the DB is unchanged, and the ValueError message lists the errors)
  - `test_manifest_counts_blocks_as_units`: units equal the total blocks, and `terminal_paragraph_id` is the last chapter's last block.
  - `test_word_count_uses_visible_text_not_json`: a `p` block `'one two three'` counts 3.
  - `test_image_block_without_caption_is_a_unit` (Review Focus 2): word_count 0, and the marker resolves.
  - `test_cjk_text_counts_characters` (Review Focus 5)
  - `test_recover_marker_by_quote_after_reimport`: a marker saved on block 3 resolves to the same block after a block is inserted before it.
- [ ] **Step 2: Run them and confirm they fail.** **Step 3: Implement.** **Step 4: Run the full suite, then commit** "Add Distill content database with reader index hooks".

### Task 3: `distill/scripts/push_book.py` — import CLI

**Files:**
- Create: `distill/scripts/__init__.py`, `distill/scripts/push_book.py`
- Test: `tests/distill/test_push_book.py`

**Interfaces:**
- `main(argv: list[str]) -> int`, with the usage `push_book.py <folder> [--dry-run] [--db PATH]`. The default `--db` is `distill.config.DATABASE_PATH`.
  - It prints the title, the chapter count, the total words (computed with `block_text`), the image count and the image bytes. On errors it prints each one and returns 1.
  - `--dry-run` returns 0 without touching the DB.
  - Otherwise it imports and prints `Imported <slug> as book <id>`.
- Run it as `venv/bin/python -m distill.scripts.push_book <folder>`.

- [ ] Tests:
  - `test_dry_run_does_not_create_db`
  - `test_import_prints_id_and_returns_0`
  - `test_invalid_folder_returns_1_and_lists_errors`

  Implement, run the full suite, then commit "Add push_book import command".

### Task 4: `distill/scripts/convert_html_summaries.py` — one-time converter

**Files:**
- Create: `distill/scripts/convert_html_summaries.py`
- Create: `distill/requirements-tools.txt` (`beautifulsoup4`, a local-only tool dependency; install it into the venv)
- Test: `tests/distill/test_convert_html.py`, plus small hand-written fixture pages under `tests/distill/fixtures/`

**Interfaces:**
- `convert_page(html: str, slug: str, out_dir: Path, fetch: Callable[[str], bytes]) -> PageReport`. It writes `out_dir/<slug>/book.json` and `images/`.
- `PageReport` is a dataclass with these fields:
  - `slug`, `title`, `chapters: int`, `words: int`
  - `images_embedded`, `images_downloaded`, `images_failed: list[str]`
  - `dropped: list[str]` (a tag/class summary of anything not mapped)
  - `empty_chapters: list[str]`
  - `flagged: bool`
- `main(argv)`, with the usage `convert_html_summaries.py <src_dir> --out <dir> [--only slug,...]`. It writes `<out>/report.md` and `<out>/report.json`, plus a "likely duplicates" section that pairs titles with the same normalised title prefix, such as the two *Abundance* files.
- `fetch` defaults to a urllib getter with a `User-Agent`, a 20 s timeout, at most 4 attempts with exponential backoff on 429/5xx (1, 2, 4 s), a 1 s pause between downloads, and a disk cache at `<out>/_cache/<sha1(url)>`.

**Mapping rules.** The real pages vary, so survey them first: run a quick class/tag census over the 54 files in `/Users/pengyao/Library/Mobile Documents/iCloud~md~obsidian/Documents/pengyao_vault/03-resources/book-summaries/`. Read-only; never write there.
- **Title and author:** from `.hero` (h1 and `.subtitle`), falling back to `<title>`.
- **Tabs:** `div.tab-content[id^=tab-]`.
  - The `overview` tab becomes `overview` blocks.
  - `sources` becomes `sources`.
  - `worklog` is dropped silently, as is any tab whose id contains `worklog`.
  - Every other tab is a part, with its title from the matching `.tab-btn` text.
- **Chapters within a part:** each `h3`, or `div.chapter`/`section.chapter` with its own heading, starts a chapter. Its title is the heading's text, without the `.chapter-num`/`.eyebrow` decoration (put the number in front, as in "3. Title", when present). Content before the first chapter heading in a part (a `.part-intro`) becomes a chapter titled with the part title plus " — Introduction" only if it has text. Otherwise it is dropped.
- **Blocks:**
  - `p` → `p` (`.lead` too)
  - `h4`/`h5` → `h`
  - `ul`/`ol` → list
  - `ul.keypoints`, `.chapter-points` and `.keypoints-wrap` → `keypoints`, dropping the `.kp-label`/`.key-points-label` label
  - `blockquote` and `.callout` → `quote`
  - `table` → `table`
  - `figure`/`img` → `image`, with the caption from `figcaption` minus `.credit`
  - inline `b`/`strong` → `**`, and `i`/`em` → `*`
  - links keep their text
  - everything else is unwrapped to text where it has text, and recorded in `dropped` where it doesn't
- **Images:**
  - `data:` URIs are decoded.
  - `http(s)` sources are fetched with `fetch`.
  - Each image is opened with Pillow and saved as JPEG at quality 82, or as PNG if it has alpha or a palette with few colours.
  - Anything wider than 1600 px is downscaled to 1600.
  - SVG can't be opened by Pillow, so it is recorded as failed (2 known).
  - The first image in the hero, if any, becomes `cover`.
- **Language:** `lang` is `zh` if more than 30% of the text characters are CJK, otherwise `en`.
- **Flags:** a page is flagged if it has `chapters == 0`, any `dropped` with text, `empty_chapters`, or `images_failed`.

- [ ] **Step 1: Write the failing tests** over 3 tiny fixture pages that you write by hand, modelled on the real structure:
  - (a) h3 chapters plus keypoints, a table and an inline data-URI PNG
  - (b) div.chapter + chapter-num, with no overview tab
  - (c) a hotlinked image

  Tests:
  - `test_tabs_become_parts_and_overview`
  - `test_worklog_dropped`
  - `test_keypoints_and_table_blocks`
  - `test_inline_markup_converted`
  - `test_data_uri_image_written_as_jpeg_or_png`
  - `test_hotlink_retries_on_429_then_succeeds`, with a fake fetch returning 429 twice and then bytes, and the sleep patched out
  - `test_hotlink_failure_reported_not_raised`
  - `test_output_passes_validate_book`, which is the key test: every converted fixture validates cleanly
- [ ] **Step 2: Run them and confirm they fail. Step 3: Implement. Step 4: Run the full suite, then commit** "Add one-time HTML summary converter".

### Task 5: Convert and import the 54 pages; review the report

This task is run by the controller or an implementer, not TDD. It produces data, not code, except for fixes to Task 4 found here, which go through Task 4's tests.

- [ ] **Step 1:** `venv/bin/python -m distill.scripts.convert_html_summaries "<vault>/03-resources/book-summaries" --out data/distill_import`. This takes a while because of the downloads, so run it in the background.
- [ ] **Step 2:** Read `data/distill_import/report.md`. For every flagged book, decide whether it's a converter bug (fix in Task 4 with a new fixture test, then rerun with `--only`) or acceptable (record why).
- [ ] **Step 3:** Resolve the duplicates. Import the more complete *Abundance* page (more chapters and words) and skip the other. Record this.
- [ ] **Step 4:** Import every converted folder: `for d in data/distill_import/*/; do venv/bin/python -m distill.scripts.push_book "$d"; done`. Expect about 53 imports with exit 0.
- [ ] **Step 5:** Sanity-check:
  - `ensure_reader_content` succeeds for every book (a one-liner loop)
  - the total `data/distill.db` size is printed and is under ~150 MB
- [ ] **Step 6:** Log the counts, the flagged list and the decisions in `WORK_LOG.md`. Commit the work log only (data stays untracked).
