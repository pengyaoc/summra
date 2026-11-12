# Book Ingestion Workflow (always dry-run first)

> Moved from `CLAUDE.md` on 2026-11-11 so agent instructions stay short. `CLAUDE.md` links here; this file is the source of truth.

When asked to ingest a new book file (typically a `data/books/pg<id>.txt` from Project Gutenberg), follow this 3-step workflow. Do NOT skip the dry-run.

**1. Dry-run and review.**
```sh
venv/bin/python -m plainly.scripts.content.generate_summaries data/books/<file> --dry-run
```
The `CHAPTER BREAKDOWN` block at the end prints each detected chapter with its title, char/word counts, and **start/end line numbers in the raw source file**. Read the source at those line numbers (or grep for `^CHAPTER\|^PART\|^BOOK\|^VOLUME` in the file) and verify:
  - Chapter count matches the source's actual chapter count.
  - Titles look right (real Hardy/Doyle/etc. titles, not garbage like `"V. \"Cithaeron\" (6): Oedipus..."`).
  - Coverage is ≥95% (printed at top of breakdown). If <95%, the parser likely lost content.
  - No chapter is monstrously large or tiny (e.g., Chapter 0 = entire book = "preface" is the canonical "swallowed the book" failure mode).
  - The `(anchor not found in raw file)` line-range note flags chapters whose first ~6 words don't appear in the raw source — usually means the title is from a TOC entry rather than real prose, or the chapter is the wrong content.

**2. Ingest only if dry-run looks correct.** If anything looks off, STOP. Either fix the parser for that case (rare, only for clearly script-side bugs like the `PART I.` → `'.'` capture or `M.D.` → `M.d.` normalization), or document the book as a known-bad case below.
```sh
venv/bin/python -m plainly.scripts.content.generate_summaries data/books/<file> --parse-only
```
Note the new `book_id` printed.

**3. Validate after ingest.**
```sh
venv/bin/python -m plainly.scripts.audits.validate_chapter_split --book-id <id> --llm-digest
```
The deterministic checks should be 0 FAIL and at most 1 WARN (the "off-by-one for preface" warning is expected for most books). Read the `--llm-digest` block and spot-check that titles + first/last 200 chars look right per chapter.

## Known-bad book classes — do NOT attempt to auto-ingest

The parser is tuned for **single-work prose novels with explicit CHAPTER markers** (and the two-level PART/CHAPTER variant). The following classes fail in known ways. Recognize them from the dry-run output and either skip, or ingest manually:

1. **Anthologies / multi-work books.** Example: `pg100.txt` (Complete Works of Shakespeare, 38 plays in one file). Symptom: ~25% coverage, a single "chapter" 1MB+, ACT markers detected from the *first* play only. **Fix:** these aren't a "book" in our model — skip, or split the source into per-work files manually.

2. **Aphoristic / non-chaptered classics.** Example: `pg2680.txt` (Marcus Aurelius's *Meditations* — 12 numbered books of aphorisms, no explicit chapter markers in body, only translator's footnotes use `BOOK X` for cross-references). Symptom: parser matches lowercase prose like `"part concerned with outward things"` mid-sentence as a PART marker because `re.IGNORECASE` is on. Underlying bug: `section_pattern` lowercased matches absorb prose. **Fix candidate (deferred):** add a structural guard (require surrounding blank lines, reject if first word of next line is also lowercase). For now: skip.

3. **Books with no in-body chapter markers / non-English structure.** Example: `pg175.txt` (Leroux's *Phantom of the Opera* — English translation but uses unusual heading conventions). Symptom: 2 chapters detected, one is the entire book as "Preface" (76K words), the other is title `'.'` (1 chapter from a stray match). **Fix:** skip.

See `WORK_LOG.md` "Failed-to-parse list" for the canonical inventory of skipped books with rationale per file.

## Cases the parser handles well (no special handling needed)

- Novels with `CHAPTER I`, `CHAPTER II` etc. markers on their own line (`pg23`, `pg110`, `pg1695`, `pg2852`, etc.).
- Two-level books: `PART I` / `PART II` with `CHAPTER I..N` inside each (`pg244`, `pg2600`, `pg1399`).
- BOOK-as-chapter aphoristic works where each BOOK is one logical chapter (`pg3296` Augustine's *Confessions*).
- Books with `Chapter N` in title case rather than `CHAPTER N`.
- Empty PART subtitle (`PART I.` with no title text) — captured as empty string, not `'.'`.
- Dotted abbreviations in titles like `M.D.`, `Ph.D.`, `U.S.A.` — preserved through case normalization.

## Tests covering these cases
- `tests/test_book_chapter_name_detection.py` — title normalization (incl. dotted abbreviations)
- `tests/test_part_section_title.py` — bare `PART I.` regression
- `tests/test_derive_chapter_line_ranges.py` — line-range helper for dry-run output
- `tests/test_validate_chapter_split.py` — post-ingest deterministic validator
- `tests/test_two_level_toc.py` — multi-part book regression suite
