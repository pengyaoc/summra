# Plain English (Modern Translation) Workflow

End-to-end process for generating, validating, and fixing `chapters.modern_english_text` — the "plain English" version of each chapter shown alongside the original in the side-by-side reading view.

This document is the long-form companion to the "Plain English Workflow" section in `CLAUDE.md`. CLAUDE.md is the cheat-sheet; this is the full story, including every corner case we hit during the first 20-book migration and how we solved it.

## The end goal

For every chapter where modern text exists:

- **`paragraph_diff == 0` (EXACT match).** Splitting `chapter_text` and `modern_english_text` on `\n\n` must yield the same paragraph count. The side-by-side reading view pairs them by index — any mismatch causes visible misalignment. Within ±2 is NOT good enough.
- **`char_ratio` in `[0.50, 1.10]`.** Modern is at least 50% of original length and not wildly longer. Anything <50% almost always indicates truncation or summary substitution by Gemini.
- **Modern ends at a sentence terminator** matching the original's narrative endpoint. Mid-word endings ("...risky har") are an instant-fail truncation signal.
- **Title alignment.** If the original's first paragraph is the chapter title, modern's first paragraph must be the same title (case-matched to the body — not to the `chapter_title` field which may differ).

## The 6-step process

```
1. Generate (Gemini)
2. Reformat hard-wrapped paragraphs (mechanical)
3. Strip decorative dividers      (mechanical)
4. Audit each chapter             (mechanical)
5. Fix misalignments              (mostly mechanical; Sonnet subagent if needed)
6. Regenerate damaged chapters    (Gemini, only for truncated/summary cases)
```

Steps 2, 3, 4 are idempotent and free. Step 5 is mechanical for the common patterns (title prepend, divider strip, end-marker append) and falls back to a Sonnet subagent for non-trivial cases. Step 6 is the only paid step beyond step 1; gate it carefully.

---

## Step 1 — Generate the plain-English version

```sh
PYTHONPATH=backend venv/bin/python scripts/content/generate_modern_english.py --book-id <id> --all-chapters --dry-run
PYTHONPATH=backend venv/bin/python scripts/content/generate_modern_english.py --book-id <id> --all-chapters
```

### Rules

- **Always dry-run first** to see batch count and per-batch char sizes. The smart batcher caps each batch at 60K input chars and 10 chapters per batch — large chapters land solo.
- **Always start with `gemini-3.1-flash-lite`** (the default). Cheapest, fastest, handles 90%+ of chapters cleanly. Don't escalate preemptively.
- **Escalate to `--model gemini-3.5-flash`** for individual chapters that come back truncated or summary-shaped (detected in step 4). Confirmed to recover full output where flash-lite gave up.
- **The prompt instructs Gemini to keep the chapter title as the first paragraph** (`scripts/content/generate_modern_english.py:109-110`). Older runs predating that prompt fix often dropped titles — step 5a fixes those mechanically.

### Cost discipline (`MEMORY.md → feedback_llm_cost.md`)

- Never run without explicit permission.
- Raw responses persist to `data/log/gemini_logs/`; per-chapter previews to `data/log/modern_english/`. If a parsing bug requires reprocessing, you can replay from these logs without paying again.

### Rate limits

- Free tier: ~5 RPM, 1M TPM, 1500 RPD for `gemini-3.1-flash-lite`.
- Each script run sleeps 3 seconds between batches.
- **Don't run more than 2 books in parallel.** We tried 10 — they all stalled on rate-limit backoff (10-minute exponential retries piled up) and produced zero progress for 30+ minutes before we killed them. 2 concurrent processes keep total RPM under the limit because batches take 30-180 seconds each.

### Batch size and truncation

Config constants in the script:
- `MAX_CHAPTERS_PER_BATCH = 10`
- `MAX_BATCH_CHARS = 60000` — chapters >60K solo
- `MAX_OUTPUT_TOKENS = 65535` — output cap

The output cap isn't usually the bottleneck. Truncation happens because flash-lite **chooses to abbreviate** on long inputs even when output cap allows more. Examples we hit:

- **Moby Dick ch.81** (24K orig) → modern was 30% length, ending mid-word "har"
- **Sherlock ch.1** (~50K orig) → modern was 36% length, ending "...with you." mid-conversation
- **Invisible Man ch.28** (16K orig + 6K epilogue) → modern dropped the entire 12-paragraph "THE EPILOGUE"
- **Odyssey ch.24** (79K orig, 252 paragraphs of stichomythia) → flash-lite AND 3.5-flash both produced ~45-paragraph summaries; this chapter remains the model's ceiling

---

## Step 2 — Reformat hard-wrapped paragraphs

```sh
PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id <id> --dry-run
PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id <id>
PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id <id> --column modern_english_text
```

### Why this matters

Many Project Gutenberg ingests stored `chapter_text` (and some `modern_english_text`) hard-wrapped: paragraphs separated by single `\n` instead of `\n\n`. The paragraph validator splits on `\n\n` and would misreport `Orig=1, Modern=N` for every such chapter — looks like 100% mismatch but is actually just a formatting artifact.

### What the script does

For each chapter:
1. Strips a leading `title\n` prefix if the chapter_text starts with the title followed by a newline.
2. Replaces any single `\n` (not adjacent to another `\n`) with `\n\n`.

Pure DB rewrite. No LLM calls. Idempotent.

### Corner cases handled

- **Title-case mismatch**: `chapter_title` field may be `"In Which Piglet Meets a Heffalump"` while `chapter_text` starts with `"IN WHICH PIGLET MEETS A HEFFALUMP\n..."`. The strip uses the title from `chapter_title` literally, so uppercase body titles aren't stripped. This is fine — step 5a handles title alignment separately.
- **Poetry books**: `is_poetry=1` books refuse to be reformatted (verse line breaks are not paragraph breaks). Paradise Lost is the canonical example.
- **Pre-existing `\n\n` runs**: left alone (the regex `(?<!\n)\n(?!\n)` only matches isolated newlines).

### Tests

`tests/test_reformat_paragraphs.py` — covers transform purity, title-prefix stripping with special regex chars, idempotency, `--column` flag.

---

## Step 3 — Strip decorative section dividers

```sh
PYTHONPATH=backend venv/bin/python scripts/audits/strip_decorative_dividers.py --book-id <id> --dry-run
PYTHONPATH=backend venv/bin/python scripts/audits/strip_decorative_dividers.py --book-id <id>
```

### Why this matters

Some books use rows of `* * * * *` (or dashes/dots) as scene-break markers. Gemini correctly ignores them as non-content, so modern winds up short — but the original side still counts them as paragraphs, causing systematic mismatches.

### Examples we hit

- **Alice ch.1**: 6 dividers (Carroll marks each "Alice shrinks/grows" scene change). Without strip, ch.1 was `orig=30, mod=24` (diff -6).
- **Dracula**: 23 of 28 chapters had `* * *` scene breaks. Without strip, every chapter mismatched.
- **Single asterisks**: a lone `*` is also treated as a divider (Alice ch.1 had one).

### What the script does

Removes any paragraph that is entirely whitespace + decorative chars (`* - . … • · ~ _ =`). Idempotent. Tests at `tests/test_strip_decorative_dividers.py`.

### Important — frontend rendering

`formatChapterText` and `formatSideBySideText` in `frontend/static/js/app.js` split on **single `\n`**, then filter blank lines. So if a `*` survives in the DB, it appears as a `<p>*</p>` in the rendered chapter. The DB-strip is the single source of truth — the frontend does NOT defensively filter dividers (we chose explicit data over hidden cleanup).

### Sibling cleanup — strip illustration captions

For illustrated editions (Little Women in particular), `chapter_text` is polluted with illustration captions interleaved as paragraphs (`"Tail-piece"`, `"The procession set out"`, `"List of Illustrations"`). Run this immediately after `strip_decorative_dividers`:

```sh
PYTHONPATH=backend venv/bin/python scripts/audits/strip_illustration_captions.py --book-id <id> --dry-run
PYTHONPATH=backend venv/bin/python scripts/audits/strip_illustration_captions.py --book-id <id>
```

The script strips (from `chapter_text` only):
- Short paragraphs (<100 chars) that don't end with terminal punctuation and don't start with an opening quote or lowercase letter
- Known front-matter labels (`Contents`, `Preface`, `Tail-piece`, `List of Illustrations`, `Part First`, `Part Second`)
- Trailing transcriber/publisher notes (`On page N`, `Transcriber's Note`, `Project Gutenberg`, `This is a list of`)

Idempotent. Safe to run on non-illustrated books (no-op on most). See lesson #13 for detection details and lesson #14 for the related publisher-boilerplate case where you may need to manually truncate `chapter_text` at the last narrative paragraph.

---

## Step 4 — Audit each chapter

For every chapter, verify ALL of these — any single failure is a real problem to investigate:

| Check | Expected | Failure means |
|---|---|---|
| `paragraph_diff == 0` | `len(chapter_text.split('\n\n')) == len(modern_english_text.split('\n\n'))` | Off-by-1 usually = missing title; larger = truncation/merge |
| `char_ratio in [0.50, 1.10]` | `len(modern) / len(original)` | Below 50% = truncation or summary substitution |
| Modern ends at terminator | Last non-whitespace char in `.!?")'”’` | Mid-word endings = truncated |
| Modern's ending matches narrative endpoint | Compare last ~200 chars | Different events = truncated |
| Title alignment | If orig's first paragraph IS the title, modern's must be too | Causes off-by-1 |

### Smart-quote pitfall

Earlier audits incorrectly flagged chapters ending in `”` (right smart quote) as "no terminator." **Smart quotes ARE valid terminators.** Include `”` and `’` in the terminator set. Confirmed false positives we wasted time on: Alice ch.6/9/10/11/12, Sherlock ch.2, Oliver Twist ch.13.

### Quick per-book audit snippet

```sh
PYTHONPATH=backend venv/bin/python3 -c "
import sqlite3
db = sqlite3.connect('data/database.db')
def c(t): return len(t.strip().split(chr(10)*2)) if t and t.strip() else 0
for n, ot, mt in db.execute('SELECT chapter_number, chapter_text, modern_english_text FROM chapters WHERE book_id=BOOK_ID ORDER BY chapter_number'):
    if mt is None: print(f'ch.{n}: NULL'); continue
    o, m = c(ot), c(mt); ratio = len(mt)/max(1,len(ot))*100
    end = mt.strip()[-1] if mt.strip() else ''
    flag = 'EXACT' if o == m else 'MISMATCH'
    print(f'ch.{n}: orig={o} mod={m} diff={o-m:+d} ratio={ratio:.0f}% ends={end!r} {flag}')
"
```

---

## Step 5 — Fix paragraph misalignment

Try mechanical fixes FIRST. Most off-by-N diffs match one of these patterns and don't need any LLM:

### 5a. Missing title in modern (most common — off-by-1)

The original's first paragraph IS the chapter title, but Gemini's translation dropped it. Prepend the title using the body's casing — NOT the `chapter_title` field's casing, which often differs (e.g., body has `"FRIDAY NIGHT."` while `chapter_title` is `"Friday Night"`).

```python
import sqlite3
db = sqlite3.connect("data/database.db")
for r in db.execute("SELECT chapter_number, chapter_title, chapter_text, modern_english_text FROM chapters WHERE book_id=BOOK_ID ORDER BY chapter_number"):
    n, title, ot, mt = r
    if mt is None: continue
    op = ot.split("\n\n")[0]
    mp = mt.split("\n\n")[0]
    # orig's first paragraph IS the title (short, matches title field case-insensitively)
    if title and title.lower().rstrip(".") in op.lower().rstrip(".") and len(op) < len(title) + 20:
        if title.lower().rstrip(".") not in mp.lower().rstrip("."):
            body_title = op.strip()
            new_mt = f"{body_title}\n\n{mt}"
            db.execute("UPDATE chapters SET modern_english_text=? WHERE book_id=BOOK_ID AND chapter_number=?", (new_mt, n))
            print(f"Fixed ch.{n}: prepended {body_title!r}")
db.commit()
```

**Corner case — false negative.** The heuristic `title.lower() not in mp.lower()` can return False when the title phrase appears mid-text. War of the Worlds ch.8 had title "Friday Night" and modern text contained the phrase "on Friday night" 246 chars in — the heuristic skipped the prepend. Fall back to a manual prepend for any chapter that still mismatches after the bulk run.

### 5b. Missing "THE END" or chapter-closing marker

Modern often drops trailing single-line markers like `THE END` or `THE EPILOGUE` because they look like boilerplate. Append them verbatim from the original.

Examples we hit: Wizard of Oz ch.0 (missing book title at end), Looking-Glass ch.12 (missing "THE END"), Hound ch.15 (missing "THE END").

```python
ot, mt = db.execute("SELECT chapter_text, modern_english_text FROM chapters WHERE book_id=B AND chapter_number=N").fetchone()
new = mt.rstrip() + "\n\nTHE END"
db.execute("UPDATE chapters SET modern_english_text=? WHERE book_id=B AND chapter_number=N", (new,))
```

### 5c. Missing frontmatter (bibliography, publisher info)

Some chapter-0 (preface) rows have publisher/translator/year info as separate paragraphs in the original that Gemini collapsed. Either append back to modern OR strip from original — both work.

Example: All Quiet on the Western Front ch.0 had orig=7 (title, author, translator, city, publisher, year, preface body) but mod=3 (title, author, preface body). We inserted the missing 4 bibliographic paragraphs into modern.

### 5d. Trailing publisher boilerplate

The reverse: some originals end with publisher advertisements after "THE END" that Gemini correctly omitted. Strip from original.

Example: Dracula ch.27 had orig=104, mod=80 — modern stopped at "THE END" (paragraph 80) but original continued for 24 paragraphs of Grosset & Dunlap catalog listings. We removed paragraphs 81-104 from original.

### 5d-warning. **NEVER append verbatim PROSE to fix mid-chapter truncation**

A subtle but critical anti-pattern. The legitimate verbatim-append cases above (5b end-markers, 5c bibliographic frontmatter, 5d publisher boilerplate, 5e footnotes, 5f volume markers) all share one property: **the appended text is structural/boilerplate, not narrative prose to be modernized.** It's correct to keep `THE END`, `END OF THE SECOND VOLUME`, `[1] Heber C. Kemball...`, `0185m` page markers, `[Picture: Asked him to take care of us]` captions, and bibliographic blocks verbatim — those are metadata that doesn't need translation.

**It is NEVER correct to paste raw 19th-century prose paragraphs verbatim from `chapter_text` to recover from a truncated translation.** The product invariant is that `modern_english_text` reads as modern English. Pasting source-language prose at the chapter end creates a Frankenstein chapter: 90% modernized + 10% raw Dickens / Dumas / Dostoevsky. Side-by-side readers will see the modern column suddenly switch register, and the duplicate-paragraph signature (see below) sometimes occurs when the appended verbatim overlaps content the truncated modern already partially covered.

**Confirmed casualty:** Monte Cristo ch.35 and ch.37 (2026-05-31 batch). A Sonnet subagent batch was told "if you can't fix mechanically, REPORT" but interpreted "5 missing paragraphs at the chapter end" as an invitation to append those paragraphs verbatim from `chapter_text`. Ch.35 ended with 3 paragraphs of raw 1844-Dumas prose; ch.37 with 5. Both had duplicate-paragraph contamination where the appended verbatim overlapped content the truncated modern had already started rendering. Rolled back via direct SQL `UPDATE` (dropped the contaminated tails) and queued for `gemini-3.5-flash` regen.

**Detection signature (run after any large-diff fix campaign):**

```python
import sqlite3
db = sqlite3.connect("data/database.db")
for bid in (...):
    for n, ot, mt in db.execute("SELECT chapter_number, chapter_text, modern_english_text FROM chapters WHERE book_id=? AND modern_english_text IS NOT NULL", (bid,)):
        op = ot.strip().split("\n\n")
        mp = mt.strip().split("\n\n")
        # Flag: last N paragraphs of modern identical to last N of original AND those paragraphs are prose (>40 chars, not all-caps marker, not [Picture/[1]/asterisk/page-number)
        for offset in (1, 2, 3, 4, 5):
            if len(op) < offset or len(mp) < offset: break
            o_tail = op[-offset].strip()
            m_tail = mp[-offset].strip()
            if not (len(o_tail) > 40 and o_tail == m_tail): break
            if o_tail.startswith(("[Picture", "*", "[*]")) or o_tail.upper() == o_tail: continue
            print(f"book {bid} ch.{n}: tail offset -{offset} verbatim — INSPECT")
```

A handful of false positives (Gemini correctly leaves short modern-English-already sentences unchanged — "Though Miss Matty was startled, she submitted to Fate and Love."). The real positives have a tell: **the modern's last few paragraphs are full of Victorian/19th-c register inconsistent with the rest of the chapter**, often with adjacent-paragraph duplicates.

**Correct response when modern is truncated at end:**

1. Confirm via step-4 audit signals: `char_ratio < 0.95` AND modern's last paragraph doesn't match the narrative endpoint of original's last paragraph.
2. **Do NOT append verbatim.** Roll back any prior verbatim-append by dropping the contaminated tail from `modern_english_text`.
3. Regenerate the full chapter via step 6 (`--chapters N --model gemini-3.5-flash`). If 3.5-flash also truncates, accept the partial translation and document the chapter as a known stuck case — better a complete-but-summary modern than a half-modernized half-Dickens hybrid.

**Subagent prompt addendum (bake into all step-5g dispatches):** "If you find that the modern text is truncated mid-chapter (last paragraph doesn't reach the original's narrative endpoint), REPORT and EXIT. Do NOT paste verbatim original-language prose to fill the gap — that creates a half-translated hybrid that breaks the product invariant. Truncated chapters must be regenerated via step 6, not patched."

### 5e. Footnote paragraphs

Some originals contain translator/editor footnotes (e.g. `[1] Heber C. Kemball, in one of his sermons...`) that aren't narrative content. Modern translation correctly omits them. Strip from original.

Example: Study in Scarlet ch.10 had a single editor footnote between O18 and O20. Removing it dropped orig from 39 to 38, matching modern.

### 5f. Poem stanza splits

Gemini sometimes formats each verse line as its own paragraph when the original keeps stanzas as paragraphs. Use the `--merge` flag in `split_modern_paragraphs.py` to join consecutive lines back into stanzas.

Examples:
- **Jungle Book ch.8 (Lukannon)**: 6 stanzas each split into 4 lines (modern had 25 paragraphs, original 7). Merged each group of 4 lines.
- **Dorian Gray ch.14**: 12 verse lines of French poetry split into individual paragraphs; original had 3 stanza-paragraphs.
- **All Quiet ch.3**: a rhyming couplet split into 2 paragraphs by modern; original had them as one.

### 5g. Internal Gemini merge/split (when 5a-5f don't apply)

**Decision rule: `abs(diff) ≤ 5` → ALWAYS dispatch a Sonnet subagent. `abs(diff) > 5` → regenerate via step 6 first.** See lesson #11 for the rationale and validation data. Subagents are cheaper, deterministic, and never produce damage when properly gated.

Dispatch a **Sonnet** subagent (NOT Haiku — see below) per chapter:

```sh
PYTHONPATH=backend venv/bin/python scripts/audits/split_modern_paragraphs.py --book-id <id> --chapter-number <n> --inspect --snippet 200
PYTHONPATH=backend venv/bin/python scripts/audits/split_modern_paragraphs.py --book-id <id> --chapter-number <n> --split "5:200,7:100" --dry-run
PYTHONPATH=backend venv/bin/python scripts/audits/split_modern_paragraphs.py --book-id <id> --chapter-number <n> --split "5:200,7:100"
```

Subagent prompt must include:
- ONLY modify that single chapter (`book_id` + `chapter_number`).
- ALWAYS dry-run via `--split "..." --dry-run` before applying.
- NEVER split mid-sentence — only at sentence-terminator boundaries (`.!?")'”’`).
- Target paragraph counts must match EXACTLY (`orig - mod == 0`). Don't stop at ±1.
- If split points don't visually align with original paragraph boundaries, REPORT and exit. Don't guess.
- Mention the alternative: if the original has a paragraph the modern dropped (poetry, footnote, end-of-volume marker, transcriber note), append/insert it verbatim from `chapter_text` via direct SQL rather than splitting mod text.
- **CRITICAL — never paste verbatim PROSE to fix mid-chapter truncation** (see §5d-warning). Verbatim-append is only for structural/boilerplate paragraphs (markers, footnotes, picture captions, page numbers, bibliographic blocks). If modern is truncated and missing narrative-prose paragraphs at the end, REPORT and EXIT — the chapter must be regenerated via step 6, not patched.

### Why Sonnet, not Haiku

Earlier in this work we used Haiku subagents for alignment. **They dutifully inserted `\n\n` mid-sentence to hit a paragraph count when the modern text was truncated, producing chapters with sentence-cut damage.** Confirmed casualties that had to be regenerated:

- Moby Dick ch.81 (split "Rather\n\n than lose the whale")
- Odyssey ch.2/14
- Oliver Twist ch.3/12

Sonnet is the required model for any alignment work that involves judgment.

### Gate step 5g on completeness

Before dispatching ANY alignment subagent, the chapter must pass:

- **char_ratio ≥ 0.50** — modern is at least half the original's length.
- **Modern ends at a sentence terminator** — last char in `.!?")'”’`.

If either fails, the modern text is INCOMPLETE. Splitting it produces garbage. Regenerate via step 6 first.

---

## Step 6 — Regenerate damaged chapters (Gemini)

When step 4 audit flags a chapter as truncated, summary-shaped, or has a massive irreducible diff that can't be fixed mechanically, regenerate with Gemini.

```sh
# First retry: re-run with default flash-lite (it's non-deterministic at temperature 0.3)
PYTHONPATH=backend venv/bin/python scripts/content/generate_modern_english.py --book-id <id> --chapters "N,M" --dry-run
PYTHONPATH=backend venv/bin/python scripts/content/generate_modern_english.py --book-id <id> --chapters "N,M"

# If still truncated/summarized, escalate just that chapter
PYTHONPATH=backend venv/bin/python scripts/content/generate_modern_english.py --book-id <id> --chapters "N" --model gemini-3.5-flash
```

### Failure modes and remediation

| Pattern | Signal | Fix |
|---|---|---|
| **Truncated** | char_ratio <50% AND ends mid-word | Re-run flash-lite (may succeed). If repeats, escalate one chapter to 3.5-flash. |
| **Summary-shaped** | char_ratio <30%, content is condensed not translated. Sometimes prefaced with "I have provided a modern English summary..." | Same — retry, then escalate. |
| **Massive paragraph mismatch (diff >50, valid content)** | orig 252 → mod 45 with full coverage | Manual subagent alignment infeasible without splitting mid-sentence. Try 3.5-flash (better at preserving structure). If it still summarizes, flag for manual review. Odyssey ch.24 is at the model's ceiling — accepted as known-unfixable. |
| **NULL modern** | Gemini's parser failed to extract a chapter from the bulk response | Re-run — usually succeeds on retry |
| **Verse books** | `is_poetry=1`, orig=1 single big block | Skip the paragraph-count check; comparison is meaningless for verse |

After regenerating any chapter, return to step 2 (reformat) → step 3 (strip) → step 4 (audit) → step 5 (fix what's left).

---

## Supporting scripts

| Script | Purpose | Tests |
|---|---|---|
| `scripts/content/generate_modern_english.py` | Calls Gemini; writes to `chapters.modern_english_text` and logs | (integration) |
| `scripts/audits/reformat_paragraphs.py` | Hard-wrap → `\n\n`, strip title prefix. Works on either column. | `tests/test_reformat_paragraphs.py` |
| `scripts/audits/strip_decorative_dividers.py` | Removes `* * *`, `---`, etc. divider paragraphs from both columns | `tests/test_strip_decorative_dividers.py` |
| `scripts/audits/strip_illustration_captions.py` | Removes illustration captions (short, no terminal punct, no opening quote), front-matter labels (`Tail-piece`, `Contents`, etc.), and trailing transcriber/publisher noise from `chapter_text`. Run BEFORE first-pass generation on illustrated editions. | (none yet — add when used in anger) |
| `scripts/audits/split_modern_paragraphs.py` | Manual `--split` / `--merge` tool for surgical alignment via Sonnet subagent | `tests/test_split_modern_paragraphs.py` |

All scripts:
- Take `--book-id`, support `--dry-run`.
- Are idempotent (running twice is a no-op).
- Make zero LLM calls.
- Refuse to operate on `is_poetry=1` books where applicable.

---

## Per-book parallelism

Rate-limit math: 5 RPM ÷ 1 batch per ~60-180s = roughly 2 concurrent books is the safe ceiling for `gemini-3.1-flash-lite` on free tier.

What we tried that didn't work: 10 books in parallel → all hit 429s, the SDK backed off with exponential retries up to 10 min, processes appeared alive but did nothing for 30+ minutes. Had to kill all 10 and restart serially.

What works: launch 2 at a time. As each finishes, validate via steps 2-5 (which run fast, no LLM cost) and queue the next book. While Sonnet is doing alignment on a finished book, a new book can be regen'ing.

---

## The 20-book migration journey (May 2026)

### Match rate progression

| Stage | EXACT count | Pct |
|---|---|---|
| Session start (pre-fix) | 225 / 523 | 43% |
| After reformat sweep | 484 / 523 | 92.5% |
| After Gemini regen of 12 summary-shaped chapters | 493 / 523 | 94.3% |
| After Haiku manual alignment of 7 small-diff chapters | 500 / 523 | 95.6% |
| After Gemini 3.5-flash escalation for 6 truncated chapters | 505 / 523 | 96.6% |
| After Haiku alignment of 8 more — DAMAGE FOUND, switched to Sonnet | 505 / 523 | 96.6% |
| After Sonnet alignment of remaining mismatches | 507 / 523 | 97.0% |
| After regen + cleanup of Dracula publisher boilerplate | 510 / 523 | 97.5% |
| First 10 new books regenerated (147 chapters) | 657 / 670 | 98.1% |
| Second 10 new books regenerated (146 chapters) | **816 / 816** | **100%** |
| **Top-10 next batch (May 31, 11 new books, 408 chapters)** | **1224 / 1224** | **100%** |

### Books with notable corner cases

| Book | Issue | Fix |
|---|---|---|
| Alice ch.1 | 6 `* * *` scene dividers + a single `*` | Strip dividers |
| Alice ch.9/12 | Modern dropped title paragraph (title was first paragraph of original) | Title prepend |
| Dracula ch.1-23 | 23 chapters had `* * *` scene breaks | Strip dividers |
| Dracula ch.27 | 24 paragraphs of Grosset & Dunlap publisher ads after "THE END" | Strip from original |
| Wizard of Oz ch.0 | Missing "The Wonderful Wizard of Oz" title at end | Append marker |
| Moby Dick ch.81 | Truncated mid-word "har"; Haiku then split mid-sentence to fake paragraph count | Regen with flash-lite; switched to Sonnet for alignment |
| Moby Dick ch.1, Great Expectations ch.1 | Heavily condensed (18-27% length) | Regen; 3.5-flash recovered them |
| Odyssey ch.2/14, Oliver Twist ch.3/12 | Truncated long before Haiku touched them | Regen |
| Odyssey ch.24 | 79K-char chapter with 252 dialogue paragraphs; even 3.5-flash summarizes | Accepted at model's ceiling |
| War of the Worlds (all 20+ chapters) | All chapters' modern text dropped uppercase title paragraph | Bulk title prepend |
| Study in Scarlet (all 14 chapters) | Same — all titles dropped | Bulk title prepend |
| Study in Scarlet ch.10 | Editor footnote (`[1] Heber C. Kemball...`) in original Gemini correctly skipped | Strip from original |
| All Quiet ch.0 | Original had bibliographic frontmatter (translator, city, publisher, year) Gemini collapsed | Append to modern |
| All Quiet ch.3 | Rhyming couplet split into 2 paragraphs by modern | Sonnet merge |
| Jungle Book ch.8 (Lukannon) | Poem — 6 stanzas exploded into 25 single-line paragraphs | Sonnet merges (18 of them) |
| Jungle Book ch.7 (White Seal) | Seal Lullaby poem stanzas exploded | Sonnet merges |
| Little Women ch.1 (305 paras), ch.47 (256 paras) | Illustration captions interleaved as paragraphs in `chapter_text` (e.g. "Tail-piece", "The procession set out"); Gemini correctly omitted them | New `strip_illustration_captions.py` script, then regen |
| Little Women ch.47 | 165 paragraphs of publisher catalog ads (Alcott book list with prices) after final story line | Truncate `chapter_text` at the last narrative paragraph |
| Huckleberry Finn chs 35-38 | Gemini injected literal `### CHAPTER 1`-`### CHAPTER 4` markdown headers as paragraph 0 | Mechanical strip of the bogus header paragraph |
| Huckleberry Finn ch.43 | Gemini prepended a `CHAPTER 43: <title>` paragraph not in original | Mechanical strip |
| Scarlet Letter ch.24 | Original ended with 5 paragraphs of transcriber typo-correction notes (`page 072 — spelling normalized...`) Gemini dropped | Append verbatim from original to modern |
| Scarlet Letter ch.0 (Custom-House) | 89K-char preface; gemini-3.5-flash *truncated* on the long input, summarizing down to ~30K chars. Default flash-lite handled it correctly. | Counter-intuitive: don't escalate long chapters; flash-lite handled it on first try |
| Anne ch.19, Anne ch.33, Little Women ch.47 | Inline poetry quote that Gemini collapsed into surrounding narration without paragraph breaks | Sonnet split at sentence-terminator boundaries adjacent to the quote |
| Anne ch.36 | Gemini injected `### CHAPTER 1` markdown header (same pattern as Huck chs 35-38) | Merge into next paragraph |
| Sense & Sensibility ch.22, ch.36 | Original ends with `END OF THE FIRST VOLUME` / `END OF THE SECOND VOLUME` marker as its own paragraph; Gemini dropped it | Append verbatim from original |
| A Little Princess ch.19 | Original's last paragraph was the Project Gutenberg end note (`"End of Project Gutenberg's A Little Princess..."`) Gemini omitted | Append verbatim |
| Uncle Tom's Cabin (14 chapters) | Bible/literary citation footnotes as standalone paragraphs (`[1] Ps. 74:20.`, `[2] hymn attribution`) Gemini dropped | Insert verbatim from original at correct position |
| Tess ch.44 | Original ended with 3 division markers (`End of Phase the Fifth`, `Phase the Sixth:`, `The Convert`) Gemini dropped | Append verbatim from original |
| Tess ch.43 | Gemini merged two short adjacent narration paragraphs into one | Sonnet split at sentence terminator |

---

## Lessons learned

### 1. Don't trust Gemini's response shape blindly

Gemini will silently substitute a summary for a translation when the input is long, AND keep the same `### CHAPTER N` / `### END CHAPTER N` envelope so the parser accepts it. We caught this in a Dec 2025 gemini log:

> "I can certainly help you understand these chapters from *Moby Dick*. **Instead of a line-by-line translation, I have provided a modern English summary of each section** to help clarify the story and its themes."

The parser dutifully wrote 5 summary-paragraphs to `modern_english_text` for 5 Moby Dick chapters. char_ratio caught it later (4-10% per chapter). **Always run step 4 audit, never trust step 1 completion alone.**

### 2. Gate alignment subagents on completeness

A subagent told to "make paragraph counts match" will faithfully insert `\n\n` mid-sentence to hit a target — even mid-word in the worst case. This produces chapters that pass the count check but are content-broken (Moby Dick ch.81 "Rather\n\n than lose the whale...").

**Before dispatching any alignment subagent, verify**:
- char_ratio ≥ 0.50
- modern ends at sentence terminator

If either fails, regenerate, don't align.

### 3. Sonnet for judgment, Haiku not allowed for alignment

Haiku tends to take "match the count" too literally and split where it shouldn't. Sonnet recognizes when no valid split exists and reports back instead of forcing it.

### 4. Use the body's casing for title-prepend, not the title field

`chapters.chapter_title` is often title-case (`"In Which Piglet Meets a Heffalump"`) while the body has uppercase (`"IN WHICH PIGLET MEETS A HEFFALUMP"`). When prepending the title to modern, **use what appears in the body** to preserve the book's typography. Strip via `chapter_text.split('\n\n')[0].strip()`.

### 5. The title-match heuristic has false positives

Checking `title.lower() in modern_first_paragraph.lower()` can match a passing reference to the title's words. War of the Worlds ch.8 title "Friday Night" appeared mid-paragraph as "...on Friday night..." and the heuristic skipped the prepend. **For chapters that remain off-by-1 after bulk-prepend, manually verify and force-prepend.**

### 6. Frontend renders both columns by splitting on single `\n`

`formatChapterText` in `frontend/static/js/app.js` splits on `\n`, not `\n\n`, then filters blank lines. So `\n\n`-separated paragraphs render fine (empty strings get filtered). But any decorative `*` that survives in the DB renders as a literal `<p>*</p>`. The DB-strip is the only line of defense.

### 7. Smart quotes are valid sentence terminators

Audit scripts that check `last_char in '.!?")'` miss valid terminators `”` and `’`. Add both. Failure to do so caused us to incorrectly flag and regenerate clean chapters multiple times.

### 8. Rate-limit math: 2 books in parallel, max

Don't trust "they all started fine" — Gemini's SDK backs off silently for 10+ minutes on 429s. 10 concurrent books → 30+ min of zero progress before timeouts started killing processes. 2 concurrent is a safer ceiling because each batch takes longer than 12 seconds (5 RPM = 12s/req).

### 9. Publisher boilerplate and editor footnotes belong in the original-side cleanup

When modern correctly omits non-narrative content (publisher ads after "THE END", editor footnotes), **the right fix is to remove them from `chapter_text`**, not add them to `modern_english_text`. Modern should be plain English of the actual story, not a translation of publisher catalogs.

### 10. Verse books need a separate strategy

Paradise Lost (`is_poetry=1`) uses single `\n` as a verse-line break. The paragraph-count comparison is meaningless. Scripts that touch paragraphs refuse to operate on these. Currently no plain-English version exists for verse books; would need a verse-aware prompt + validation flow.

### 11. The ±5 rule — Sonnet for small deltas, Gemini for big ones

Decision boundary: `abs(diff) ≤ 5` → ALWAYS dispatch a Sonnet subagent. `abs(diff) > 5` OR `char_ratio < 0.50` → regenerate via Gemini.

Rationale validated on this batch: across the Top-10 next-batch session, Sonnet subagents fixed 18 distinct chapters with diffs ranging ±1 to +4 at 100% success rate (Uncle Tom's Cabin 14, Anne 2, A Little Princess 1, S&S 2, Little Women 1). Every Sonnet attempt either nailed exact match or correctly reported the problem was structural (poetry collapse without sentence-terminator anchors) — never produced damage. Gemini regen costs 1 paid call (often more if it retries on the same mismatch); Sonnet costs a few cents and is deterministic. **The previous "don't stop at ±2" guidance from step 5g is superseded by ±5.**

For abs(diff) > 5: those are almost always summary-shaped chapters or truncated chapters where mechanical splitting can't work because the source material is missing. Regenerate first, audit, then if still off-by-small dispatch Sonnet.

### 12. `gemini-3.5-flash` has a hard 20-requests-per-day quota on the free tier

Once exhausted, you get `429 RESOURCE_EXHAUSTED` for the rest of the day on that model only. Default `gemini-3.1-flash-lite` has a separate, much higher quota. Plan escalations carefully: don't burn 3.5-flash on 14 chapters of Uncle Tom's Cabin in one shot when you might need it tomorrow for an actually-truncated chapter. **Triage first**: only escalate chapters where you've confirmed flash-lite's output is summary-shaped or mid-word-truncated, not just off-by-1.

### 13. Illustration captions are pollution in `chapter_text`, not narrative

Books like Little Women (illustrated edition) interleave illustration captions as paragraphs between narrative paragraphs (e.g. `"Tail-piece"`, `"The procession set out"`, `"List of Illustrations"`). Gemini correctly omits these from translation, but they inflate the original's paragraph count, breaking alignment.

**Detection pattern**: short paragraph (<100 chars), doesn't end with terminal punctuation (`.!?")`), doesn't start with an opening quote (real dialogue), doesn't start with lowercase. Plus known front-matter labels (`Contents`, `Preface`, `Tail-piece`, `List of Illustrations`, `Part First`, `Part Second`).

Use `scripts/audits/strip_illustration_captions.py --book-id N --dry-run` BEFORE first-pass `generate_modern_english.py`. Idempotent. Safer to run on every illustrated edition.

### 14. Trailing publisher boilerplate can be hundreds of paragraphs

Little Women ch.47 had 165 paragraphs of Louisa May Alcott book catalog ads after the story's final line ("...never can wish you a greater happiness than this!"). Modern correctly stopped at the story's end; original kept going. The +166 diff is misleading — it's not a translation problem, it's a `chapter_text` pollution problem.

**Detection**: original is many times longer than modern + last narrative paragraph identifiable + back-matter has telltale markers (`THE LITTLE WOMEN SERIES.`, equals-sign-wrapped book titles, prices like `$1.50`). Truncate `chapter_text` at the last narrative paragraph before regenerating modern.

### 15. Counter-intuitive: long chapters fare BETTER on flash-lite than 3.5-flash

Scarlet Letter ch.0 ("The Custom-House", 89K chars) was *truncated* by `gemini-3.5-flash` (output capped at ~30K) but handled fully by default `gemini-3.1-flash-lite` (full 15K-word translation, exact 101→101 paragraph match). Don't default to escalating long chapters — try flash-lite first; 3.5-flash has a tighter output ceiling.

### 16. Gemini sometimes injects `### CHAPTER N` markdown headers as paragraph 0

When a single batch contains multiple chapters, Gemini occasionally prepends a literal `### CHAPTER 1`-style header to the first chapter's translation. This is *not* a chapter title, just markdown chrome. Strip mechanically — drop paragraph 0 if it matches `^### CHAPTER \d+` or `^CHAPTER \d+:`.

Pattern observed in: Huck Finn chs 35-38 + ch.43, Anne ch.36.

### 17. `END OF THE FIRST VOLUME` / `END OF THE SECOND VOLUME` / `Phase the Sixth:` markers

Multi-volume Victorian novels (Sense & Sensibility, Vanity Fair, Tess of the D'Urbervilles, etc.) often have structural markers as standalone paragraphs at the end of certain chapters: volume divisions (`END OF THE FIRST VOLUME`), phase divisions in Tess (`End of Phase the Fifth`, `Phase the Sixth:`, `The Convert`), or part divisions. Gemini drops them — they look like trash to the translator. Append verbatim from `chapter_text` — they're load-bearing for paragraph alignment but not translatable.

### 18. Inline poetry quotes — Gemini collapses them into surrounding narration

When the original has narration → poetry quote → continuation as three paragraphs, Gemini frequently squashes all three into one prose paragraph, dropping the poetry quote entirely or paraphrasing it inline. Sonnet can split the result at sentence-terminator boundaries adjacent to where the quote belongs, sometimes recovering structure without needing to re-inject the quote.

Pattern observed in: Anne ch.19, Anne ch.33, Little Women ch.47.

### 19. Project Gutenberg page-number markers (`0185m`, `30041m`) appear as standalone paragraphs

A specific Project Gutenberg edition format — all 117 chapters of Monte Cristo (book_id 80) had paragraphs matching `^[0-9]{4,5}m$` (e.g. `0023m`, `20227m`, `30041m`) — these are page-image anchors. Gemini correctly omits them from translation, so the count diff shows up everywhere.

**Bulk fix (one SQL transaction, 47 chapters in one shot):**

```python
import re, sqlite3
db = sqlite3.connect("data/database.db")
MARKER = re.compile(r"^[0-9]{4,5}m$")
for n, ot, mt in db.execute("SELECT chapter_number, chapter_text, modern_english_text FROM chapters WHERE book_id=80 AND modern_english_text IS NOT NULL"):
    op = ot.strip().split("\n\n")
    mp = mt.strip().split("\n\n")
    non_markers = [p for p in op if not MARKER.match(p.strip())]
    if len(non_markers) == len(mp):  # only fix if diff fully explained by markers
        db.execute("UPDATE chapters SET chapter_text=? WHERE book_id=80 AND chapter_number=?", ("\n\n".join(non_markers), n))
db.commit()
```

Always prefer **strip-from-orig** over insert-into-mod: it leaves `modern_english_text` clean and makes the audit truthful. Run BEFORE dispatching subagents — saves ~50× Sonnet invocations on a single MC-style book.

### 20. Double-strip pitfall — orig-side AND mod-side markers can coexist

If day-N subagents inserted page markers into `modern_english_text` (the "insert-into-mod" approach from §19's alternative), then a later day-N+1 orig-side strip removes them from orig but leaves mod with the markers — flipping the diff sign to negative. Detection: any chapter where `mod_has_markers and not orig_has_markers`. Fix: strip from mod too.

```python
import re, sqlite3
MARKER = re.compile(r"^[0-9]{4,5}m$")
db = sqlite3.connect("data/database.db")
for n, ot, mt in db.execute("SELECT chapter_number, chapter_text, modern_english_text FROM chapters WHERE book_id=? AND modern_english_text IS NOT NULL", (BOOK,)):
    op = ot.strip().split("\n\n"); mp = mt.strip().split("\n\n")
    orig_has = any(MARKER.match(p.strip()) for p in op)
    mod_has = any(MARKER.match(p.strip()) for p in mp)
    if mod_has and not orig_has:
        new_mp = [p for p in mp if not MARKER.match(p.strip())]
        db.execute("UPDATE chapters SET modern_english_text=? WHERE book_id=? AND chapter_number=?", ("\n\n".join(new_mp), BOOK, n))
db.commit()
```

**Process rule:** pick ONE side to strip markers from per book (preferably orig). If you ever mix strategies across runs, sweep with this double-strip detector before declaring done.

### 21. Hidden misalignment — count matches, content shifted

A count-matched chapter (`len(op) == len(mp)`) can still be wrong if a prior fix (or generation accident) split or merged paragraphs at the wrong place. The diff shows zero but mod paragraph K corresponds to orig paragraph K+1 (or K-1) for a stretch in the middle.

**Detection — scan for length-ratio outliers across paragraph pairs:**

```python
import sqlite3
db = sqlite3.connect("data/database.db")
def cnt(t): return len(t.strip().split("\n\n")) if t and t.strip() else 0
for bid in BOOKS:
    for n, ot, mt in db.execute("SELECT chapter_number, chapter_text, modern_english_text FROM chapters WHERE book_id=? AND modern_english_text IS NOT NULL", (bid,)):
        op = ot.strip().split("\n\n"); mp = mt.strip().split("\n\n")
        if len(op) != len(mp): continue  # only check count-aligned
        bad = sum(1 for o,m in zip(op,mp) if len(o) >= 30 and not 0.4 <= len(m)/max(1,len(o)) <= 2.5)
        if bad >= 2:
            print(f"book {bid} ch.{n}: {bad} paragraphs with suspicious length ratios — INSPECT")
```

Run this AFTER every batch of subagent fixes — it caught Brothers K ch.42 (subagent's 149-merge fix had count-match but split O4 across M4+M5), Cranford ch.5+ch.12 (missing `[Picture: ...]` cancelled out by over-splits elsewhere), and Crime ch.12 (subagent split M27 at an arbitrary char offset to absorb +1 diff, mis-aligning everything after).

**Fix pattern:** find the transition where the offset starts, undo the bad operation (merge an over-split or split an under-split), and apply the correct fix (usually insert a missing structural paragraph like `[Picture: ...]`).

### 22. Hard-wrapped originals masquerading as paragraphs (ch.0 preface gotcha)

Project Gutenberg preface/prelude/introduction chapters are often hard-wrapped at ~70 chars per line, with every line stored as a separate `\n\n`-delimited paragraph. Modern translations correctly produce one paragraph per *real* paragraph, so the count diff looks catastrophic (e.g. Crime ch.0: 73 orig "paragraphs" vs 13 mod). The standard `reformat_paragraphs.py` step targets a different format (single-`\n` paragraph breaks → `\n\n`) and doesn't catch this.

**Symptom:** `chapter_text` has `double \n\n count` >> `single \n count`, median paragraph length 15-70 chars, max ~70-72 chars (PG default column width). Almost always preface/prelude/intro chapters.

**Fix — reflow heuristic** (merge lines back into paragraphs):

```python
def reflow_hard_wrap(text):
    def is_title(s):
        core = s.rstrip(".")
        return len(s) < 50 and core.upper() == core and len(core) > 0
    paras = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    out, buf = [], paras[0] if paras else ""
    for nxt in paras[1:]:
        bs = buf.rstrip(); last = bs[-1] if bs else ""; first = nxt[0] if nxt else ""
        if is_title(bs):
            out.append(bs); buf = nxt; continue
        if is_title(nxt):
            out.append(bs); buf = nxt; continue
        if first.islower():
            buf = bs + " " + nxt; continue           # definite continuation
        if last not in '.!?":”’\')]':
            buf = bs + " " + nxt; continue            # buf ended mid-sentence
        if len(bs) < 25:
            buf = bs + " " + nxt; continue            # buf too short to be real para
        out.append(bs); buf = nxt
    out.append(buf.rstrip())
    return "\n\n".join(out)
```

**The user's insight was load-bearing:** *"merge the original text according to the modern translation"* — the modern is the structural truth, not the original. When orig has bogus paragraph breaks and mod doesn't, fix orig, don't try to make mod match orig. Cleared the last 3 stuck preface chapters (Crime ch.0 73→13, Middlemarch ch.0 143→4 with TOC strip, Ferdinand ch.0 319→32) without any Gemini calls.

**Special case — Middlemarch ch.0:** the chapter parser had absorbed a 96-paragraph TOC entry (PRELUDE + BOOK I-VIII + CHAPTER I-LXXXVI + FINALE) into ch.0 before the prelude prose itself starts at orig index 97. Strip the TOC slice first (`op[97:]`), then reflow.

### 23. Subagent verbatim-prose alternative — write a real modern translation when only one paragraph is missing

Per §5d-warning, you must never paste verbatim 19th-c prose to fix mid-chapter truncation. But for **single-paragraph drops** (Gemini omitted one specific narrative paragraph from the middle of a chapter, no surrounding damage), the subagent can write a modern-English translation of that single paragraph and insert it at the right index. Worked cleanly for Monte Cristo ch.35 (the Count's "Mad dog" speech ~460 chars) — the result is indistinguishable from a single-paragraph regen but doesn't burn a Gemini quota slot.

**Subagent prompt rule of thumb:**
- 1 paragraph missing → write a translation in modern English, insert via direct SQL
- 2-5 paragraphs missing → REPORT and recommend regen of just that chapter
- >5 paragraphs missing → certainly regen with gemini-3.5-flash

The cutoff exists because (a) one paragraph is small enough that a Sonnet translation matches the style of surrounding Gemini paragraphs reasonably well, and (b) anything larger risks compounding judgment errors and producing tone drift.

---

## Cost summary

**20-book initial migration (May 2026):**
- ~316 chapters across 20 books, average ~3 API calls per chapter (with reruns + escalations) ≈ ~70 paid API calls
- Almost all on `gemini-3.1-flash-lite` free tier (cost: $0)
- ~5 chapters escalated to `gemini-3.5-flash` (cost: <$0.10 at list pricing)
- ~10 Sonnet subagent invocations for alignment (cost: a few cents each via Anthropic API)
- **Total marginal spend: ~$1-2** for 316 chapters of paragraph-aligned plain English

**Top-10 next-batch session (May 31, 11 new books, 408 chapters → 100% match):**
- ~85 Gemini batches (~22 books worth — many regens for misalignments)
- All on `gemini-3.1-flash-lite` except ~25 calls on `gemini-3.5-flash` (exhausted the 20/day quota on day 1)
- **5 Sonnet subagent invocations** total — fixed 18 chapters at 100% success rate
- Key insight: every Sonnet call replaces 1-3 Gemini regens that would have eaten quota AND still might leave mismatches. ±5 rule pays back fast.

---

## When you find a new corner case

Add it to the "Books with notable corner cases" table above with: book/chapter, signal, fix. If the fix is a recurring pattern, also update the corresponding step (2, 3, or 5 sub-section). Update CLAUDE.md if the workflow steps themselves change.
