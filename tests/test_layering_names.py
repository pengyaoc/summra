# Repo-wide stale-name guard: nothing may still refer to the old `backend` package,
# or to `scripts` / `frontend/static` at their pre-move top-level locations.
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SKIP = {'venv', 'node_modules', '.git', 'archive', 'data', '.claude'}
EXTS = ('*.py', '*.mjs', '*.sh', '*.toml', '*.service', '*.json', '*.ini', '*.yml', '*.yaml')


def _hits(pat, outside_plainly=False):
    out = []
    for ext in EXTS:
        for p in ROOT.rglob(ext):
            rel = p.relative_to(ROOT)
            if SKIP & set(rel.parts) or p.name == 'test_layering_names.py':
                continue
            if outside_plainly and rel.parts[0] == 'plainly':
                continue
            if pat.search(p.read_text(errors='ignore')):
                out.append(str(rel))
    return out


def test_no_stale_backend_references():
    pat = re.compile(r"\bfrom backend\b|\bimport backend\b|['\"]backend\.|(?<!summra/)\bbackend/|backend\.app_prod|backend\.app\b")
    assert _hits(pat) == []


def test_no_stale_scripts_or_frontend_references():
    # `scripts` now lives at plainly/scripts, so a bare `scripts.` import is stale.
    # Files inside plainly/ may say `frontend/static` (it is relative to plainly/).
    pat = re.compile(r"\bfrom scripts\b|['\"]scripts\.|(?<!plainly/)frontend/static")
    assert _hits(pat, outside_plainly=True) == []
