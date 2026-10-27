# Codex Entry Point

Follow the canonical cross-project policy in [~/.agents/AGENTS.md](/Users/pengyao/.agents/AGENTS.md).

## Required documentation before committing

- After every coding update, update [docs/ERD.md](docs/ERD.md), [docs/PRD.md](docs/PRD.md), and [WORK_LOG.md](WORK_LOG.md) before committing.
- Keep the ERD aligned with the implemented architecture, data model and technical behavior; keep the PRD aligned with product behavior and requirements; record the changes, validation and deployment status in the worklog.
- If a coding update has no architectural or product impact, explicitly record that assessment in the relevant document rather than skipping it.
- Before committing, verify that all three documents reflect the final changes and include their updates in the commit. Do not defer documentation until after committing or wait for the user to request it.

## Plain English generation

Use the Codex subagent workflow in [docs/agent_plain_english_workflow.md](docs/agent_plain_english_workflow.md) for full-book Plain English requests.

- Writers: GPT 6.1 Sol (`gpt-6.1-sol`), **low** reasoning effort.
- Verification: separate, fresh GPT 6.1 Sol subagents, **medium** reasoning effort.
- Spawn with `fork_turns="none"` and explicit role instructions and file assignments. Respect available concurrency; never have writers verify their own work.
- Preserve all paragraphs and meaning, pass the mechanical gate, independently review every pair, then apply and verify the reader.
- Use Codex subagents when running under Codex. Claude retains its existing Sonnet subagent configuration. Do not use Gemini unless explicitly requested.
