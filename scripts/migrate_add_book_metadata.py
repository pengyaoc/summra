#!/usr/bin/env python3
"""
Database migration script to add new book metadata fields.

Adds:
1. books.about_text - Short "About the Book" section (150-200 words)
2. books.relevance_now - Why the book is relevant today (100-150 words)
3. authors.country - Author's country
4. authors.other_books - Comma-separated list of other books by author
5. similar_books table - Many-to-many relationship for book recommendations
"""

import sqlite3
from pathlib import Path


def migrate_database():
    """Apply database migrations for new metadata fields."""
    db_path = Path(__file__).parent.parent / 'data' / 'database.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print("Starting database migration...")

    # 1. Add new columns to books table
    print("\n1. Adding new columns to books table...")

    columns_to_add = [
        ("about_text", "TEXT"),  # Short summary for "About the Book" section
        ("relevance_now", "TEXT"),  # Why relevant today
    ]

    for column_name, column_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE books ADD COLUMN {column_name} {column_type}")
            print(f"   ✓ Added books.{column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"   ⊘ books.{column_name} already exists")
            else:
                raise

    # 2. Update authors table - add other_books column
    print("\n2. Adding other_books column to authors table...")
    try:
        cursor.execute("ALTER TABLE authors ADD COLUMN other_books TEXT")
        print("   ✓ Added authors.other_books")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("   ⊘ authors.other_books already exists")
        else:
            raise

    # 3. Create similar_books table for many-to-many relationships
    print("\n3. Creating similar_books table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS similar_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            similar_book_id INTEGER NOT NULL,
            rank INTEGER NOT NULL,  -- 1-5, indicating order of similarity
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
            FOREIGN KEY (similar_book_id) REFERENCES books(id) ON DELETE CASCADE,
            UNIQUE(book_id, similar_book_id),
            CHECK(book_id != similar_book_id)  -- Can't be similar to itself
        )
    """)
    print("   ✓ Created similar_books table")

    # 4. Create index for performance
    print("\n4. Creating indexes...")
    indexes = [
        ("idx_similar_books_book_id", "similar_books", "book_id"),
        ("idx_similar_books_similar_id", "similar_books", "similar_book_id"),
    ]

    for index_name, table_name, column_name in indexes:
        try:
            cursor.execute(f"CREATE INDEX {index_name} ON {table_name}({column_name})")
            print(f"   ✓ Created index {index_name}")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                print(f"   ⊘ Index {index_name} already exists")
            else:
                raise

    # Commit changes
    conn.commit()
    print("\n✅ Migration completed successfully!")

    # Show updated schema
    print("\n📋 Updated schema:")
    cursor.execute("PRAGMA table_info(books)")
    print("\nbooks table columns:")
    for row in cursor.fetchall():
        print(f"  - {row[1]} ({row[2]})")

    cursor.execute("PRAGMA table_info(authors)")
    print("\nauthors table columns:")
    for row in cursor.fetchall():
        print(f"  - {row[1]} ({row[2]})")

    cursor.execute("PRAGMA table_info(similar_books)")
    print("\nsimilar_books table columns:")
    for row in cursor.fetchall():
        print(f"  - {row[1]} ({row[2]})")

    conn.close()


if __name__ == '__main__':
    migrate_database()
