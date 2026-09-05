"""Tests for reverse-proxy URL-prefix support (PrefixMiddleware + base_path).

Bug this guards against:
Deploying Summra under a path prefix (e.g. Apache's
`ProxyPass /summrabook/ http://127.0.0.1:5001/`, which strips the prefix
before forwarding) requires every generated URL — url_for() links, the
service worker, the PWA manifest, robots.txt, canonical/OG tags, and the
window.APP_BASE_PATH the frontend JS reads — to include that prefix.
Without PrefixMiddleware reading the proxy's X-Forwarded-Prefix header and
applying it as SCRIPT_NAME, url_for() has no way to know it isn't being
served from the domain root.

These tests cover both the default root deployment (no header — must be
byte-for-byte unaffected) and a proxied deployment (header present).
"""
import pytest


@pytest.fixture
def client():
    from backend import app_base
    return app_base.app.test_client()


def test_root_deployment_is_unaffected(client):
    """No X-Forwarded-Prefix header (today's production) must keep generating
    unprefixed URLs — this is the backward-compatibility guarantee."""
    resp = client.get('/')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'window.APP_BASE_PATH = "";' in body
    assert 'href="/discover"' in body
    assert 'href="//discover"' not in body


def test_prefixed_deployment_injects_base_path(client):
    """With X-Forwarded-Prefix set (simulating the Apache proxy), the base
    path must reach the frontend via window.APP_BASE_PATH and every
    root-relative nav link."""
    resp = client.get('/', headers={'X-Forwarded-Prefix': '/summrabook'})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'window.APP_BASE_PATH = "/summrabook";' in body
    assert 'href="/summrabook/discover"' in body
    assert 'href="/summrabook/books"' in body
    assert 'href="/summrabook/categories"' in body


def test_prefixed_deployment_routes_still_resolve(client):
    """PrefixMiddleware must strip the prefix from PATH_INFO so Flask's router
    still matches the real route, not 404."""
    resp = client.get('/summrabook/discover', headers={'X-Forwarded-Prefix': '/summrabook'})
    assert resp.status_code == 200


def test_prefixed_static_asset_urls(client):
    """url_for('static', ...) must include the prefix (CSS/JS/icon links)."""
    resp = client.get('/', headers={'X-Forwarded-Prefix': '/summrabook'})
    body = resp.get_data(as_text=True)
    assert '/summrabook/static/css/style.css' in body


def test_service_worker_scope_matches_prefix(client):
    """Service-Worker-Allowed and the precached '/' entry must both live
    under the deploy prefix, or the browser will refuse/scope it wrong."""
    resp = client.get('/service-worker.js', headers={'X-Forwarded-Prefix': '/summrabook'})
    assert resp.status_code == 200
    assert resp.headers.get('Service-Worker-Allowed') == '/summrabook/'
    body = resp.get_data(as_text=True)
    assert "BASE_PATH = \"/summrabook\";" in body


def test_service_worker_precache_revision_is_not_the_old_hardcoded_literal(client):
    """The precached '/' and '/offline' entries' revision must be a real
    content hash (backend/routes/system.py's _precache_revision()), not the
    '1.0.1' literal that was never bumped — meaning Workbox never noticed
    an index.html/offline.html change and refetched the precached shell."""
    resp = client.get('/service-worker.js')
    body = resp.get_data(as_text=True)
    assert "revision: '1.0.1'" not in body
    import re
    revisions = re.findall(r"revision: '(\d+)'", body)
    assert len(revisions) == 2, f"expected 2 precache entries, found: {revisions}"
    assert revisions[0] == revisions[1], "both precached entries must share one revision"
    assert revisions[0] != '0', (
        "revision is '0' — _precache_revision() likely read zero bytes "
        "(e.g. resolved the wrong directory) rather than hashing real "
        "template content"
    )


def test_manifest_scope_matches_prefix(client):
    """manifest.json's scope must not overreach beyond this app's own
    subpath — otherwise it would try to claim the whole domain, conflicting
    with whatever else (e.g. WordPress) lives at the root."""
    resp = client.get('/manifest.json', headers={'X-Forwarded-Prefix': '/summrabook'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['start_url'] == '/summrabook/'
    assert data['scope'] == '/summrabook/'
    # icon src is cache-busted with asset_v() (?v=<content-hash>), so check
    # the prefix rather than an exact match.
    assert data['icons'][0]['src'].startswith('/summrabook/static/images/icon-32.png?v=')


def test_robots_txt_reflects_prefix_and_origin(client):
    """robots.txt Allow/Disallow rules and the Sitemap line must match the
    real deployed paths, not the domain root."""
    resp = client.get('/robots.txt', headers={
        'X-Forwarded-Prefix': '/summrabook',
        'Host': 'pengyaochen.com',
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Allow: /summrabook/' in body
    assert 'Disallow: /summrabook/api/' in body
    assert 'Sitemap: http://pengyaochen.com/summrabook/sitemap.xml' in body


def test_sitemap_urls_use_live_origin_not_hardcoded_domain(client):
    """Regression guard: sitemap.xml used to hardcode https://summra.com,
    which was never this app's real domain. URLs must be derived from the
    live request instead."""
    resp = client.get('/sitemap.xml', headers={
        'X-Forwarded-Prefix': '/summrabook',
        'Host': 'pengyaochen.com',
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'summra.com' not in body
    assert '<loc>http://pengyaochen.com/summrabook/</loc>' in body
