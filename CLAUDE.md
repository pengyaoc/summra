# Claude Instructions

## Work Log

Keep a work log for all tasks completed and in progress in `WORK_LOG.md`. Update the work log when task starts and update the status along the way. The work log would be used as future development context.

## Documentation

### PRD.md
Keep the Product Requirements Document at `docs/PRD.md` up-to-date with user-facing feature definitions. This should include:
- Feature descriptions and user stories
- User interface specifications
- User workflows and interactions
- Feature requirements and acceptance criteria

### ERD.md
Keep the Engineering Reference Document at `docs/ERD.md` up-to-date with technical details. This should include:
- Complex component and logic descriptions
- System components and architecture
- Database schema and data models
- Code structure and organization
- Technical implementation details

## Coding Principles

### Behavioral Guidelines

Reduce common LLM coding mistakes. Bias toward caution over speed; use judgment on trivial tasks.

**1. Think Before Coding** — Don't assume. Don't hide confusion. Surface tradeoffs.
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

**2. Simplicity First** — Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Test: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

**3. Surgical Changes** — Touch only what you must. Clean up only your own mess.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that *your* changes made unused; leave pre-existing dead code alone unless asked.
- Test: every changed line should trace directly to the user's request.

**4. Goal-Driven Execution** — Define success criteria. Loop until verified.
- Transform tasks into verifiable goals:
  - "Add validation" → "Write tests for invalid inputs, then make them pass"
  - "Fix the bug" → "Write a test that reproduces it, then make it pass"
  - "Refactor X" → "Ensure tests pass before and after"
- For multi-step tasks, state a brief plan with a verify check per step.
- Strong success criteria enable independent looping; weak criteria ("make it work") force constant clarification.

### Test-Driven Development (Required)

Every new feature, bug fix, or behavioral change MUST start with a failing test. No exceptions for "small" or "obvious" changes — those are exactly where regressions hide.

**The Red → Green → Refactor loop:**
1. **Red:** Write a test that describes the expected behavior. Run it. Confirm it fails for the *right reason* (asserting the missing behavior, not a syntax error or missing import).
2. **Green:** Write the minimum code that makes the test pass. No extra features, no speculative branches.
3. **Refactor:** Clean up while tests stay green. Run the full suite, not just the new test.

**If asked to "add feature X" or "fix bug Y," respond with:** *"Let me write a failing test first."* Do not skip ahead to implementation, even if the fix seems trivial.

**Required coverage for every change:**
- **Happy path** — the requested behavior with valid inputs
- **At least one edge case** — empty input, boundary values, invalid types, null/missing fields, or whatever applies
- **Bug fixes:** the test must reproduce the original bug and fail before your fix

**Never:**
- Modify a test to make it pass instead of fixing the implementation. If a test seems wrong, stop and flag it — don't silently edit it.
- Delete or skip failing tests to "make CI green."
- Mock the thing you're testing. Mock external boundaries (network, filesystem, time) only.
- Claim a task is done without showing the test output (pass count, not just exit code).

**Backend (pytest):** `pytest tests/ -v` — add tests under `tests/` mirroring the module path.
**Frontend (Playwright):** add a scenario to `tests/e2e/smoke.mjs` (or a new `*.mjs` next to it) and run `node smoke.mjs` — the harness exits non-zero on any failure.

**Why this is non-negotiable:** LLMs (including me) default to writing implementation first and tests after — which produces tests that confirm whatever was written, not what was specified. Writing the test first forces the spec to exist before the code does.

### DRY (Don't Repeat Yourself)
Follow the DRY principle to eliminate code duplication and maintain a single source of truth:

- **Identify Duplication:** When you notice identical or nearly identical code in multiple places, refactor to a shared function or method
- **Single Implementation:** Maintain one canonical implementation for each piece of logic
- **Easier Maintenance:** Changes should only need to be made in one place
- **Consistent Behavior:** Shared code ensures consistent behavior across the codebase

**Examples of DRY violations to avoid:**
- Duplicate text processing logic (e.g., separate normalization functions for different content types)
- Copy-pasted validation code
- Repeated API call patterns
- Duplicated database query logic

**How to refactor:**
1. Extract the common logic into a shared function
2. Update all call sites to use the shared function
3. Delete the duplicate implementations
4. Document the refactoring in WORK_LOG.md

**Recent example:** The `_clean_preface_text()` and `normalize_chapter_text()` methods performed identical text normalization. We eliminated the 84-line duplicate by using `normalize_chapter_text()` for both prefaces and chapters.

## Frontend Test Loop

Headless Chromium harness lives in `tests/e2e/`. Use it to verify frontend changes (templates, JS, CSS) without leaving the terminal.

**Setup (one-time):**
```sh
cd tests/e2e && npm install && npx playwright install chromium
```

**Loop:**
1. Start Flask in the background: `python backend/app.py` (binds `:5001` — `:5000` is taken by macOS ControlCenter).
2. Edit the template / JS / CSS.
3. Run `cd tests/e2e && node smoke.mjs` — defaults to `http://localhost:5001/`.
4. `Read` the PNG in `tests/e2e/screenshots/` to confirm visually.

**Flags:**
- `PATHS=/,/book/104,/explore node smoke.mjs` — visit multiple pages
- `HEADED=1 node smoke.mjs` — show the browser
- `BASE_URL=http://localhost:5000 node smoke.mjs` — override host/port

Exit code is non-zero on any non-200, console error, or failed first-party request (third-party analytics is filtered as noise). See `tests/e2e/README.md` for details.

## Parallel Sessions (Git Worktrees)

Run multiple Claude sessions on this repo by giving each its own git worktree. **Never share a working directory** — sessions will silently overwrite each other's edits.

**Setup (one-time):**
```sh
echo ".claude/worktrees/" >> .gitignore   # if not already present
```

**Create a worktree per session:**
```sh
git worktree add .claude/worktrees/<name> -b <branch>
git worktree list                          # see all
git worktree remove .claude/worktrees/<name>   # cleanup
```

**Per-session isolation (required):**
- **Flask port** — only one session can bind `:5001`. Others must use `PORT=5002 python backend/app.py` etc., and run smoke tests with `BASE_URL=http://localhost:5002 node smoke.mjs`.
- **Python venv** — each worktree needs its own `venv/` (or symlink a shared one, accepting that dep changes affect all).
- **`node_modules`** under `tests/e2e/` — reinstall per worktree or symlink.
- **SQLite DB at `data/summra.db`** — each worktree has its own copy; ingestion in one worktree is invisible to others.

**Practical limits:** 2–4 parallel sessions is the sweet spot. Beyond that, you lose the ability to review output and hit API rate limits.

**Scope discipline:** Give each session a non-overlapping slice (e.g., one on `scripts/content/`, one on `frontend/`, one on `scripts/audits/`). Two sessions editing the same file will produce merge conflicts at PR time.

**Git hygiene:**
- Commit at session boundaries — uncommitted state is the only thing that doesn't survive a reset.
- Prefer rebase over merge when integrating between worktrees (keeps history linear, easier for Claude to reason about).
- Clean up stale worktrees weekly — they accumulate uncommitted state and waste disk.

**Subagent worktree discipline:** Subagents inherit the parent's CWD but can `cd` anywhere and use absolute paths. A subagent spawned from a worktree can silently write to the main checkout (or commit to `main`) if not constrained. Always:
- **Brief explicitly** — subagents don't see conversation context. State the worktree path and branch in the prompt: "You are in worktree `.claude/worktrees/feature-x` on branch `feature-x`. Do NOT `cd` to the main checkout or use absolute paths outside this worktree."
- **Use relative paths** in subagent prompts (`backend/app.py`, not `/Users/pengyao/Documents/dev/summra/backend/app.py`).
- **For truly independent work, spawn with `isolation: "worktree"`** — the Agent tool creates a fresh worktree just for that subagent.
- **Verify before committing** — end subagent prompts with: "Before committing, run `pwd && git branch --show-current` and confirm it matches the expected worktree. If not, stop and report."
- **If a subagent writes to main unexpectedly:** `cd` to the main checkout, `git status` / `git log -5 main` to assess, then `git reset --hard HEAD~N` (local only) or `git revert <sha>` (if pushed). Re-do the work in the correct worktree.

## Book Ingestion Workflow (always dry-run first)

When asked to ingest a new book file (typically a `data/books/pg<id>.txt` from Project Gutenberg), follow this 3-step workflow. Do NOT skip the dry-run.

**1. Dry-run and review.**
```sh
PYTHONPATH=backend venv/bin/python scripts/content/generate_summaries.py data/books/<file> --dry-run
```
The `CHAPTER BREAKDOWN` block at the end prints each detected chapter with its title, char/word counts, and **start/end line numbers in the raw source file**. Read the source at those line numbers (or grep for `^CHAPTER\|^PART\|^BOOK\|^VOLUME` in the file) and verify:
  - Chapter count matches the source's actual chapter count.
  - Titles look right (real Hardy/Doyle/etc. titles, not garbage like `"V. \"Cithaeron\" (6): Oedipus..."`).
  - Coverage is ≥95% (printed at top of breakdown). If <95%, the parser likely lost content.
  - No chapter is monstrously large or tiny (e.g., Chapter 0 = entire book = "preface" is the canonical "swallowed the book" failure mode).
  - The `(anchor not found in raw file)` line-range note flags chapters whose first ~6 words don't appear in the raw source — usually means the title is from a TOC entry rather than real prose, or the chapter is the wrong content.

**2. Ingest only if dry-run looks correct.** If anything looks off, STOP. Either fix the parser for that case (rare, only for clearly script-side bugs like the `PART I.` → `'.'` capture or `M.D.` → `M.d.` normalization), or document the book as a known-bad case below.
```sh
PYTHONPATH=backend venv/bin/python scripts/content/generate_summaries.py data/books/<file> --parse-only
```
Note the new `book_id` printed.

**3. Validate after ingest.**
```sh
PYTHONPATH=backend venv/bin/python scripts/audits/validate_chapter_split.py --book-id <id> --llm-digest
```
The deterministic checks should be 0 FAIL and at most 1 WARN (the "off-by-one for preface" warning is expected for most books). Read the `--llm-digest` block and spot-check that titles + first/last 200 chars look right per chapter.

### Known-bad book classes — do NOT attempt to auto-ingest

The parser is tuned for **single-work prose novels with explicit CHAPTER markers** (and the two-level PART/CHAPTER variant). The following classes fail in known ways. Recognize them from the dry-run output and either skip, or ingest manually:

1. **Anthologies / multi-work books.** Example: `pg100.txt` (Complete Works of Shakespeare, 38 plays in one file). Symptom: ~25% coverage, a single "chapter" 1MB+, ACT markers detected from the *first* play only. **Fix:** these aren't a "book" in our model — skip, or split the source into per-work files manually.

2. **Aphoristic / non-chaptered classics.** Example: `pg2680.txt` (Marcus Aurelius's *Meditations* — 12 numbered books of aphorisms, no explicit chapter markers in body, only translator's footnotes use `BOOK X` for cross-references). Symptom: parser matches lowercase prose like `"part concerned with outward things"` mid-sentence as a PART marker because `re.IGNORECASE` is on. Underlying bug: `section_pattern` lowercased matches absorb prose. **Fix candidate (deferred):** add a structural guard (require surrounding blank lines, reject if first word of next line is also lowercase). For now: skip.

3. **Books with no in-body chapter markers / non-English structure.** Example: `pg175.txt` (Leroux's *Phantom of the Opera* — English translation but uses unusual heading conventions). Symptom: 2 chapters detected, one is the entire book as "Preface" (76K words), the other is title `'.'` (1 chapter from a stray match). **Fix:** skip.

See `WORK_LOG.md` "Failed-to-parse list" for the canonical inventory of skipped books with rationale per file.

### Cases the parser handles well (no special handling needed)

- Novels with `CHAPTER I`, `CHAPTER II` etc. markers on their own line (`pg23`, `pg110`, `pg1695`, `pg2852`, etc.).
- Two-level books: `PART I` / `PART II` with `CHAPTER I..N` inside each (`pg244`, `pg2600`, `pg1399`).
- BOOK-as-chapter aphoristic works where each BOOK is one logical chapter (`pg3296` Augustine's *Confessions*).
- Books with `Chapter N` in title case rather than `CHAPTER N`.
- Empty PART subtitle (`PART I.` with no title text) — captured as empty string, not `'.'`.
- Dotted abbreviations in titles like `M.D.`, `Ph.D.`, `U.S.A.` — preserved through case normalization.

### Tests covering these cases
- `tests/test_book_chapter_name_detection.py` — title normalization (incl. dotted abbreviations)
- `tests/test_part_section_title.py` — bare `PART I.` regression
- `tests/test_derive_chapter_line_ranges.py` — line-range helper for dry-run output
- `tests/test_validate_chapter_split.py` — post-ingest deterministic validator
- `tests/test_two_level_toc.py` — multi-part book regression suite

## Plain English (Modern Translation) Workflow

When generating or fixing the `chapters.modern_english_text` column, follow this 6-step process in order. Steps 2, 3, 4, and 6 are **mechanical** (no LLM cost); step 1 and step 5's regen path are paid Gemini calls — confirm cost discipline before running. **Target is EXACT paragraph match** (`orig - mod == 0`), not ±2 — paragraph boundaries are load-bearing for the side-by-side reading view.

### 1. Generate the plain-English version

```sh
PYTHONPATH=backend venv/bin/python scripts/content/generate_modern_english.py --book-id <id> --all-chapters --dry-run
PYTHONPATH=backend venv/bin/python scripts/content/generate_modern_english.py --book-id <id> --all-chapters
```

Always dry-run first to confirm batch count and chapter sizes. **Always start with the default `gemini-3.1-flash-lite`** — it's the cheapest/fastest model and handles most chapters. Only escalate to `--model gemini-3.5-flash` for individual chapters that come back truncated or summary-shaped (see step 4 for how to detect).

The prompt instructs Gemini to keep the chapter title as the first paragraph of its translation. Older runs (before the prompt fix) often dropped titles — step 5 fixes those mechanically.

For multi-book batches, run several books in parallel but respect rate limits — Gemini free tier allows ~5 RPM. Each book's batches sleep 3s between calls; running 4–5 books concurrently usually stays within the limit because each batch takes 30–180 seconds.

Raw responses are persisted to `data/log/gemini_logs/`; per-chapter previews to `data/log/modern_english/`. Never run without permission per `MEMORY.md → feedback_llm_cost.md`.

### 2. Reformat hard-wrapped paragraphs

Older ingests stored `chapter_text` (and some `modern_english_text`) as hard-wrapped with single `\n` between paragraphs instead of `\n\n`. The generator's paragraph validator splits on `\n\n` and will misreport `Orig=1, Modern=N` for these. Fix:

```sh
PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id <id> --dry-run
PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id <id>
# Also reformat modern_english_text if it has the same shape:
PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id <id> --column modern_english_text
```

The script refuses to touch `is_poetry=1` books (single `\n` is a verse line break, not a paragraph). The transform is idempotent. Tests at `tests/test_reformat_paragraphs.py`.

### 3. Strip decorative section dividers

Some books use rows of `* * * * *` (or dashes/dots) as scene-break markers — Alice ch.1 has 6 of them (Carroll marks size changes), Dracula has them in 23 of 28 chapters. Gemini correctly ignores them as non-content, so modern winds up short. Strip them from BOTH columns so paragraph counts align:

```sh
PYTHONPATH=backend venv/bin/python scripts/audits/strip_decorative_dividers.py --book-id <id> --dry-run
PYTHONPATH=backend venv/bin/python scripts/audits/strip_decorative_dividers.py --book-id <id>
```

Removes any paragraph that's entirely whitespace + decorative chars (`* - . … • · ~ _ =`). Idempotent. Tests at `tests/test_strip_decorative_dividers.py`.

### 4. Audit paragraph and character differences

For each chapter with `modern_english_text`, check ALL of the following — any single failure is a real problem:

- **`paragraph_diff == 0`** — `len(chapter_text.split('\n\n')) == len(modern_english_text.split('\n\n'))`. Off-by-1 usually means a missing title (fix in step 5); larger diffs usually mean truncation or Gemini merge/split.
- **`char_ratio` in `[0.50, 1.10]`** — `len(modern) / len(original)`. Below 50% almost always means truncation or summary substitution; flag for regen in step 5.
- **Modern ends at a sentence terminator** — last non-whitespace char in `.!?")'”’`. Mid-word endings like `"...risky har"` are an instant-fail truncation signal. Endings on `”` (smart quote) are VALID — earlier audits mis-flagged these.
- **Modern's ending matches original's narrative endpoint** — compare last ~200 chars of both. If they describe different events, modern was truncated.
- **Title alignment** — if original's first paragraph IS the chapter title (short, matches `chapters.chapter_title` case-insensitively) but modern's first paragraph is NOT, prepend the title to modern in step 5. This is the single most common cause of off-by-1 diffs.

Quick per-book audit (replace `BOOK_ID`):

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

### 5. Fix paragraph misalignment

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
PYTHONPATH=backend venv/bin/python scripts/audits/split_modern_paragraphs.py --book-id <id> --chapter-number <n> --inspect --snippet 200
PYTHONPATH=backend venv/bin/python scripts/audits/split_modern_paragraphs.py --book-id <id> --chapter-number <n> --split "5:200,7:100" --dry-run
PYTHONPATH=backend venv/bin/python scripts/audits/split_modern_paragraphs.py --book-id <id> --chapter-number <n> --split "5:200,7:100"
```

Tests at `tests/test_split_modern_paragraphs.py`.

### 6. Regenerate damaged chapters (Gemini)

When step 4 audit flags a chapter as truncated, summary-shaped, or has a massive irreducible diff that can't be fixed mechanically, regenerate with Gemini:

- **Truncated** — modern ends mid-sentence and is <50% of original length. Cause: `gemini-3.1-flash-lite` cut the output on a long chapter. Fix: re-run that single chapter; flash-lite is non-deterministic at temperature 0.3 and may produce a full response on retry. If a second flash-lite attempt also truncates, escalate that chapter to `--model gemini-3.5-flash`.
- **Summary-shaped** — modern is 1 paragraph or <30% of original length, with condensed content. Sometimes Gemini prefaces with "I have provided a modern English summary of each section". Same flash-lite-first, escalate-to-3.5-on-repeat rule.
- **Massive paragraph mismatch (diff >50 with valid full-length content)** — modern merged many original paragraphs. Manual alignment via subagent is infeasible without splitting mid-sentence. Escalate to `gemini-3.5-flash` which tends to preserve paragraph structure better. Some monster chapters (Odyssey ch.24 at 252 paragraphs / 79K chars) remain stubbornly summary-shaped even on 3.5-flash — accept and flag for manual review in those cases.
- **Verse books** (`is_poetry=1`) — single `\n` is a verse line, not a paragraph. The paragraph-count check is meaningless. Suppress or skip.

After regenerating, return to step 2 to reformat then re-audit (steps 3–5).

```sh
PYTHONPATH=backend venv/bin/python scripts/content/generate_modern_english.py --book-id <id> --chapters "N,N" --model gemini-3.5-flash
```

## Deploying to Production (GCP VM)

Production runs on a GCP VM serving **https://summrabook.com** (NOT `summra.com` — that's a stale parked domain still referenced in code comments and `app_base.py` sitemap entries; ignore those when verifying prod).

**VM facts:**
- Project: `project-7f192cbf-77f3-4f7a-acc`, instance `instance-20251125-033837`, zone `us-west1-b`, external IP `34.82.3.27`
- Repo at `/var/www/summra` (owned `pengyaoc:www-data`, group-writable)
- venv at `/var/www/summra/venv/` (Python 3.11)
- systemd unit `summra.service` runs gunicorn as `www-data`: `-c deploy/gunicorn_config.py backend.app_prod:app`, bound to `:5000`
- nginx terminates TLS for `summrabook.com` and proxies to `:5000`
- DB at `/var/www/summra/data/database.db` (`pengyaoc:www-data`, mode `664`)
- Pull/git work runs as `pengyaoc`; service work needs `sudo`

All commands below assume you're driving the VM remotely via `gcloud compute ssh ... --command="..."`. The base SSH invocation:

```sh
gcloud compute ssh instance-20251125-033837 --zone=us-west1-b --command="<remote command>"
```

### 1. Pull latest `main` on the VM

Always check status first; if behind, fast-forward only (never merge unknown VM-local changes):

```sh
gcloud compute ssh instance-20251125-033837 --zone=us-west1-b --command="sudo -u pengyaoc bash -c 'cd /var/www/summra && git fetch origin --quiet && BEHIND=\$(git rev-list --count HEAD..origin/main) && echo BEHIND=\$BEHIND && if [ \$BEHIND -gt 0 ]; then git log --oneline HEAD..origin/main && git pull --ff-only; else echo Already up-to-date; fi'"
```

**If the pull fails with "your local changes would be overwritten":** the VM has uncommitted state. Do NOT `git stash` or `--hard reset` blindly. Run `git diff HEAD -- backend/` to see if any divergence is prod-only (env-specific config, hot-patches). If it's truly safe to discard, snapshot first to a backup branch:

```sh
sudo -u pengyaoc bash -c 'cd /var/www/summra && git checkout -b vm-state-backup-$(date +%Y%m%d-%H%M%S) && git add -A && git commit -m "snapshot VM working state before reset" && git checkout main && git reset --hard origin/main'
```

The backup branch survives so you can cherry-pick anything that turns out to matter.

### 2. Check whether a restart is needed

| Changed file | Restart? |
|---|---|
| `backend/**` (any `.py` under backend/) | **Yes** — gunicorn workers cache imported modules |
| `backend/requirements.txt` | **Yes** + `pip install -r backend/requirements.txt` inside the venv first |
| `backend/models.py` schema changes | **Yes** — `Database.__init__` runs idempotent ALTER-TABLE migrations on boot |
| `deploy/gunicorn_config.py` | **Yes** |
| `/etc/systemd/system/summra.service` | **Yes** + `sudo systemctl daemon-reload` first |
| `frontend/templates/**` | No — Flask re-reads templates per request |
| `frontend/static/**` (CSS, JS, images) | No — nginx serves directly. Bump cache-busting query string in `index.html` if you need clients to pull a new asset |
| `data/books/**` raw text | No — only used during ingestion, not at request time |
| `docs/**`, `WORK_LOG.md`, `README.md`, `tests/**` | No |

```sh
gcloud compute ssh instance-20251125-033837 --zone=us-west1-b --command="sudo systemctl restart summra.service && sleep 3 && sudo systemctl is-active summra.service && curl -sS -o /dev/null -w 'local HTTP %{http_code}\n' http://127.0.0.1:5000/ && sudo journalctl -u summra.service --since '1 minute ago' --no-pager | grep -iE 'error|exception|traceback' | grep -v 'sent SIGTERM' | tail -5 || echo no errors"
```

### 3. Verify public site after deploy

```sh
curl -sSL -o /dev/null -w 'GET /         HTTP %{http_code}  time=%{time_total}s\n' https://summrabook.com/
curl -sSL -o /dev/null -w 'GET /books    HTTP %{http_code}  time=%{time_total}s\n' https://summrabook.com/books
curl -sSL -o /dev/null -w 'GET /api/books HTTP %{http_code}  time=%{time_total}s\n' https://summrabook.com/api/books
```

All should return 200 in under ~1s. If any return 500, check `sudo journalctl -u summra.service --no-pager | tail -50` on the VM.

### 4. Copy local `database.db` to VM and activate it

The VM's DB is the live source of truth for prod. Replacing it is destructive — overwrites whatever has been ingested directly on the VM. Today the VM does NOT take writes (no auth, no user content), so the only thing at risk is recent ingestion done on the VM itself; in practice all ingestion happens locally and is pushed via this flow.

**Pre-flight (always):**
```sh
# row counts side-by-side
sqlite3 /Users/pengyao/Documents/dev/summra/data/database.db "SELECT 'books='||COUNT(*) FROM books UNION ALL SELECT 'chapters='||COUNT(*) FROM chapters UNION ALL SELECT 'authors='||COUNT(*) FROM authors;"
gcloud compute ssh instance-20251125-033837 --zone=us-west1-b --command="sudo -u www-data /var/www/summra/venv/bin/python3 -c \"
import sqlite3
c = sqlite3.connect('/var/www/summra/data/database.db').cursor()
for tbl in ('books','chapters','authors'): print(f'{tbl}=' + str(c.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]))
\""
```

If VM counts are higher than local for anything other than `blog_posts`, STOP — the VM has data that's not in local. Investigate first.

**Copy and activate:**
```sh
# 1. Snapshot VM's current DB
gcloud compute ssh instance-20251125-033837 --zone=us-west1-b --command="sudo cp /var/www/summra/data/database.db /var/www/summra/data/database.db.bak-pre-copy-\$(date +%Y%m%d-%H%M%S) && ls -lh /var/www/summra/data/database.db*"

# 2. SCP local DB to /tmp on VM (can't scp directly into /var/www — perms)
gcloud compute scp /Users/pengyao/Documents/dev/summra/data/database.db instance-20251125-033837:/tmp/database.db.new --zone=us-west1-b

# 3. Verify checksums match (paranoid but cheap)
md5 -q /Users/pengyao/Documents/dev/summra/data/database.db
gcloud compute ssh instance-20251125-033837 --zone=us-west1-b --command="md5sum /tmp/database.db.new"

# 4. Stop service, move into place with correct ownership, restart
gcloud compute ssh instance-20251125-033837 --zone=us-west1-b --command="sudo systemctl stop summra.service && sudo mv /tmp/database.db.new /var/www/summra/data/database.db && sudo chown pengyaoc:www-data /var/www/summra/data/database.db && sudo chmod 664 /var/www/summra/data/database.db && sudo systemctl start summra.service && sleep 3 && sudo systemctl is-active summra.service"
```

**Why stop/start instead of just restart:** gunicorn workers hold open SQLite file handles. A live `mv` over the DB leaves workers reading the old (now unlinked) inode until they're recycled — better to take the request path down for ~5s and bring it back on a clean file.

**Why chmod 664 + group www-data:** Flask runs as `www-data`. The DB needs to be group-readable; the group-write bit lets future writes (if FEATURE_AUTH ever flips on) work without a re-chown.

**Verify the new DB is live:**
```sh
# Confirm a row only present in the new DB resolves publicly. Replace <new-slug>
# with a book that exists locally but did NOT exist on the VM pre-copy.
curl -sSL -o /dev/null -w 'GET /books/<new-slug> HTTP %{http_code}\n' https://summrabook.com/books/<new-slug>
curl -sSL https://summrabook.com/api/books | python3 -c "import sys, json; d=json.load(sys.stdin); books=d.get('books', d); print(f'total: {len(books)}')"
```

**Backups accumulate.** `data/database.db.bak-pre-copy-*` on the VM is root-owned and ~170M each. Periodically: `sudo rm /var/www/summra/data/database.db.bak-pre-copy-*` after you're sure the deploy is healthy (keep at most the last 1–2).
