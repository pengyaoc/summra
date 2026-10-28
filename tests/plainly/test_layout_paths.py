import re
from pathlib import Path

from plainly import config

ROOT = Path(__file__).resolve().parents[2]


def test_base_dir_is_repo_root():
    assert config.BASE_DIR == ROOT and (ROOT / 'pyproject.toml').is_file()


def test_covers_live_in_plainly_frontend():
    assert config.COVERS_DIR == ROOT / 'plainly' / 'frontend' / 'static' / 'covers'
    # Generated media is restored separately; a fresh clone has no covers yet.
    assert config.COVERS_DIR.parent.is_dir()


def test_apache_static_alias_matches_flask_static_dir():
    conf = (ROOT / 'deploy' / 'apache' / 'summra.conf').read_text()
    alias = re.search(r'Alias \$\{SUMMRA_PREFIX\}/static/ (\S+)', conf)[1]
    assert alias == '/opt/summra/plainly/frontend/static/'
