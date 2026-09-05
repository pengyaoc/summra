#!/usr/bin/env python3
"""
Import blog posts from markdown files into the database.
Reads all .md files from data/blog/ and inserts them into blog_posts table.
"""

import re
from datetime import datetime
from backend import config
from backend.models import Database


def slugify(text):
    """Convert text to URL-friendly slug"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


def extract_title_from_markdown(content):
    """Extract title from first H1 heading"""
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def extract_excerpt(content, max_chars=200):
    """Extract first 200 characters as excerpt, excluding the title"""
    # Remove title (first H1)
    content_without_title = re.sub(r'^#\s+.+$', '', content, count=1, flags=re.MULTILINE)

    # Remove other markdown formatting
    text = re.sub(r'#+\s+', '', content_without_title)  # Remove headers
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # Remove bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)  # Remove italic
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)  # Remove links
    text = re.sub(r'\n+', ' ', text)  # Replace newlines with spaces
    text = text.strip()

    # Extract first max_chars characters
    if len(text) > max_chars:
        excerpt = text[:max_chars].rsplit(' ', 1)[0] + '...'
    else:
        excerpt = text

    return excerpt


def main():
    """Import all blog posts from data/blog/ directory"""
    # Get blog directory path
    blog_dir = config.BLOG_DIR

    if not blog_dir.exists():
        print(f"Error: Blog directory not found at {blog_dir}")
        return

    # Initialize database
    db = Database()

    # Get all markdown files (excluding README.md)
    md_files = [f for f in blog_dir.glob('*.md') if f.name != 'README.md']

    if not md_files:
        print(f"No blog posts found in {blog_dir}")
        return

    print(f"Found {len(md_files)} blog posts to import")

    imported_count = 0
    for md_file in md_files:
        try:
            # Read markdown file
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract metadata
            title = extract_title_from_markdown(content)
            if not title:
                print(f"Warning: No title found in {md_file.name}, skipping")
                continue

            # Generate slug from filename
            slug = md_file.stem  # filename without extension

            # Extract excerpt
            excerpt = extract_excerpt(content)

            # Use file modification time as published date
            published_date = datetime.fromtimestamp(md_file.stat().st_mtime).strftime('%Y-%m-%d')

            # Insert into database
            db.add_blog_post(
                slug=slug,
                title=title,
                content=content,
                excerpt=excerpt,
                published_date=published_date
            )

            imported_count += 1
            print(f"✓ Imported: {title}")
            print(f"  Slug: {slug}")
            print(f"  Excerpt: {excerpt[:50]}...")

        except Exception as e:
            print(f"Error importing {md_file.name}: {e}")
            continue

    print(f"\nImport complete: {imported_count}/{len(md_files)} blog posts imported successfully")


if __name__ == '__main__':
    main()
