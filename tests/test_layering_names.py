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
    # Also catches path built from split fragments: join(..., "frontend", "static").
    pat = re.compile(r"\bfrom scripts\b|['\"]scripts\.|(?<!plainly/)frontend/static"
                     r"|(?<!plainly['\"], )['\"]frontend['\"],\s*['\"]static['\"]")
    assert _hits(pat, outside_plainly=True) == []


def test_no_stale_command_paths_in_agent_and_doc_files():
    # Runnable commands in agent instructions and live docs must use the
    # `python -m plainly.scripts...` form. Dated history (archive, superpowers
    # plans) is left alone.
    pat = re.compile(r"PYTHONPATH=backend|(?<![\w./-])scripts/(content|audits|tts|ingest|maintenance)/\S+\.py"
                     r"|python3? scripts/")
    files = list((ROOT / '.claude' / 'agents').glob('*.md')) + list((ROOT / 'docs').glob('*.md'))
    files += list((ROOT / 'docs' / 'tts').glob('*.md'))
    files += [ROOT / 'plainly' / 'scripts' / 'content' / 'README_MODERN_ENGLISH.md',
              ROOT / 'plainly' / 'frontend' / 'static' / 'js' / 'README.md']
    bad = [str(p.relative_to(ROOT)) for p in files if p.exists() and pat.search(p.read_text(errors='ignore'))]
    assert bad == []
