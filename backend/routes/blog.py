"""Blog routes (page + API): index, post detail, list, single post.

Registered only when config.FEATURE_BLOG is True (see app_base.py) — same
pattern as auth_bp/progress_bp being registered only when FEATURE_AUTH is
True, so the routes return clean 404s (not 403s) when the feature is off.

Moved out of app_base.py as part of the blueprint split (2026-09 refactor).
"""
import logging

from flask import Blueprint, jsonify, render_template

from backend.routes import common

logger = logging.getLogger(__name__)

bp = Blueprint('blog', __name__)


@bp.route('/blog')
def blog_index():
    """Server-side rendering for blog index (SEO)"""
    db = common.db
    site_origin = common.site_origin

    meta_title = "Blog - Classic Literature Guides | Summra"
    meta_description = "Read our guides on classic literature, ESL learning, and book recommendations. Learn how to read classics as a non-native English speaker."
    canonical_url = f"{site_origin()}/blog"

    # Get all blog posts for SEO
    posts = db.get_all_blog_posts()

    # Schema.org structured data for Blog
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Blog",
        "name": "Summra Blog",
        "description": "Classic literature guides and reading tips for ESL learners"
    }

    # Build breadcrumbs
    breadcrumbs = common.build_breadcrumbs('blog')
    breadcrumb_schema = common.breadcrumbs_to_schema(breadcrumbs)

    combined_structured_data = [structured_data, breadcrumb_schema]

    initial_data = {
        'type': 'blog',
        'breadcrumbs': breadcrumbs
    }

    return render_template(
        'index.html',
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        og_type='website',
        structured_data=combined_structured_data,
        initial_data=initial_data
    )


@bp.route('/blog/<slug>')
def blog_post_page(slug):
    """Server-side rendering for blog post pages (SEO)"""
    db = common.db
    site_origin = common.site_origin

    post = db.get_blog_post_by_slug(slug)

    if not post:
        return render_template('index.html'), 404

    # Prepare meta tags
    meta_title = f"{post['title']} | Summra Blog"

    # Extract first 160 chars for description
    meta_description = post.get('excerpt', '')[:160] if post.get('excerpt') else post['title']

    canonical_url = f"{site_origin()}/blog/{slug}"

    # Schema.org structured data for BlogPosting
    structured_data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post['title'],
        "datePublished": post.get('published_date', post.get('created_at', '')),
        "author": {
            "@type": "Organization",
            "name": post.get('author', 'Summra Team')
        },
        "publisher": {
            "@type": "Organization",
            "name": "Summra"
        }
    }

    if post.get('excerpt'):
        structured_data["description"] = post['excerpt']

    # Build breadcrumbs
    breadcrumbs = common.build_breadcrumbs('blog-post', blog_post=post)
    breadcrumb_schema = common.breadcrumbs_to_schema(breadcrumbs)

    combined_structured_data = [structured_data, breadcrumb_schema]

    initial_data = {
        'type': 'blog-post',
        'slug': slug,
        'breadcrumbs': breadcrumbs
    }

    return render_template(
        'index.html',
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        og_type='article',
        structured_data=combined_structured_data,
        initial_data=initial_data
    )


@bp.route('/api/blog', methods=['GET'])
def get_all_blog_posts():
    """Get all blog posts (title, slug, excerpt, date only)"""
    db = common.db
    try:
        posts = db.get_all_blog_posts()
        return jsonify({
            'success': True,
            'posts': posts,
            'count': len(posts)
        })
    except Exception as e:
        logger.error(f"Error fetching blog posts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/blog/<slug>', methods=['GET'])
def get_blog_post(slug):
    """Get full blog post by slug"""
    db = common.db
    try:
        post = db.get_blog_post_by_slug(slug)
        if post:
            return jsonify({
                'success': True,
                'post': post
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Blog post not found'
            }), 404
    except Exception as e:
        logger.error(f"Error fetching blog post {slug}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
