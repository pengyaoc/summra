# Claude Instructions

## Work Log

Keep a work log for all tasks completed and in progress in `WORK_LOG.md`. Update the work log when task starts and update the status along the way. The work log would be used as future development context.

## Documentation

PRD and ERD are split by app (2026-11-11): `docs/shared/`, `docs/plainly/` and `docs/distill/` each have a `PRD.md` and an `ERD.md`. Update the files for the code you changed: `shared/` → `docs/shared/`, and so on. A change that touches several parts updates each one. `docs/PRD.md` and `docs/ERD.md` are only indexes.

### PRD.md
Keep the Product Requirements Document (`docs/<part>/PRD.md`) up-to-date with user-facing feature definitions. This should include:
- Feature descriptions and user stories
- User interface specifications
- User workflows and interactions
- Feature requirements and acceptance criteria

### ERD.md
Keep the Engineering Reference Document (`docs/<part>/ERD.md`) up-to-date with technical details. This should include:
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
1. Start Flask in the background: `python plainly/app.py` (binds `:5001` — `:5000` is taken by macOS ControlCenter).
2. Edit the template / JS / CSS.
3. Run `cd tests/e2e && node smoke.mjs` — defaults to `http://localhost:5001/`.
4. `Read` the PNG in `tests/e2e/screenshots/` to confirm visually.

**Flags:**
- `PATHS=/,/book/104,/explore node smoke.mjs` — visit multiple pages
- `HEADED=1 node smoke.mjs` — show the browser
- `BASE_URL=http://localhost:5000 node smoke.mjs` — override host/port

Exit code is non-zero on any non-200, console error, or failed first-party request (third-party analytics is filtered as noise). See `tests/e2e/README.md` for details.

**Distill (second app, port 5003):**
1. Start it with its own scratch user DB: `DISTILL_USER_DB=$TMPDIR/distill_user_e2e.db PORT=5003 venv/bin/python -m distill.app` (auth is `off` locally; it binds loopback).
2. `cd tests/e2e && node distill.mjs` (defaults to `http://localhost:5003`) runs three passes: desktop, mobile (375×667) and Kindle (758×950). It exits non-zero on any FAIL or console error.
3. `reader_style_snapshot.mjs` defaults to `:5001`, so set `BASE_URL` (`MODE=record|compare BASE_URL=http://localhost:5002 node reader_style_snapshot.mjs`). It guards the shared reader's computed styles for Plainly.

The 14 Plainly e2e scripts to run after any change under `shared/` or `plainly/`: `smoke`, `kindle_mode`, `reader_progress`, `reader_themes`, `reader_last_line_visible`, `reader_opens_at_chapter`, `reader_segments_fast_open`, `reader_illustrations`, `reader_font_figtree`, `reader_nav_mouse`, `sxs_row_split`, `text_size_adjust`, `redesign_home`, `redesign_reader` (each `node <name>.mjs` against your Plainly server's `BASE_URL`).

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
- **Flask port** — only one session can bind `:5001`. Others must use `PORT=5002 python plainly/app.py` etc., and run smoke tests with `BASE_URL=http://localhost:5002 node smoke.mjs`.
- **Python venv** — each worktree needs its own `venv/` (or symlink a shared one, accepting that dep changes affect all).
- **`node_modules`** under `tests/e2e/` — reinstall per worktree or symlink.
- **SQLite DB at `data/summra.db`** — each worktree has its own copy; ingestion in one worktree is invisible to others.

**Practical limits:** 2–4 parallel sessions is the sweet spot. Beyond that, you lose the ability to review output and hit API rate limits.

**Scope discipline:** Give each session a non-overlapping slice (e.g., one on `plainly/scripts/content/`, one on `plainly/frontend/`, one on `plainly/scripts/audits/`). Two sessions editing the same file will produce merge conflicts at PR time.

**Git hygiene:**
- Commit at session boundaries — uncommitted state is the only thing that doesn't survive a reset.
- Prefer rebase over merge when integrating between worktrees (keeps history linear, easier for Claude to reason about).
- Clean up stale worktrees weekly — they accumulate uncommitted state and waste disk.

**Subagent worktree discipline:** Subagents inherit the parent's CWD but can `cd` anywhere and use absolute paths. A subagent spawned from a worktree can silently write to the main checkout (or commit to `main`) if not constrained. Always:
- **Brief explicitly** — subagents don't see conversation context. State the worktree path and branch in the prompt: "You are in worktree `.claude/worktrees/feature-x` on branch `feature-x`. Do NOT `cd` to the main checkout or use absolute paths outside this worktree."
- **Use relative paths** in subagent prompts (`plainly/app.py`, not an absolute path to your local checkout).
- **For truly independent work, spawn with `isolation: "worktree"`** — the Agent tool creates a fresh worktree just for that subagent.
- **Verify before committing** — end subagent prompts with: "Before committing, run `pwd && git branch --show-current` and confirm it matches the expected worktree. If not, stop and report."
- **If a subagent writes to main unexpectedly:** `cd` to the main checkout, `git status` / `git log -5 main` to assess, then `git reset --hard HEAD~N` (local only) or `git revert <sha>` (if pushed). Re-do the work in the correct worktree.

## Plainly: book ingestion (always dry-run first)

Full workflow, known-bad book classes and the tests that cover them: [`docs/plainly/ingestion_workflow.md`](docs/plainly/ingestion_workflow.md). Read it before ingesting any book.
- Dry-run (`generate_summaries ... --dry-run`) and check the `CHAPTER BREAKDOWN` before `--parse-only`. If anything looks off, STOP.
- Afterwards, `validate_chapter_split --book-id <id> --llm-digest` must give 0 FAIL and at most 1 WARN.
- Skip anthologies, aphoristic works without chapter markers, and books with unusual heading conventions.

## Plainly: Plain English text

- Default: [`docs/plainly/agent_plain_english_workflow.md`](docs/plainly/agent_plain_english_workflow.md).
  - Under Claude: `plain-english-writer` and a fresh `plain-english-verifier` (`.claude/agents/`, Sonnet). Never Haiku.
  - Under Codex: GPT 6.1 Sol, low effort for writers, medium for fresh verifiers.
- Gemini only when explicitly requested, and never without the owner's permission (cost).
- Step-by-step checklist (generate, reformat, strip dividers, audit, fix, regenerate): [`docs/plainly/plain_english_checklist.md`](docs/plainly/plain_english_checklist.md). Long-form history: [`docs/plainly/plain_english_workflow.md`](docs/plainly/plain_english_workflow.md). Lessons per book: [`docs/plainly/agent_plain_english_learnings.md`](docs/plainly/agent_plain_english_learnings.md).
- Target an EXACT paragraph match (`orig - mod == 0`). Paragraph boundaries drive the side-by-side view.

## Deploying (one GCP VM, both apps)

- Concrete identifiers live in the gitignored `.prod-metadata.local.md`. Never commit them.
- Plainly: [`deploy/plainly/RUNBOOK.md`](deploy/plainly/RUNBOOK.md) covers the VM shape, pull, the restart matrix, verification and the database copy.
- Distill: [`deploy/distill/RUNBOOK.md`](deploy/distill/RUNBOOK.md). Code goes through `distill.scripts.deploy_code`, content through `deploy_db` / `push_book --deploy`. Run code before content.
- Use the repo scripts. No hand-built SSH or one-off Python where a script exists.
