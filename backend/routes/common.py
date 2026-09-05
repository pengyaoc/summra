"""Shared context and helpers for the route blueprints in backend/routes/.

`db` and `config` are set by app_base.py immediately after the Flask app,
database, and config are created — before any blueprint using this module
is registered. This mirrors the existing pattern in auth_routes.py /
progress_routes.py (`user_db = None`, set externally), and avoids what
would otherwise be a circular import: app_base.py must import these
blueprint modules to register them, so the blueprint modules can't import
app_base.py back to reach `db`/`config` at their own import time.
"""
from flask import request

# Set by app_base.py.
db = None
config = None


def site_origin() -> str:
    """Scheme + host + base path, for absolute URLs (sitemap, canonical links,
    OG tags, JSON-LD). Derived from the live request via PrefixMiddleware so
    it's correct under any deployment (root domain, /summrabook proxy, local
    dev) without hardcoding a domain.
    """
    return request.url_root.rstrip('/')


def author_name_to_slug(name):
    """Convert author name to lowercase-hyphen slug format.

    Examples:
        "H. G. Wells" -> "h-g-wells"
        "Jack London" -> "jack-london"
        "Charles Dickens" -> "charles-dickens"
    """
    import re
    # Remove special characters, convert to lowercase, replace spaces with hyphens
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)  # Remove non-alphanumeric except spaces and hyphens
    slug = re.sub(r'\s+', '-', slug)  # Replace spaces with hyphens
    slug = re.sub(r'-+', '-', slug)  # Replace multiple hyphens with single hyphen
    slug = slug.strip('-')  # Remove leading/trailing hyphens
    return slug


def slug_to_author_name(slug):
    """Convert lowercase-hyphen slug back to author name for database lookup.

    This searches the database for an author whose slugified name matches the slug.
    Returns the actual author name from the database or None if not found.
    """
    # Get all authors and find match
    authors = db.get_all_authors()
    for author in authors:
        if author_name_to_slug(author['name']) == slug:
            return author['name']
    return None


def build_breadcrumbs(page_type, **kwargs):
    """
    Build breadcrumb data for SEO and navigation.

    Returns list of breadcrumb items with:
    - name: Display text
    - url: Relative URL
    - position: Position in breadcrumb trail (starts at 1)
    """
    breadcrumbs = [
        {'name': 'Home', 'url': '/', 'position': 1}
    ]

    if page_type == 'categories':
        breadcrumbs.append({'name': 'Categories', 'url': '/categories', 'position': 2})

    elif page_type == 'category':
        category = kwargs.get('category')
        breadcrumbs.append({'name': 'Categories', 'url': '/categories', 'position': 2})
        if category:
            breadcrumbs.append({
                'name': category['name'],
                'url': f"/categories/{category['id']}",
                'position': 3
            })

    elif page_type == 'all_books':
        breadcrumbs.append({'name': 'All Books', 'url': '/all-books', 'position': 2})

    elif page_type == 'book':
        book = kwargs.get('book')
        if book:
            breadcrumbs.append({'name': 'All Books', 'url': '/all-books', 'position': 2})
            breadcrumbs.append({
                'name': book['title'],
                'url': f"/books/{book['slug']}",
                'position': 3
            })

    elif page_type == 'book_summary':
        book = kwargs.get('book')
        if book:
            breadcrumbs.append({'name': 'All Books', 'url': '/all-books', 'position': 2})
            breadcrumbs.append({
                'name': book['title'],
                'url': f"/books/{book['slug']}",
                'position': 3
            })
            breadcrumbs.append({
                'name': 'Summary',
                'url': f"/books/{book['slug']}/summary",
                'position': 4
            })

    elif page_type == 'chapter':
        book = kwargs.get('book')
        chapter = kwargs.get('chapter')
        if book:
            breadcrumbs.append({'name': 'All Books', 'url': '/all-books', 'position': 2})
            breadcrumbs.append({
                'name': book['title'],
                'url': f"/books/{book['slug']}",
                'position': 3
            })
            if chapter:
                # Use chapter title if available, otherwise fall back to chapter number
                chapter_title = chapter.get('chapter_title')
                chapter_name = (
                    f"{chapter['chapter_number']}. {chapter_title}"
                    if chapter_title
                    else f"Chapter {chapter['chapter_number']}"
                )
                breadcrumbs.append({
                    'name': chapter_name,
                    'url': f"/books/{book['slug']}/chapters/{chapter['chapter_number']}",
                    'position': 4
                })

    elif page_type == 'author':
        author = kwargs.get('author')
        if author:
            author_name = author.get('name', 'Unknown Author')
            author_slug = author_name_to_slug(author_name)
            breadcrumbs.append({
                'name': author_name,
                'url': f"/authors/{author_slug}",
                'position': 2
            })

    elif page_type == 'blog':
        breadcrumbs.append({'name': 'Blog', 'url': '/blog', 'position': 2})

    elif page_type == 'blog-post':
        blog_post = kwargs.get('blog_post')
        breadcrumbs.append({'name': 'Blog', 'url': '/blog', 'position': 2})
        if blog_post:
            breadcrumbs.append({
                'name': blog_post['title'],
                'url': f"/blog/{blog_post['slug']}",
                'position': 3
            })

    return breadcrumbs


def breadcrumbs_to_schema(breadcrumbs):
    """Convert breadcrumbs list to Schema.org BreadcrumbList JSON-LD"""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": crumb['position'],
                "name": crumb['name'],
                "item": f"{site_origin()}{crumb['url']}" if crumb['position'] < len(breadcrumbs) else None
            }
            for crumb in breadcrumbs
        ]
    }
