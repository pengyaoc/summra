#!/usr/bin/env python3
"""Check for duplicate King in Yellow entries in database"""
from scripts.lib.db import get_connection

conn = get_connection()
cursor = conn.cursor()

# Find all books with "King in Yellow" in title
query = "SELECT id, title, author, word_count, gutenberg_id, cover_image FROM books WHERE title LIKE ?"
books = cursor.execute(query, ('%King in Yellow%',)).fetchall()

print(f"Found {len(books)} book(s) matching 'King in Yellow':\n")

for book in books:
    book_id = book['id']
    title = book['title']
    author = book['author']
    word_count = book['word_count']
    gutenberg_id = book['gutenberg_id']
    cover_image = book['cover_image']

    print(f"Book ID: {book_id}")
    print(f"  Title: {title}")
    print(f"  Author: {author}")
    print(f"  Word count: {word_count:,}")
    print(f"  Gutenberg ID: {gutenberg_id}")
    print(f"  Cover image: {cover_image}")

    # Check summaries
    summaries = cursor.execute(
        "SELECT summary_type, LENGTH(content) as length FROM summaries WHERE book_id = ?",
        (book_id,)
    ).fetchall()
    print(f"  Summaries: {len(summaries)}")
    for summary in summaries:
        print(f"    - {summary['summary_type']}: {summary['length']:,} chars")

    # Check chapters
    chapter_count = cursor.execute(
        "SELECT COUNT(*) as count FROM chapters WHERE book_id = ?",
        (book_id,)
    ).fetchone()['count']
    print(f"  Chapters: {chapter_count}")

    print()

conn.close()
