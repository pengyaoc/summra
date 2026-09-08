"""System/infra routes: robots.txt, PWA manifest, sitemap.

Moved out of app_base.py as part of the blueprint split (2026-09 refactor).
"""
from datetime import datetime
from flask import Blueprint, current_app, render_template

from backend.routes import common

bp = Blueprint('system', __name__)


@bp.route('/robots.txt')
def robots():
    """Render robots.txt with the live URL prefix and origin baked in, so its
    Allow/Disallow rules and Sitemap line stay correct under any deployment."""
    response = current_app.make_response(render_template('robots.txt'))
    response.headers['Content-Type'] = 'text/plain'
    return response


@bp.route('/manifest.json')
def manifest():
    """Render the PWA manifest with the live URL prefix baked into start_url,
    scope, and icon paths — required so its `scope` never overreaches beyond
    this app's own subpath when reverse-proxied alongside another site."""
    response = current_app.make_response(render_template('manifest.json'))
    response.headers['Content-Type'] = 'application/manifest+json'
    return response


@bp.route('/sitemap.xml')
def sitemap():
    """Generate dynamic XML sitemap for SEO"""
    db = common.db
    config = common.config
    site_origin = common.site_origin

    pages = []

    # Home page
    pages.append({
        'loc': f'{site_origin()}/',
        'lastmod': datetime.now().strftime('%Y-%m-%d'),
        'changefreq': 'daily',
        'priority': '1.0'
    })

    # All books pages
    books = db.get_all_books()
    for book in books:
        slug = book.get('slug')
        if not slug:
            continue

        # Book detail page
        pages.append({
            'loc': f'{site_origin()}/books/{slug}',
            'lastmod': book.get('updated_at', datetime.now().strftime('%Y-%m-%d')),
            'changefreq': 'weekly',
            'priority': '0.8'
        })

    # Category pages
    categories = db.get_all_categories()
    for category in categories:
        pages.append({
            'loc': f'{site_origin()}/categories/{category["id"]}',
            'changefreq': 'weekly',
            'priority': '0.7'
        })

    # All books and categories listing pages
    pages.append({
        'loc': f'{site_origin()}/books',
        'changefreq': 'daily',
        'priority': '0.9'
    })

    pages.append({
        'loc': f'{site_origin()}/categories',
        'changefreq': 'weekly',
        'priority': '0.8'
    })

    # Blog URLs only when the blog feature is enabled. Listing blog URLs in
    # the sitemap while routes 404 would actively hurt SEO.
    if config.FEATURE_BLOG:
        pages.append({
            'loc': f'{site_origin()}/blog',
            'changefreq': 'weekly',
            'priority': '0.6'
        })
        for post in db.get_all_blog_posts():
            slug = post.get('slug')
            if not slug:
                continue
            pages.append({
                'loc': f'{site_origin()}/blog/{slug}',
                'lastmod': post.get('published_date') or post.get('created_at'),
                'changefreq': 'monthly',
                'priority': '0.5'
            })

    sitemap_xml = render_template('sitemap.xml', pages=pages)
    response = current_app.make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response
