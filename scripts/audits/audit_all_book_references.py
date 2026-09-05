#!/usr/bin/env python3
"""
Comprehensive audit of all book references in blog posts.
Finds all book mentions and checks if they have links.
"""

import sqlite3
import re

from backend import config

DB_PATH = config.DATABASE_PATH
BLOG_DIR = config.BLOG_DIR

def get_available_books():
    """Get all books with valid slugs from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, slug FROM books WHERE slug IS NOT NULL AND slug != ''")
    books = cursor.fetchall()
    conn.close()
    return {title: slug for title, slug in books}

def extract_existing_links(markdown_text):
    """Extract all existing book links from markdown"""
    pattern = r'\[([^\]]+)\]\(/books/([^\)]+)\)'
    matches = re.findall(pattern, markdown_text)
    return {link_text.lower(): slug for link_text, slug in matches}

def find_book_references(markdown_text, available_books):
    """Find all potential book references in the text"""
    references = []

    # Create a set of book titles (case insensitive)
    book_titles = {title.lower(): (title, slug) for title, slug in available_books.items()}

    # Split text into sentences for context
    sentences = re.split(r'[.!?]\s+', markdown_text)

    for sentence in sentences:
        sentence_lower = sentence.lower()

        # Check for each book title
        for title_lower, (original_title, slug) in book_titles.items():
            # Skip very short titles to avoid false positives
            if len(title_lower) < 5:
                continue

            # Look for the book title in the sentence
            if title_lower in sentence_lower:
                # Check if it's already linked
                # Look for markdown link pattern around this title
                is_linked = f']({slug})' in sentence or f'/books/{slug}' in sentence

                if not is_linked:
                    references.append({
                        'title': original_title,
                        'slug': slug,
                        'context': sentence.strip()[:150]
                    })

    return references

def audit_blog_post(blog_file, available_books):
    """Audit a single blog post for unlinked book references"""
    with open(blog_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Get existing links
    existing_links = extract_existing_links(content)

    # Find unlinked references
    unlinked_refs = find_book_references(content, available_books)

    # Remove duplicates (same book mentioned multiple times)
    unique_refs = {}
    for ref in unlinked_refs:
        key = ref['slug']
        if key not in unique_refs:
            unique_refs[key] = ref

    return list(unique_refs.values()), existing_links

def main():
    print("=" * 80)
    print("BLOG POST BOOK REFERENCE AUDIT")
    print("=" * 80)
    print()

    # Get available books
    available_books = get_available_books()
    print(f"Found {len(available_books)} books with valid slugs in database")
    print()

    # Audit each blog post
    blog_files = sorted(BLOG_DIR.glob('*.md'))

    total_unlinked = 0
    total_linked = 0

    for blog_file in blog_files:
        unlinked_refs, existing_links = audit_blog_post(blog_file, available_books)

        if unlinked_refs or existing_links:
            print(f"\n📄 {blog_file.name}")
            print("-" * 80)

            if existing_links:
                print(f"✅ Existing links: {len(existing_links)}")
                for link_text, slug in existing_links.items():
                    print(f"   - {link_text} → /books/{slug}")
                total_linked += len(existing_links)

            if unlinked_refs:
                print(f"\n⚠️  Unlinked book references: {len(unlinked_refs)}")
                for ref in unlinked_refs:
                    print(f"   - {ref['title']}")
                    print(f"     Slug: /books/{ref['slug']}")
                    print(f"     Context: {ref['context']}")
                    print()
                total_unlinked += len(unlinked_refs)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total blog posts: {len(blog_files)}")
    print(f"Total existing links: {total_linked}")
    print(f"Total unlinked references: {total_unlinked}")
    print()

if __name__ == '__main__':
    main()
