"""Shared static and template plumbing: shared/templates is a fallback
template root, shared/static is reachable from each app's static folder."""
from pathlib import Path

from flask import Flask, render_template, render_template_string

from shared import web

ROOT = Path(__file__).resolve().parents[2]


def _fake_shared(tmp_path, monkeypatch, text):
    (tmp_path / 'shared').mkdir()
    (tmp_path / 'shared' / 'probe.html').write_text(text)
    monkeypatch.setattr(web, 'SHARED_TEMPLATES', tmp_path)


def test_install_shared_ui_resolves_shared_templates(tmp_path, monkeypatch):
    _fake_shared(tmp_path, monkeypatch, 'from shared')
    app = Flask(__name__)
    web.install_shared_ui(app)
    with app.test_request_context():
        assert render_template_string("{% include 'shared/probe.html' %}") == 'from shared'


def test_app_templates_win_over_shared(tmp_path, monkeypatch):
    _fake_shared(tmp_path, monkeypatch, 'from shared')
    app_templates = tmp_path / 'app_templates'
    (app_templates / 'shared').mkdir(parents=True)
    (app_templates / 'shared' / 'probe.html').write_text('from app')
    app = Flask(__name__, template_folder=str(app_templates))
    web.install_shared_ui(app)
    with app.test_request_context():
        assert render_template('shared/probe.html') == 'from app'


def test_plainly_serves_shared_static():
    from plainly import app_base
    resp = app_base.app.test_client().get('/static/shared/.gitkeep')
    assert resp.status_code == 200


def test_static_shared_is_symlink_to_shared_static():
    link = ROOT / 'plainly/frontend/static/shared'
    assert link.is_symlink()
    assert link.resolve() == (ROOT / 'shared/static').resolve()


def test_shared_assets_are_app_neutral():
    roots = [ROOT / 'shared/static', ROOT / 'shared/templates']
    for root in roots:
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix in ('.woff', '.woff2', '.ttf', '.otf'):
                continue
            text = path.read_text(errors='ignore').lower()
            assert 'plainly' not in text and 'distill' not in text, path
