# Claude Instructions

## Work Log

Keep a work log for all tasks completed and in progress in `WORK_LOG.md`. Update the work log when task starts and update the status along the way. The work log would be used as future development context.

## Documentation

### PRD.md
Keep the Product Requirements Document up-to-date with user-facing feature definitions. This should include:
- Feature descriptions and user stories
- User interface specifications
- User workflows and interactions
- Feature requirements and acceptance criteria

### ERD.md
Keep the Engineering Reference Document up-to-date with technical details. This should include:
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
