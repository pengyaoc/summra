"""The favicon is a flat SVG (open book with a gold spark on the burgundy
accent tile), with PNG fallbacks for browsers and home screens that don't take SVG icons."""
import pytest


@pytest.fixture
def client():
    from backend import app_base
    return app_base.app.test_client()


def test_page_links_svg_favicon(client):
    body = client.get('/').get_data(as_text=True)
    assert 'rel="icon" type="image/svg+xml" href="/static/images/icon.svg?v=' in body


def test_svg_favicon_is_served(client):
    resp = client.get('/static/images/icon.svg')
    assert resp.status_code == 200
    svg = resp.get_data(as_text=True)
    assert svg.lstrip().startswith('<svg')
    assert '#8A2E2E' in svg  # brand accent tile
    assert "#D9A441" in svg  # gold spark above the book


def test_svg_favicon_respects_url_prefix(client):
    body = client.get('/', headers={'X-Forwarded-Prefix': '/summrabook'}).get_data(as_text=True)
    assert 'href="/summrabook/static/images/icon.svg?v=' in body
