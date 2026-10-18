# Plain English by Claude Subagents (no Gemini)

How to write a book's `chapters.modern_english_text` with Claude subagents and make sure Side-by-Side pairs every paragraph. A **Sonnet** subagent writes each chapter; a **separate, fresh** subagent then verifies it against the original. First run: The Iliad (book 66), 2026-10-16, with Haiku writers. Haiku left too many meaning errors, so the writer is now Sonnet (see `docs/agent_plain_english_learnings.md`).

Lessons from each run, and why these rules exist, are in `docs/agent_plain_english_learnings.md`.

This is an alternative to Step 1 and Step 6 of `docs/plain_english_workflow.md` (the Gemini generator). The cleanup steps (2, 3, 5e) and the audit (Step 4) are the same.

## Why it works

- **Same writing rules as Gemini.** The export step builds each prompt with `ModernEnglishGenerator.build_single_chapter_prompt()` from `scripts/content/generate_modern_english.py`. There is one copy of the rules (8th-grade level, keep every sentence, keep names, exact paragraph count). Change them there and both paths change.
- **Numbered paragraphs, small chunks.** Each original paragraph is tagged `[P12]`, and chapters are cut into chunks of about 12K characters. The agent writes one JSON file per chunk: `{"start": 12, "paragraphs": [...]}`. Alignment is checked by position, so a merged or skipped paragraph cannot hide.
- **A mechanical gate before anything reaches the database.** `passage_rewrite.py check` checks, per chapter:
  - the paragraph count is exact;
  - each paragraph is one line and ends at a terminator, unless it is a verbatim heading;
  - each paragraph is 0.5–1.3× the original's length, and the chapter 0.50–1.10×;
  - there is no summary language ("this passage", "the narrator"…) unless the original uses the phrase;
  - there is no "…something. If he…" filler where a that-clause should be, unless the original says "something".

  A terminator may be followed by closing quotes, `)`, `]`, `_` or `}` (a braced citation such as `{See Pfeffel.}`). The gate also prints **WARN** lines, which do not fail the chapter: the original has "therefore", "perhaps" or "not only" and the plain English has no equivalent. Dropped connectives were the most common meaning error on The Wealth of Nations, so the verifier checks every WARN line.
- **Sonnet reads for meaning.** The gate cannot tell a faithful paragraph from a fluent wrong one. A Sonnet subagent per chapter compares every pair and fixes the JSON.

## Steps

Set `BOOK=<id>` and `DIR=data/log/agent_plain_english/book$BOOK` (gitignored). Back up the DB first: `cp data/database.db data/database.pre-<book>-plain-$(date +%Y%m%d).db`.

### 1. Clean the original (mechanical, dry-run each first)

The reader pairs paragraph *i* of the original with paragraph *i* of Plain English, so non-text paragraphs must leave the original first.

```sh
PYTHONPATH=backend:. venv/bin/python scripts/audits/reformat_paragraphs.py --book-id $BOOK --dry-run      # single \n → \n\n
PYTHONPATH=backend:. venv/bin/python scripts/audits/strip_footnotes.py --book-id $BOOK --dry-run          # [12] markers + trailing "Footnotes" block
PYTHONPATH=backend:. venv/bin/python scripts/audits/strip_illustration_captions.py --book-id $BOOK --dry-run [--tags-only]
PYTHONPATH=backend:. venv/bin/python scripts/audits/strip_decorative_dividers.py --book-id $BOOK --dry-run
```

Order matters: reformat first (the other scripts work on `\n\n` paragraphs), and strip footnotes before captions (`ARGUMENT.[40]` loses its marker and is then a normal heading).

Before applying the caption script, read what it would remove. Its default rules also take any short line without end punctuation, which deletes real headings in some books. Use `--tags-only` to remove only `[Illustration…]` paragraphs.

Check the structure too. Grep each chapter for `BOOK`, `PART`, `VOLUME` and `INTRODUCTION` paragraphs that are not at its start. Ingest sometimes leaves the next Book's heading or introduction at the end of the previous chapter (Wealth of Nations). Books that encode the level in the chapter number (101, 201…) should move to `book_sections` with chapters numbered 1..N. Fix this before writing: moving paragraphs later means moving them in both columns.

Then check paragraph sizes. A paragraph over ~6K characters is fine but worth a note in that agent's brief.

### 2. Export the prompts

```sh
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py export --book-id $BOOK --dir $DIR
```

Writes `$DIR/in/RULES.md` once per book: the Gemini generator's rules plus the agent output rules. It also writes `$DIR/in/ch<N>/<start>.md`, one short file per chunk: the chapter title, the numbered paragraphs, and the absolute path of the JSON to write in `$DIR/out/ch<N>/`. Agents read RULES.md once, not once per chunk. Before this split, the repeated rules were 39% of all prompt text on Wealth of Nations.

### 3. Sonnet writers (background)

Use the `plain-english-writer` agent type (`.claude/agents/plain-english-writer.md`). It runs on Sonnet with Read, Write and Bash only, and the brief is built in. A launch prompt is just the assignment:

> Run dir `data/log/agent_plain_english/book<id>`, book id <id>, chapter <N> ("<title>"). You own the WHOLE chapter (or: only these files). Chunk files: `in/ch<N>/001.md, 013.md, …`. Book notes: <one or two lines, e.g. "keep the salt tables verbatim">.

**Batch for tokens.** Every agent pays a fixed startup cost: on Wealth of Nations, a writer with a single 9K-character chunk still used about 82K tokens. So:
- Give each writer about 60–80K characters of text (5–7 chunks).
- Put several short chapters in one writer's assignment.
- Split a long chapter only where it exceeds that.

Do not use Haiku: its Iliad drafts passed the gate but needed 317 meaning fixes.

**Plan the sittings.** Every agent counts against the session usage limit, and running more agents at once does not change the total. A limit hit stops every running agent at once. `SendMessage` resumes each one after the reset with its work intact ("the usage limit has reset; re-read your JSON files and continue"). A book over ~1M characters will hit the limit at least once, so agree the plan with the user first. Keep about 10 agents running at a time.

**Keep the coordinator cheap.** On Wealth of Nations the coordinator (Opus, one long session) likely cost as much as all the writers. Every report re-read a growing history. Run each sitting in a fresh session on Sonnet, and keep scratch files for doubts and fix tallies so a new session can pick up from them.

**Effort.** The writer runs at `effort: low` and the verifier at `effort: medium`, both set in the agent files. This is new as of 2026-10-18 and untested. On the next book, compare verifier fixes per paragraph with Wealth of Nations' 5%. If the rate rises noticeably, remove `effort: low` from the writer.

The agents report in at most 6–8 lines, which keeps the coordinator's context small over ~100 launches. Keep their doubt lists in a scratch file, so you can paste them into the verifier assignments without re-reading the reports.

Agents that own only part of a chapter skip the gate, because it fails until the chapter is complete. Run it yourself once all parts land.

### 4. Gate the whole book

```sh
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py check --book-id $BOOK --dir $DIR
```

Spot-check 3–4 pairs from the first chapter that finishes before launching the rest. If the brief has a problem, it is cheaper to find it after one chapter than after 25.

### 5. Fresh-agent verification (one per chapter, background)

```sh
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py review --book-id $BOOK --dir $DIR
```

This writes `$DIR/review/ch<N>.md`: each original paragraph next to its Plain English, with the length ratio. Regenerate it after any writer finishes late. Then launch **new** `plain-english-verifier` agents (`.claude/agents/plain-english-verifier.md`). Never ask the writer to check its own work; a fresh context reads the original without the writer's assumptions.

Size verifier assignments like writers: about 60–80K characters of original text each. Use disjoint paragraph ranges and file lists within a chapter, and several short chapters per verifier.

The assignment names the run dir, book id, chapter, paragraph range and the writer's doubts. Always paste the writer's own "unsure" list: writers admit where they compressed ("condensed the phrasing", "shortened a little"), and those are exactly the places to check.

**This step is not optional.** The gate checks shape; it cannot see meaning. On the Iliad, every chapter passed the gate, and Sonnet still fixed 317 paragraphs: 5–22 per Book, 7 in the prose Introduction (see `docs/agent_plain_english_learnings.md`).

### 6. Apply and audit

```sh
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py apply --book-id $BOOK --dir $DIR --dry-run
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py apply --book-id $BOOK --dir $DIR
```

Then run the CLAUDE.md Step 4 audit snippet. Every chapter must be EXACT with a ratio of 50–110%.

Before applying, make apostrophes consistent with the source. Agents mix `Nestor's` and `Nestor’s`; a one-off regex over the JSON files, `(?<=\w)'(?=\w|\s|[.,;:!?”’]|$)` → `’`, fixes word apostrophes and leaves quotation marks alone. Re-run the gate afterwards.

### 7. Verify Side-by-Side

Flask must be running (`python backend/app.py`, :5001). The reader recompiles its index on the first request after the text changes (`ensure_reader_content`).

- Add the book to `BOOKS` in `tests/e2e/agent_plain_english_side_by_side.mjs`: its id, slug, the chapter to open, and regexes for the first and last rows. Run it before applying, to see it fail, and again after. It walks every side-by-side segment through the API: every row has both sides, and no footnote markers or image tags remain. It then opens `/books/<slug>/read?mode=side_by_side&chapter=<id>` and checks the page for the chapter heading, paired rows, no gaps, no overflow and no console errors. `BOOKS=<slug>` runs a single book.
- Run `PATHS=/books/<slug>,/books/<slug>/read node smoke.mjs`, plus `sxs_row_split.mjs` and `reader_opens_at_chapter.mjs`.
- Look at a screenshot.

`reader_chapter_starts_page.mjs` covers the reader around chapter starts. Every chapter starts a new page with its heading first, in every mode including Side by Side. Opening a chapter, or switching mode there, keeps you in that chapter.
