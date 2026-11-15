# Codex Entry Point

Follow the canonical cross-project policy in [~/.agents/AGENTS.md](/Users/pengyao/.agents/AGENTS.md).

## Required documentation before committing

- After every coding update, update the ERD and PRD for the part you changed (`docs/shared/`, `docs/plainly/` or `docs/distill/`, each with `ERD.md` and `PRD.md`; `docs/ERD.md` and `docs/PRD.md` are indexes) and [WORK_LOG.md](WORK_LOG.md) before committing.
- Keep the ERD aligned with the implemented architecture, data model and technical behavior; keep the PRD aligned with product behavior and requirements; record the changes, validation and deployment status in the worklog.
- If a coding update has no architectural or product impact, explicitly record that assessment in the relevant document rather than skipping it.
- Before committing, verify that all three documents reflect the final changes and include their updates in the commit. Do not defer documentation until after committing or wait for the user to request it.

## Reader content: tables and scrolling

**Tables must split into pages. Nothing in the reader view may scroll.** The reader turns pages by swipe, tap and keys; a nested scroll box (`overflow: auto` / `scroll`, a fixed `max-height` with scrolling, a sticky header inside a scroller) takes the swipe on mobile web and traps the reader on that page.
- Add a table to reader content only as a structured `table` block (header + rows of plain cell text; `presentation: "grid"` for a research grid). Never raw HTML, an image of a table, or one cell holding a whole table.
- The paginator splits a table between its body rows and repeats the header row on each continuation page (`splitTableToFit` in `shared/static/js/pagination.js`). A single row taller than a page cannot split, so keep cells short.
- Wide tables wrap their cells to the page width. Never add a horizontal scroller.
- Never add `overflow: auto/scroll` to anything inside the reader page, and never exempt an element from page-turn gestures. `tests/e2e/distill_tables.mjs` (375×667, NVIDIA research report) guards this.

## Plain English generation

Use the Codex subagent workflow in [docs/plainly/agent_plain_english_workflow.md](docs/plainly/agent_plain_english_workflow.md) for full-book Plain English requests.

- Writers: GPT 6.1 Sol (`gpt-6.1-sol`), **low** reasoning effort.
- Verification: separate, fresh GPT 6.1 Sol subagents, **medium** reasoning effort.
- Spawn with `fork_turns="none"` and explicit role instructions and file assignments. Respect available concurrency; never have writers verify their own work.
- Preserve all paragraphs and meaning, pass the mechanical gate, independently review every pair, then apply and verify the reader.
- Use Codex subagents when running under Codex. Claude retains its existing Sonnet subagent configuration. Do not use Gemini unless explicitly requested.
