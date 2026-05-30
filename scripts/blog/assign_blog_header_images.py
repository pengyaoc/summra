#!/usr/bin/env python3
"""
Assign header images from Unsplash to blog posts.

This script searches Unsplash for relevant images based on blog post titles/topics
and updates the blog_posts table with header_image_url.

Usage:
    python scripts/blog/assign_blog_header_images.py             # Assign to all posts missing images
    python scripts/blog/assign_blog_header_images.py --slug SLUG # Assign to specific post
    python scripts/blog/assign_blog_header_images.py --force     # Re-assign to all posts
"""

import sys
import os
import argparse
import requests
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

import config
from models import Database

def search_unsplash(query, per_page=1):
    """
    Search Unsplash for images matching the query.

    Args:
        query: Search query string
        per_page: Number of results to return (default: 1)

    Returns:
        List of image dictionaries with 'url', 'photographer', 'photographer_url'
    """
    if not config.UNSPLASH_ACCESS_KEY:
        print("ERROR: UNSPLASH_ACCESS_KEY not set in environment")
        print("Please set UNSPLASH_ACCESS_KEY in your .env file")
        print("\nTo get an Unsplash API key:")
        print("1. Go to https://unsplash.com/developers")
        print("2. Register as a developer")
        print("3. Create a new application")
        print("4. Copy the 'Access Key' to your .env file as UNSPLASH_ACCESS_KEY=your_key_here")
        sys.exit(1)

    url = "https://api.unsplash.com/search/photos"
    headers = {
        "Authorization": f"Client-ID {config.UNSPLASH_ACCESS_KEY}"
    }
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": "landscape"  # Blog headers look better in landscape
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        results = []
        for photo in data.get('results', []):
            results.append({
                'url': photo['urls']['regular'],  # Regular size (1080px width)
                'thumb_url': photo['urls']['small'],  # Small size for thumbnails
                'photographer': photo['user']['name'],
                'photographer_url': photo['user']['links']['html'],
                'description': photo.get('description', '')
            })

        return results

    except requests.exceptions.RequestException as e:
        print(f"Error searching Unsplash: {e}")
        return []


def generate_search_query(title, slug):
    """
    Generate a smart search query based on blog post title.

    Args:
        title: Blog post title
        slug: Blog post slug

    Returns:
        Search query string
    """
    # Map common blog topics to better search queries
    query_mappings = {
        'british': 'british library books vintage',
        'american': 'american literature library',
        'shortest': 'reading book cozy',
        'non-native': 'reading learning education',
        'horror': 'dark atmospheric gothic',
        'romance': 'romantic vintage couple',
        'mystery': 'detective noir mystery',
        'adventure': 'adventure explore journey',
        'classics': 'classic literature vintage books',
        'english': 'english literature library'
    }

    # Check for keywords in title or slug
    title_lower = title.lower()
    slug_lower = slug.lower()

    for keyword, query in query_mappings.items():
        if keyword in title_lower or keyword in slug_lower:
            return query

    # Default: use first few words of title + "books literature"
    words = title.split()[:3]
    return ' '.join(words) + ' books literature'


def assign_image_to_post(db, post, force=False):
    """
    Assign an Unsplash image to a blog post.

    Args:
        db: Database instance
        post: Blog post dictionary
        force: Force re-assignment even if image exists

    Returns:
        True if image was assigned, False otherwise
    """
    slug = post['slug']
    title = post['title']
    current_image = post.get('header_image_url')

    # Skip if already has image and not forcing
    if current_image and not force:
        print(f"⏭ Skipping '{title}' (already has image)")
        return False

    # Generate search query
    query = generate_search_query(title, slug)
    print(f"\n📸 Searching for: '{query}'")

    # Search Unsplash
    results = search_unsplash(query)

    if not results:
        print(f"  ❌ No images found for '{title}'")
        return False

    # Use first result
    image = results[0]
    image_url = image['url']

    print(f"  ✓ Found image by {image['photographer']}")
    print(f"    URL: {image_url}")

    # Update database
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE blog_posts
        SET header_image_url = ?, updated_date = CURRENT_TIMESTAMP
        WHERE slug = ?
    ''', (image_url, slug))

    conn.commit()
    conn.close()

    print(f"  ✓ Updated '{title}'")
    return True


def main():
    parser = argparse.ArgumentParser(description='Assign Unsplash header images to blog posts')
    parser.add_argument('--slug', help='Assign image to specific blog post by slug')
    parser.add_argument('--force', action='store_true', help='Re-assign images even if they already exist')
    args = parser.parse_args()

    # Initialize database
    db = Database()

    # Get blog posts
    if args.slug:
        post = db.get_blog_post_by_slug(args.slug)
        if not post:
            print(f"ERROR: Blog post with slug '{args.slug}' not found")
            sys.exit(1)
        posts = [post]
    else:
        posts = db.get_all_blog_posts()

    if not posts:
        print("No blog posts found in database")
        return

    print(f"Found {len(posts)} blog post(s)")

    # Assign images
    assigned_count = 0
    for post in posts:
        if assign_image_to_post(db, post, force=args.force):
            assigned_count += 1

    print(f"\n✅ Done! Assigned images to {assigned_count} blog post(s)")

    if assigned_count > 0:
        print("\n⚠️  Attribution Requirements:")
        print("When using Unsplash images, you must provide attribution per their guidelines:")
        print("https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines")
        print("\nWe'll automatically display photographer credits on the blog posts.")


if __name__ == '__main__':
    main()
