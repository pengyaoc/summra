#!/usr/bin/env python3
"""
Validate blog post links to ensure all book links are valid
"""
import re
import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / 'data' / 'database.db'

def get_all_book_slugs():
    """Get all valid book slugs from database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT slug FROM books")
    slugs = [row['slug'] for row in cursor.fetchall()]

    conn.close()
    return set(slugs)

def extract_book_links(markdown_text):
    """Extract all Summra book links from markdown"""
    # Match patterns like [text](/books/slug)
    pattern = r'\[([^\]]+)\]\(/books/([^\)]+)\)'
    matches = re.findall(pattern, markdown_text)
    return matches

def validate_blog_posts():
    """Validate all blog post links"""
    valid_slugs = get_all_book_slugs()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, slug, title, content FROM blog_posts")
    posts = cursor.fetchall()

    conn.close()

    print(f"Validating links in {len(posts)} blog posts...")
    print(f"Found {len(valid_slugs)} valid book slugs in database\n")

    all_valid = True

    for post in posts:
        print(f"\n{'='*80}")
        print(f"Post: {post['title']}")
        print(f"Slug: {post['slug']}")
        print(f"{'='*80}")

        links = extract_book_links(post['content'])

        if not links:
            print("  ⚠️  No book links found")
            continue

        print(f"  Found {len(links)} book links:")

        for link_text, book_slug in links:
            if book_slug in valid_slugs:
                print(f"  ✓ {book_slug} ({link_text})")
            else:
                print(f"  ✗ {book_slug} ({link_text}) - INVALID SLUG!")
                all_valid = False

                # Suggest similar slugs
                similar = [s for s in valid_slugs if s and book_slug.replace('-', '') in s.replace('-', '')]
                if similar:
                    print(f"    Did you mean: {', '.join(similar[:3])}")

    print(f"\n{'='*80}")
    if all_valid:
        print("✓ All blog post links are valid!")
    else:
        print("✗ Some blog post links are invalid - please fix them")
    print(f"{'='*80}\n")

    return all_valid

if __name__ == '__main__':
    validate_blog_posts()
