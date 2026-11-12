# Tests

The tests mirror the code. Rules (TDD, coverage required for each change) are in `../CLAUDE.md`.

| Folder | What it covers | Run |
|---|---|---|
| `shared/` | The platform: reader index and routes, block parity (Python vs JS), auth/pchauth, progress, Kindle, audio, web basics, and the layering rule (`test_layering.py`: `shared/` never imports an app) | `pytest tests/shared` |
| `plainly/` | Plainly: ingestion and chapter detection, Plain English tools, models, routes, pages, deploy files | `pytest tests/plainly` |
| `distill/` | Distill: book format, import, pages, Kindle, audio, pairing, `deploy_code` / `deploy_db` / `db_patch` | `pytest tests/distill` |
| `test_layering_names.py` | Repo-wide guard against stale paths (old `backend/`, top-level `scripts/`, old command forms in docs) | `pytest tests/test_layering_names.py` |
| `js/` | Node unit tests for reader JS (modes, state, blocks, routing) | `node --test tests/js/*.test.mjs` |
| `e2e/` | Playwright harness against a running server: `smoke.mjs` and the reader scripts for Plainly, `distill.mjs` for Distill | see [`e2e/README.md`](e2e/README.md) |
| `fixtures/` | Sample databases, LLM responses, audio and illustrations used by the suites | — |

```bash
venv/bin/python -m pytest tests/ -v
```

The whole pytest suite runs with no API keys and no content database. CI runs it on every push.

Markers (`pytest.ini`): `slow` and `content` are deselected by default. `-m content` audits the locally provisioned Plainly content DB, for example `pytest tests/plainly/test_home_redesign.py -m content`.

Shared fixtures live in `tests/conftest.py` and `tests/distill/conftest.py`.
