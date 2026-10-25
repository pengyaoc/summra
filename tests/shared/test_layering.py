import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ('plainly', 'distill', 'backend', 'scripts')


def _imports(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


def test_shared_package_exists():
    assert (ROOT / 'shared' / '__init__.py').is_file()


def test_shared_imports_no_app_code():
    bad = [(str(p.relative_to(ROOT)), m) for p in (ROOT / 'shared').rglob('*.py')
           for m in _imports(p) if m.split('.')[0] in FORBIDDEN]
    assert bad == []
