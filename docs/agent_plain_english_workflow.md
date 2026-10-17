# Plain English by Claude Subagents (no Gemini)

How to write a book's `chapters.modern_english_text` with Claude subagents and make sure Side-by-Side pairs every paragraph. A **Sonnet** subagent writes each chapter; a **separate, fresh** subagent then verifies it against the original. First run: The Iliad (book 66), 2026-10-16, with Haiku writers. Haiku left too many meaning errors, so the writer is now Sonnet (see the Iliad notes).

This is an alternative to Step 1 and Step 6 of `docs/plain_english_workflow.md` (the Gemini generator). The cleanup steps (2, 3, 5e) and the audit (Step 4) are the same.

## Why it works

- **Same writing rules as Gemini.** The export step builds each prompt with `ModernEnglishGenerator.build_single_chapter_prompt()` from `scripts/content/generate_modern_english.py`. There is one copy of the rules (8th-grade level, keep every sentence, keep names, exact paragraph count). Change them there and both paths change.
- **Numbered paragraphs, small chunks.** Each original paragraph is tagged `[P12]`, and chapters are cut into chunks of about 12K characters. The agent writes one JSON file per chunk: `{"start": 12, "paragraphs": [...]}`. Alignment is checked by position, so a merged or skipped paragraph cannot hide.
- **A mechanical gate before anything reaches the database.** `passage_rewrite.py check` checks, per chapter:
  - the paragraph count is exact;
  - each paragraph is one line and ends at a terminator, unless it is a verbatim heading;
  - each paragraph is 0.5–1.3× the original's length, and the chapter 0.50–1.10×;
  - there is no summary language ("this passage", "the narrator"…) unless the original uses the phrase.
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

Then check paragraph sizes. A paragraph over ~6K characters is fine but worth a note in that agent's brief.

### 2. Export the prompts

```sh
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py export --book-id $BOOK --dir $DIR
```

Writes `$DIR/in/ch<N>/<start>.md`, one ready-to-run prompt per chunk. Each names the absolute path of the JSON it must produce in `$DIR/out/ch<N>/`.

### 3. Sonnet writers (one per chapter, background)

Use one Sonnet subagent per chapter (`model: "sonnet"`, `run_in_background: true`). Do not use Haiku: its Iliad drafts passed the gate but needed 317 meaning fixes. If a chapter has more than ~6 chunks, split it between two agents with disjoint file lists. Keep about 10 agents running at a time. Brief (fill in the chapter and files):

> You are writing the Plain English version of <book>, <chapter title> (chapter N), for a reading app. Working directory: the repo root. Do NOT edit any file except the JSON outputs named below. Do NOT touch the database, git, or any script. Your inputs are prompt files, one per chunk: `$DIR/in/chN/001.md, 021.md, …`. For EACH file, in order: (1) read the whole file: it holds the app's translation rules (the same rules the Gemini generator uses), the numbered paragraphs [P#], and an "AGENT OUTPUT FORMAT" section; (2) follow those rules exactly: one plain paragraph per numbered paragraph, same count and order, nothing merged, split, skipped or summarized, every sentence translated, names kept, headings verbatim, and if an original paragraph ends with a colon leading into a speech, end yours with a period; (3) write the JSON file named in that section with the Write tool (valid JSON; escape straight `"`; no line breaks inside a paragraph). Then run `PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py check --book-id $BOOK --dir $DIR --chapter N` and fix FAIL lines until it passes. Never game the gate by padding or cutting meaning. Report: the final gate line, and any paragraphs you were unsure about (one line each).

Add book-specific notes where they help, for example "one paragraph is very long; translate all of it" or "keep the date, signature and Greek lines verbatim".

Agents that hold only part of a chapter should skip the gate, because it fails until the chapter is complete. Run it yourself once both halves land.

### 4. Gate the whole book

```sh
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py check --book-id $BOOK --dir $DIR
```

Spot-check 3–4 pairs from the first chapter that finishes before launching the rest. If the brief has a problem, it is cheaper to find it after one chapter than after 25.

### 5. Fresh-agent verification (one per chapter, background)

```sh
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py review --book-id $BOOK --dir $DIR
```

This writes `$DIR/review/ch<N>.md`: each original paragraph next to its Plain English, with the length ratio. Regenerate it after any writer finishes late. Then launch one **new** Sonnet subagent per chapter (`model: "sonnet"`) with the brief below. Never ask the writer to check its own work; a fresh context reads the original without the writer's assumptions. A chapter over ~100K characters (the Iliad's Introduction and Preface) gets two reviewers with disjoint paragraph ranges and file lists.

**This step is not optional.** The gate checks shape; it cannot see meaning. On the Iliad, every chapter passed the gate, and Sonnet still fixed 317 paragraphs: 5–22 per Book, 7 in the prose Introduction (see the notes below).

### 6. Apply and audit

```sh
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py apply --book-id $BOOK --dir $DIR --dry-run
PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py apply --book-id $BOOK --dir $DIR
```

Then run the CLAUDE.md Step 4 audit snippet. Every chapter must be EXACT with a ratio of 50–110%.

Before applying, make apostrophes consistent with the source. Agents mix `Nestor's` and `Nestor’s`; a one-off regex over the JSON files, `(?<=\w)'(?=\w|\s|[.,;:!?”’]|$)` → `’`, fixes word apostrophes and leaves quotation marks alone. Re-run the gate afterwards.

### 7. Verify Side-by-Side

Flask must be running (`python backend/app.py`, :5001). The reader recompiles its index on the first request after the text changes (`ensure_reader_content`).

- Copy `tests/e2e/iliad_side_by_side.mjs` for the new book: change the book id and slug, and the expected first and last rows. It walks every side-by-side segment through the API and checks that each row has both sides. It then opens `/books/<slug>/read?mode=side_by_side&chapter=<id>` and checks the first page for paired rows, no gaps, no overflow and no console errors.
- Run `PATHS=/books/<slug>,/books/<slug>/read node smoke.mjs`, plus `sxs_row_split.mjs` and `reader_opens_at_chapter.mjs`.
- Look at a screenshot.

`reader_chapter_starts_page.mjs` covers the reader around chapter starts. Every chapter starts a new page with its heading first, in every mode including Side by Side. Opening a chapter, or switching mode there, keeps you in that chapter.

## Verifier brief

> You are the quality checker for the Plain English version of <book>, <chapter title> (chapter N), in a reading app. Another agent wrote it; your job is to find and fix real problems. Working directory: the repo root. You may edit ONLY the JSON files in `$DIR/out/chN/`. Do NOT touch the database, git, scripts, or any other chapter. If you write a helper script, give it a unique name such as `chN_fix.py`; other reviewers share the scratchpad.
>
> Input: `$DIR/review/chN.md` pairs every original paragraph with its Plain English (`### P<n> (ratio x)`, `ORIGINAL:`, `PLAIN:`). Paragraph i of the plain text appears beside original paragraph i in Side by Side. In the JSON files (`{"start": n, "paragraphs": [...]}`), P<n> is entry n−start of the file whose start ≤ n. The writing rules are in the header of `$DIR/in/chN/001.md`; read it once.
>
> Check EVERY pair for:
> 1. Alignment: the plain paragraph covers exactly its original paragraph.
> 2. Completeness: every event, speaker, name, simile and clause is present. Flag anything dropped or "compressed".
> 3. Accuracy: who does what to whom is right; pronouns point to the right person; no invented details; no reversed meanings. Read inverted and elliptical syntax carefully.
> 4. Rules: 8th-grade reading level, no leftover archaic words, no over-long sentences, headings verbatim.
>
> Fix real problems by editing the JSON. Keep the files valid JSON with ONE LINE PER PARAGRAPH entry, the same count, and each paragraph ending with . ! ? or a closing quote after one. Do NOT rewrite paragraphs that are fine; style preferences are not problems.
>
> The writer flagged: <paste the writer's "unsure" list>.
>
> When done, run the chapter gate; it must print PASS. Report concisely: pairs reviewed; number fixed; one line per fix ("P<n>: problem → change"); anything unresolved; the final gate line.

Always paste the writer's own "unsure" list into the brief. Writers admit where they compressed ("condensed the phrasing", "shortened a little"), and those are exactly the places to check.

## Iliad notes (book 66, 2026-10-16)

**Source.** Pope's translation (pg6130), `is_poetry=0`. Ingest had flattened each verse paragraph onto one line, so paragraphs were single-`\n` lines, which the reader already treats as paragraphs. We left the original as flattened couplets (prose workflow) rather than restoring verse lines.

**Cleanup.**
- `reformat_paragraphs.py` changed all 25 chapters to `\n\n` paragraphs.
- `strip_footnotes.py` removed about 300 inline `[n]` markers, plus 461 endnote paragraphs that had been appended to Book XXIV.
- `strip_illustration_captions.py --tags-only` removed 71 `[Illustration: ]` lines. The default rules would also have deleted the headings `ARGUMENT`, `END OF THE ILIAD`, `A. POPE` and `POPE’S PREFACE TO THE ILIAD OF HOMER`.

**Size.** 25 chapters (the Introduction and Pope's Preface, then Books I–XXIV), 1,524 paragraphs, 987K characters, cut into 98 chunks of about 12K characters. 26 Haiku writers and 26 Sonnet verifiers, with the Introduction split in two for both steps.

**Result.**
- All 25 chapters are EXACT, with ratios of 94–107%.
- Side by Side has 1,524 paired rows. `iliad_side_by_side.mjs` passes, and 40 consecutive pages show no clipping.

**What Sonnet QC caught (317 paragraphs fixed across the 25 chapters).**
- Haiku's errors on Pope's compressed, inverted verse are mostly about *who did what*:
  - swapped speakers or agents (Book IV: Atrides and Nestor reversed; Book XIII: Menelaus and Helenus swapped; Book XX: wrong spear-thrower);
  - reversed meanings (Book III: a curse inverted; the Preface: "I doubt not" became "I doubt that"; Book IX: Achilles made the giver instead of the receiver);
  - wrong genealogy (Book XIII: Medon; Book XIV: Diomed's ancestry);
  - invented details (a cliff, a chariot, "of gold");
  - spots where the writer admitted it compressed text.
- Plain prose chapters such as the Introduction needed far fewer fixes (7 in 123 paragraphs).

**Gate adjustments made during the run.**
- A paragraph kept verbatim (a heading such as `A. POPE`) may end without a terminator.
- A terminator inside italics (`_Numa Pompilius._`) counts.
- A summary phrase ("the poet") is allowed when the chapter's original uses it, as in the Preface, which is commentary.

**Operational lessons.**
- Running ~26 agents at once hit the account's usage limit partway through. The stopped agents kept their work and were resumed with `SendMessage` after the reset ("continue from where you stopped; re-read the JSON files first"). Expect this on a whole book, and keep about 10 agents running at a time.
- Several reviewers wrote helper scripts named `fix.py` in the shared scratchpad and overwrote each other's. Their exact-string asserts failed before any write, so no chapter was damaged, but the brief now requires unique script names. Afterwards, check that each reported fix landed in its own chapter (`grep -l "<new text>" $DIR/out/ch*/*.json`).
- One reviewer returned "pending" instead of a report. Ask it again before counting the chapter as done.
