# Repo-wide stale-name guard: nothing may still refer to the old `backend` package.
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SKIP = {'venv', 'node_modules', '.git', 'archive', 'data', '.claude'}

def test_no_stale_backend_references():
    pat = re.compile(r"\bfrom backend\b|\bimport backend\b|['\"]backend\.|backend/app|backend\.app_prod|backend\.app\b")
    hits = [str(p.relative_to(ROOT)) for ext in ('*.py', '*.mjs', '*.sh', '*.toml', '*.service', '*.json', '*.ini')
            for p in ROOT.rglob(ext)
            if not SKIP & set(p.relative_to(ROOT).parts) and pat.search(p.read_text(errors='ignore'))
            and p.name != 'test_layering_names.py']
    assert hits == []
