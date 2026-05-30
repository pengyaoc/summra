"""Tests for the site footer.

The footer must:
1. On non-chapter pages, communicate the site's headline value prop
   (Plain English rewrites of public-domain classics) rather than the
   generic "summaries" framing the trim commit (ccea8ed) removed from
   the rest of the homepage.
2. Be absent from server-rendered chapter pages — chapter pages are a
   focused reading view and shouldn't carry a marketing footer.
"""

import pytest
from flask import render_template


@pytest.fixture
def client():
    """Flask test client. Imported lazily so the app boots inside the test."""
    import app_base
    return app_base.app.test_client()


@pytest.fixture
def app_ctx():
    """Request context — needed because index.html calls url_for() for static assets."""
    import app_base
    with app_base.app.test_request_context('/'):
        yield app_base.app


def test_footer_on_homepage_leads_with_plain_english(client):
    resp = client.get('/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Footer must exist on the homepage.
    assert '<footer' in html, 'homepage should render a <footer>'

    # Headline value prop, not the old "summaries" framing.
    assert 'Plain English' in html.split('<footer', 1)[1], \
        'footer should lead with the Plain English value prop'

    # The old generic copy must be gone — these strings were the symptom
    # the user asked us to fix.
    footer_html = '<footer' + html.split('<footer', 1)[1].split('</footer>', 1)[0]
    assert 'Free summaries and full text of classic literature' not in footer_html, \
        'old generic tagline must be removed from the footer'
    assert 'Comprehensive book summaries, chapter-by-chapter analysis' not in footer_html, \
        'old generic subline must be removed from the footer'

    # "public-domain" / "public domain" is a legal nicety the user does not
    # want in the footer copy — keep it out.
    assert 'public-domain' not in footer_html.lower(), \
        '"public-domain" wording should not appear in the footer'
    assert 'public domain' not in footer_html.lower(), \
        '"public domain" wording should not appear in the footer'

    # "every classic" overclaims coverage — we have a curated library, not
    # the entire canon. Keep it out of marketing copy.
    assert 'every classic' not in footer_html.lower(), \
        '"every classic" overclaims coverage and should not appear in the footer'


def test_footer_absent_on_chapter_page(app_ctx):
    # Render the template directly with a chapter initial_data payload,
    # mirroring what backend/app_base.py:572 passes for /book/<slug>/chapter/<n>.
    initial_data = {
        'type': 'chapter',
        'book': {'id': 1, 'title': 'Test Book', 'author': 'Test Author', 'slug': 'test-book'},
        'chapter_number': 1,
    }
    html = render_template('index.html', initial_data=initial_data)

    assert '<footer' not in html, \
        'chapter pages should not render a <footer> (focused reading view)'


def test_footer_present_on_book_summary_page(app_ctx):
    # Sanity check: non-chapter typed pages still get the footer.
    initial_data = {
        'type': 'book-summary',
        'book': {'id': 1, 'title': 'Test Book', 'author': 'Test Author', 'slug': 'test-book'},
    }
    html = render_template('index.html', initial_data=initial_data)

    assert '<footer' in html, 'book-summary pages should still render the footer'
