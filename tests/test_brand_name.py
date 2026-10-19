"""The app's user-facing brand is "Plainly" (renamed from "Summra").

Code identifiers (SummraApp, SUMMRA_* env vars, the /summrabook URL prefix,
deploy unit names) intentionally keep the old name; only text a reader can
see — page titles, meta tags, the logo, the manifest — is checked here.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# "Summra" as a whole word inside a quoted string literal — i.e. text that
# ends up on screen. Identifiers like booksOnSummra / SummraApp don't match.
QUOTED_BRAND = re.compile(r"""[`'"][^`'"\n]*\bSummra\b[^`'"\n]*[`'"]""")


@pytest.fixture
def client(test_db_path, monkeypatch):
    from backend import app_base, models
    from backend.routes import common
    db = models.Database(db_path=test_db_path)
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


def test_home_page_shows_plainly(client):
    body = client.get('/').get_data(as_text=True)
    assert '<title>Plainly — Read the Classics in Plain English</title>' in body
    assert '<h1 class="logo">Plainly</h1>' in body
    assert 'og:site_name" content="Plainly"' in body
    assert not re.search(r'\bSummra\b', body)


def test_manifest_and_robots_use_plainly(client):
    manifest = client.get('/manifest.json').get_json()
    assert manifest['short_name'] == 'Plainly'
    assert manifest['name'].startswith('Plainly')
    robots = client.get('/robots.txt').get_data(as_text=True)
    assert not re.search(r'\bSummra\b', robots)


@pytest.mark.parametrize('path', sorted(
    [p for p in (ROOT / 'frontend/static/js').rglob('*.js') if p.name != 'app.min.js']
    + list((ROOT / 'backend/routes').glob('*.py'))
    + [ROOT / 'backend/models.py']
), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_user_facing_summra_strings(path):
    hits = [line.strip() for line in path.read_text().splitlines()
            if QUOTED_BRAND.search(line)]
    assert hits == []


def test_built_bundle_has_no_summra_strings():
    bundle = (ROOT / 'frontend/static/js/app.min.js').read_text()
    assert not QUOTED_BRAND.search(bundle), 'rebuild with `npm run build`'
