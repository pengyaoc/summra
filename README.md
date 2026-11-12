# Summra

**Summra is a codename for a small reading platform and the two apps built on it.** The platform is the reader, progress sync, Kindle e-ink mode, chapter audio and sign-in. The apps bring their own content and pages.

| | What it is | Audience | Code | Local port |
|---|---|---|---|---|
| **Plainly** | Public-domain classics with a sentence-by-sentence Plain English rewrite, summaries, illustrations and audio | Public | [`plainly/`](plainly/README.md) | 5001 |
| **Distill** | Private chapter-by-chapter summaries of books the owner reads | Owner only (sign-in required) | [`distill/`](distill/README.md) | 5003 |
| **Shared platform** | Reader, progress, Kindle mode, audio, sign-in, web basics | Used by both apps | [`shared/`](shared/README.md) | — |

```
          ┌──────────────────────────┐   ┌──────────────────────────┐
          │         Plainly          │   │         Distill          │
          │  classics · Plain English│   │  private book summaries  │
          │  ingestion (Gemini)      │   │  book-folder import      │
          │  data/database.db        │   │  data/distill.db         │
          └────────────┬─────────────┘   └────────────┬─────────────┘
                       │  ReaderConfig · audio_app ·  │
                       │  blueprints · static symlink │
          ┌────────────┴──────────────────────────────┴─────────────┐
          │                     shared/ platform                     │
          │  reader (index, API, web + Kindle render) · progress     │
          │  kindle · audio (record + play) · auth (pchauth) · web   │
          └──────────────────────────────────────────────────────────┘
```

**The one rule:** `shared/` never imports `plainly` or `distill`. Each app plugs in by describing itself: a `ReaderConfig` (`<app>/reader_config.py`), an audio description (`<app>/audio_app.py`) and its own Flask app factory (`<app>/app_base.py`). The shared reader, progress and audio code is never copied into an app.

## Repository map

```
summra/
├── shared/      The platform. Python packages + shared/static (CSS, JS, fonts) + shared/templates
├── plainly/     Plainly app: Flask app, routes, frontend/, scripts/ (ingestion, Plain English, audits)
├── distill/     Distill app: Flask app, routes, templates/, static/, scripts/ (import, deploy)
├── tests/       Mirrors the code: tests/shared, tests/plainly, tests/distill, tests/e2e (Playwright)
├── deploy/      gunicorn_config.py + deploy/plainly, deploy/distill, deploy/kindle (launchers)
├── docs/        shared/, plainly/, distill/ (each with PRD.md + ERD.md), superpowers/ (specs, plans), archive/
├── skills/      Claude Code skills that feed Distill (distill-publish)
├── data/        Local databases and source texts (databases and media are gitignored)
├── CLAUDE.md    Working rules for agents (TDD, docs, worktrees) with links to the runbooks
└── WORK_LOG.md  Running log of work done
```

Each app is a Python package in one editable install (`pip install -e .`). `pyproject.toml` exposes `shared`, `plainly` and `distill`.

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r plainly/requirements.txt -r distill/requirements.txt
pip install -e .
cp .env.example .env            # Plainly ingestion needs GEMINI_API_KEY
```

Run either app (or both — they use different ports and databases):

```bash
python plainly/app.py                        # Plainly → http://localhost:5001
```

```bash
PORT=5003 python -m distill.app              # Distill → http://localhost:5003
```

Neither database is in Git. Plainly needs `data/database.db` (restore one, or ingest a book); Distill needs `data/distill.db` (import a book folder). See each app's README.

## Tests

```bash
venv/bin/python -m pytest tests/ -v          # all three packages; no API keys needed
```

The e2e harness in `tests/e2e/` drives headless Chromium against a running server: `smoke.mjs` and the reader scripts for Plainly, `distill.mjs` for Distill (desktop, mobile and Kindle passes). Any change under `shared/` must keep both apps green. `CLAUDE.md` lists the scripts to run. CI (`.github/workflows/ci.yml`) runs pytest and checks that Plainly's JS bundle is fresh.

## Deployment

Both apps run on one VM, each as its own gunicorn service behind Apache, under `/plainly` and `/distill`. Apache handles TLS and Google sign-in; Distill requires it, Plainly makes it optional.

- Overview and Plainly: [`deploy/README.md`](deploy/README.md) and [`deploy/plainly/`](deploy/plainly/), plus [`deploy/plainly/RUNBOOK.md`](deploy/plainly/RUNBOOK.md).
- Distill: [`deploy/distill/`](deploy/distill/). Use `python -m distill.scripts.deploy_code` for code and `python -m distill.scripts.deploy_db` for content.
- Kindle launchers: [`deploy/kindle/README.md`](deploy/kindle/README.md).

Generated audio and images are deployment data and are kept out of Git, including history. See [generated media](deploy/README.md#generated-media-and-history-rewrite) before provisioning a fresh clone.

## Documentation

| Doc | Covers |
|---|---|
| `docs/{shared,plainly,distill}/PRD.md` | Product behaviour, one file per part ([index](docs/PRD.md)) |
| `docs/{shared,plainly,distill}/ERD.md` | Architecture, schema and implementation details, one file per part ([index](docs/ERD.md)). Start at [shared → Repository layout](docs/shared/ERD.md#repository-layout-post-repo-split-2026-10-24) |
| [`docs/plainly/agent_plain_english_workflow.md`](docs/plainly/agent_plain_english_workflow.md) | How Plainly's Plain English text is written and checked |
| [`docs/plainly/`](docs/plainly/) | Also: ingestion workflow, Plain English workflows, checklist and learnings, marketing |
| [`docs/superpowers/`](docs/superpowers/) | Dated design specs and implementation plans (Distill, shared audio, redesign) |
| [`docs/archive/`](docs/archive/) | Superseded docs, kept for history |

## Names

"Summra" was the first app's name. The public app is now **Plainly**, and Summra is the codename for the repository and platform. Some internal identifiers keep the old name on purpose: the repo, the `SUMMRA_*` env vars, `data/summra.db` (Plainly's user database) and deploy file names.

## License

For personal and educational use. Source texts must be in the public domain, or you must hold the rights to them.
