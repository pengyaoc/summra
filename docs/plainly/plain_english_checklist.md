# Plain English (Modern Translation) Workflow

> Moved from `CLAUDE.md` on 2026-11-11 so agent instructions stay short. `CLAUDE.md` links here; this file is the source of truth.

**Default subagent workflow:** follow `docs/plainly/agent_plain_english_workflow.md` with host-native subagents. **Under Codex**, use GPT 6.1 Sol (`gpt-6.1-sol`) with low effort for writers and medium effort for separate, fresh verifiers. **Under Claude**, retain `plain-english-writer` and fresh `plain-english-verifier` (`.claude/agents/`, both Sonnet, low/medium effort respectively). The writing rules come from the shared prompt via `RULES.md`. Never use Haiku as the writer. Use cleanup, gate, independent meaning review, apply and reader checks from that workflow. Gemini below is an alternative only when explicitly requested. Lessons per book are in `docs/plainly/agent_plain_english_learnings.md`.

When generating or fixing the `chapters.modern_english_text` column, follow this 6-step process in order. Steps 2, 3, 4, and 6 are **mechanical** (no LLM cost); step 1 and step 5's regen path are paid Gemini calls — confirm cost discipline before running. **Target is EXACT paragraph match** (`orig - mod == 0`), not ±2 — paragraph boundaries are load-bearing for the side-by-side reading view.

## 1. Generate the plain-English version

```sh
venv/bin/python -m plainly.scripts.content.generate_modern_english --book-id <id> --all-chapters --dry-run
venv/bin/python -m plainly.scripts.content.generate_modern_english --book-id <id> --all-chapters
```

Always dry-run first to confirm batch count and chapter sizes. **Always start with the default `gemini-3.1-flash-lite`** — it's the cheapest/fastest model and handles most chapters. Only escalate to `--model gemini-3.5-flash` for individual chapters that come back truncated or summary-shaped (see step 4 for how to detect).

The prompt instructs Gemini to keep the chapter title as the first paragraph of its translation. Older runs (before the prompt fix) often dropped titles — step 5 fixes those mechanically.

For multi-book batches, run several books in parallel but respect rate limits — Gemini free tier allows ~5 RPM. Each book's batches sleep 3s between calls; running 4–5 books concurrently usually stays within the limit because each batch takes 30–180 seconds.

Raw responses are persisted to `data/log/gemini_logs/`; per-chapter previews to `data/log/modern_english/`. Never run without permission per `MEMORY.md → feedback_llm_cost.md`.

## 2. Reformat hard-wrapped paragraphs

Older ingests stored `chapter_text` (and some `modern_english_text`) as hard-wrapped with single `\n` between paragraphs instead of `\n\n`. The generator's paragraph validator splits on `\n\n` and will misreport `Orig=1, Modern=N` for these. Fix:

```sh
venv/bin/python -m plainly.scripts.audits.reformat_paragraphs --book-id <id> --dry-run
venv/bin/python -m plainly.scripts.audits.reformat_paragraphs --book-id <id>
# Also reformat modern_english_text if it has the same shape:
venv/bin/python -m plainly.scripts.audits.reformat_paragraphs --book-id <id> --column modern_english_text
```

The script refuses to touch `is_poetry=1` books (single `\n` is a verse line break, not a paragraph). The transform is idempotent. Tests at `tests/test_reformat_paragraphs.py`.

## 3. Strip decorative section dividers

Some books use rows of `* * * * *` (or dashes/dots) as scene-break markers — Alice ch.1 has 6 of them (Carroll marks size changes), Dracula has them in 23 of 28 chapters. Gemini correctly ignores them as non-content, so modern winds up short. Strip them from BOTH columns so paragraph counts align:

```sh
venv/bin/python -m plainly.scripts.audits.strip_decorative_dividers --book-id <id> --dry-run
venv/bin/python -m plainly.scripts.audits.strip_decorative_dividers --book-id <id>
```

Removes any paragraph that's entirely whitespace + decorative chars (`* - . … • · ~ _ =`). Idempotent. Tests at `tests/test_strip_decorative_dividers.py`.

## 4. Audit paragraph and character differences

For each chapter with `modern_english_text`, check ALL of the following — any single failure is a real problem:

- **`paragraph_diff == 0`** — `len(chapter_text.split('\n\n')) == len(modern_english_text.split('\n\n'))`. Off-by-1 usually means a missing title (fix in step 5); larger diffs usually mean truncation or Gemini merge/split.
- **`char_ratio` in `[0.50, 1.10]`** — `len(modern) / len(original)`. Below 50% almost always means truncation or summary substitution; flag for regen in step 5.
- **Modern ends at a sentence terminator** — last non-whitespace char in `.!?")'”’`. Mid-word endings like `"...risky har"` are an instant-fail truncation signal. Endings on `”` (smart quote) are VALID — earlier audits mis-flagged these.
- **Modern's ending matches original's narrative endpoint** — compare last ~200 chars of both. If they describe different events, modern was truncated.
- **Title alignment** — if original's first paragraph IS the chapter title (short, matches `chapters.chapter_title` case-insensitively) but modern's first paragraph is NOT, prepend the title to modern in step 5. This is the single most common cause of off-by-1 diffs.

Quick per-book audit (replace `BOOK_ID`):

```sh
venv/bin/python3 -c "
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

## 5. Fix paragraph misalignment

**Decision rule:** if `abs(diff) ≤ 5`, ALWAYS dispatch a Sonnet subagent to split/merge mechanically. Do NOT call Gemini to regenerate the chapter. Sonnet subagents reliably fix small deltas (the prior batch covered diffs from ±1 to ±4 across 14 chapters of Uncle Tom's Cabin with 100% success rate) and avoid burning Gemini quota or risking truncation on retry. Regenerate via step 6 only when `abs(diff) > 5` OR the chapter is truncated/summary-shaped.

Try mechanical fixes FIRST — most off-by-N diffs are these patterns, fixable without LLMs:

**5a. Missing title in modern (most common — off-by-1).** The original's first paragraph IS the chapter title, but Gemini's translation dropped it. Prepend the title using the body's casing (the body may be `UPPERCASE` while `chapters.chapter_title` is title-case — use the body's version):

```python
import sqlite3
db = sqlite3.connect("data/database.db")
for r in db.execute("SELECT chapter_number, chapter_title, chapter_text, modern_english_text FROM chapters WHERE book_id=BOOK_ID ORDER BY chapter_number"):
    n, title, ot, mt = r
    if mt is None: continue
    op = ot.split("\n\n")[0]
    mp = mt.split("\n\n")[0]
    if title and title.lower() in op.lower() and len(op) < len(title) + 20:
        if title.lower() not in mp.lower():
            body_title = op.strip()  # preserves original's casing
            new_mt = f"{body_title}\n\n{mt}"
            db.execute("UPDATE chapters SET modern_english_text=? WHERE book_id=BOOK_ID AND chapter_number=?", (new_mt, n))
            print(f"Fixed ch.{n}: prepended {body_title!r}")
db.commit()
```

**5b. Trailing transcriber or printer notes (rare).** Original ends with paragraphs like `"Printed in Canada..."` or `"[Transcriber's Note: ...]"` that Gemini dropped. Append the missing tail paragraphs verbatim from the original.

**5c. Internal Gemini merge/split (when 5a and 5b don't apply).** Dispatch one **Sonnet** subagent per chapter (NOT Haiku — Haiku has produced silent sentence-cut damage on truncated chapters: Odyssey ch.2/14, Oliver Twist ch.3/12, Moby Dick ch.81 all required regen after Haiku splits). Sonnet subagent constraints (bake into prompt):

- ONLY modify that single chapter (`book_id` + `chapter_number`).
- ALWAYS dry-run via `--split "..." --dry-run` before applying.
- NEVER split mid-sentence — only at sentence-terminator boundaries.
- Target paragraph counts must match EXACTLY (`orig - mod == 0`). Don't stop at ±2.
- If the split points don't visually align with original paragraph boundaries, REPORT and exit. Don't guess.

**Gate before dispatching subagent**: confirm step 4 passed `char_ratio ≥ 0.50` AND modern ends at a sentence terminator. If either fails, regenerate via step 6 — do NOT call the subagent on truncated text.

Tools:

```sh
venv/bin/python -m plainly.scripts.audits.split_modern_paragraphs --book-id <id> --chapter-number <n> --inspect --snippet 200
venv/bin/python -m plainly.scripts.audits.split_modern_paragraphs --book-id <id> --chapter-number <n> --split "5:200,7:100" --dry-run
venv/bin/python -m plainly.scripts.audits.split_modern_paragraphs --book-id <id> --chapter-number <n> --split "5:200,7:100"
```

Tests at `tests/test_split_modern_paragraphs.py`.

## 6. Regenerate damaged chapters (Gemini)

When step 4 audit flags a chapter as truncated, summary-shaped, or has a massive irreducible diff that can't be fixed mechanically, regenerate with Gemini:

- **Truncated** — modern ends mid-sentence and is <50% of original length. Cause: `gemini-3.1-flash-lite` cut the output on a long chapter. Fix: re-run that single chapter; flash-lite is non-deterministic at temperature 0.3 and may produce a full response on retry. If a second flash-lite attempt also truncates, escalate that chapter to `--model gemini-3.5-flash`.
- **Summary-shaped** — modern is 1 paragraph or <30% of original length, with condensed content. Sometimes Gemini prefaces with "I have provided a modern English summary of each section". Same flash-lite-first, escalate-to-3.5-on-repeat rule.
- **Massive paragraph mismatch (diff >50 with valid full-length content)** — modern merged many original paragraphs. Manual alignment via subagent is infeasible without splitting mid-sentence. Escalate to `gemini-3.5-flash` which tends to preserve paragraph structure better. Some monster chapters (Odyssey ch.24 at 252 paragraphs / 79K chars) remain stubbornly summary-shaped even on 3.5-flash — accept and flag for manual review in those cases.
- **Verse books** (`is_poetry=1`) — single `\n` is a verse line. Segment the original into blank-line passages with `plainly/scripts/content/segment_verse_passages.py`, then the paragraph check compares passages to plain paragraphs and must be exact. Paradise Lost's Plain English was written per passage by agents and gated with `plainly/scripts/content/passage_rewrite.py check`; reuse that for other verse books.

After regenerating, return to step 2 to reformat then re-audit (steps 3–5).

```sh
venv/bin/python -m plainly.scripts.content.generate_modern_english --book-id <id> --chapters "N,N" --model gemini-3.5-flash
```
