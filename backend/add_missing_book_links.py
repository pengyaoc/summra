#!/usr/bin/env python3
"""
Automatically add links to book references in blog posts.
"""

import sqlite3
import re
from pathlib import Path

# Database connection
DB_PATH = Path(__file__).parent.parent / 'data' / 'database.db'
BLOG_DIR = Path(__file__).parent.parent / 'data' / 'blog'

def get_available_books():
    """Get all books with valid slugs from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, slug FROM books WHERE slug IS NOT NULL AND slug != ''")
    books = cursor.fetchall()
    conn.close()
    return {title: slug for title, slug in books}

def add_links_to_content(content, available_books):
    """Add links to book references in markdown content"""
    changes = []

    # Create a mapping of book titles for matching
    book_mapping = {}
    for title, slug in available_books.items():
        # Store both exact title and lowercase version
        book_mapping[title.lower()] = (title, slug)

    lines = content.split('\n')
    new_lines = []

    for line_num, line in enumerate(lines, 1):
        original_line = line
        modified = False

        # Skip if line already has a link to this book
        if '/books/' in line:
            new_lines.append(line)
            continue

        # Pattern 1: Section headers like "### Pride and Prejudice by Jane Austen"
        header_match = re.match(r'^(#{1,6}\s+)([^#\n]+?)(\s+by\s+.+)?$', line)
        if header_match:
            prefix = header_match.group(1)
            title_part = header_match.group(2).strip()
            suffix = header_match.group(3) or ''

            # Check if this title matches any book
            title_lower = title_part.lower()
            if title_lower in book_mapping:
                book_title, slug = book_mapping[title_lower]
                # Add link to the title part
                line = f"{prefix}[{title_part}](/books/{slug}){suffix}"
                modified = True
                changes.append({
                    'line': line_num,
                    'original': original_line,
                    'new': line,
                    'book': book_title
                })

        # Pattern 2: Standalone book titles in sentences
        # Look for book titles that are NOT already in markdown links
        else:
            for title_lower, (book_title, slug) in book_mapping.items():
                # Skip very short titles to avoid false positives
                if len(title_lower) < 8:
                    continue

                # Skip if the title is part of a character name (e.g., "Victor Frankenstein")
                # Look for the title preceded by a name
                if re.search(r'\b(?:Mr\.|Mrs\.|Miss|Victor|Elizabeth|Captain)\s+' + re.escape(book_title), line, re.IGNORECASE):
                    continue

                # Create pattern to match the title when it's not already in a link
                # Look for the title not preceded by [ or /books/
                # Also make sure it's a word boundary (not part of another word)
                pattern = r'(?<!\[)(?<!/)(?<!/)\b(' + re.escape(book_title) + r')\b(?!\]|\(|/)'

                if re.search(pattern, line, re.IGNORECASE):
                    # Don't link if it's in a table or heading that's already covered
                    if line.strip().startswith('|') or line.strip().startswith('#'):
                        # Let the header pattern handle headings
                        continue

                    # Replace with linked version
                    def replace_with_link(match):
                        return f"[{match.group(1)}](/books/{slug})"

                    new_line = re.sub(pattern, replace_with_link, line, count=1, flags=re.IGNORECASE)

                    if new_line != line:
                        changes.append({
                            'line': line_num,
                            'original': line,
                            'new': new_line,
                            'book': book_title
                        })
                        line = new_line
                        modified = True
                        break  # Only replace one book per line

        new_lines.append(line)

    return '\n'.join(new_lines), changes

def process_blog_post(blog_file, available_books, dry_run=True):
    """Process a single blog post"""
    with open(blog_file, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content, changes = add_links_to_content(content, available_books)

    if changes:
        print(f"\n📄 {blog_file.name}")
        print("-" * 80)
        print(f"Found {len(changes)} places to add links:\n")

        for change in changes:
            print(f"Line {change['line']}: {change['book']}")
            print(f"  - {change['original'][:100]}")
            print(f"  + {change['new'][:100]}")
            print()

        if not dry_run:
            with open(blog_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ Updated {blog_file.name}")

    return len(changes)

def main():
    import sys
    dry_run = '--apply' not in sys.argv

    print("=" * 80)
    print("ADDING BOOK LINKS TO BLOG POSTS")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'APPLY CHANGES'}")
    print()

    if dry_run:
        print("Run with --apply to actually modify files")
        print()

    # Get available books
    available_books = get_available_books()
    print(f"Found {len(available_books)} books with valid slugs")
    print()

    # Process each blog post
    blog_files = sorted(BLOG_DIR.glob('*.md'))
    blog_files = [f for f in blog_files if f.name != 'README.md']  # Skip README

    total_changes = 0

    for blog_file in blog_files:
        changes_count = process_blog_post(blog_file, available_books, dry_run)
        total_changes += changes_count

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total blog posts processed: {len(blog_files)}")
    print(f"Total links to add: {total_changes}")

    if dry_run and total_changes > 0:
        print("\nTo apply these changes, run:")
        print("  python backend/add_missing_book_links.py --apply")
    print()

if __name__ == '__main__':
    main()
