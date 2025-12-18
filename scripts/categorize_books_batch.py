#!/usr/bin/env python3
"""
Script to categorize all existing books using their medium summaries.

This script:
1. Fetches all books with medium summaries
2. Fetches all available categories from the database
3. Uses Gemini API to assign appropriate categories to each book
4. Saves the book-category associations to the database

Usage:
    python scripts/categorize_books_batch.py [--book-id BOOK_ID]

Options:
    --book-id BOOK_ID    Only categorize the specified book (optional)
"""

import sys
import json
import argparse
from pathlib import Path
import time

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from models import Database
import config
from google import genai
from google.genai import types


def categorize_book(db: Database, client: genai.Client, book: dict, categories: list) -> list:
    """
    Categorize a single book using its medium summary.

    Args:
        db: Database instance
        client: Gemini API client
        book: Book dictionary with id, title, author
        categories: List of available category dictionaries

    Returns:
        List of category names assigned to the book
    """
    # Get medium summary
    summary = db.get_summary(book['id'], 'medium')

    if not summary:
        print(f"  ⚠️  No medium summary found for '{book['title']}'")
        return []

    # Prepare category list for prompt
    category_list = "\n".join([f"- {cat['name']}: {cat['description']}" for cat in categories])

    # Prepare prompt
    prompt = f"""You are a literary expert. Based on the book summary below, assign the most appropriate categories from the provided list.

Book Title: {book['title']}
Author: {book['author']}

Summary:
{summary['content'][:3000]}

Available Categories:
{category_list}

Requirements:
1. Assign between 2-5 categories that genuinely fit this book
2. Only assign categories that are clearly relevant based on the summary
3. Only use categories from the provided list (exact name match)
4. Quality over quantity - it's better to have 2-3 highly relevant categories than to pad with less relevant ones
5. Consider both the primary genre AND thematic content (e.g., a Victorian novel might be both "Victorian Literature" and "Romance")
6. Do NOT assign a category unless it's clearly applicable to the book

Respond with a JSON object in this exact format:
{{
  "categories": ["Category Name 1", "Category Name 2", "Category Name 3"]
}}

Only respond with valid JSON, no additional text."""

    print(f"  → Analyzing '{book['title']}' by {book['author']}...")

    try:
        response = client.models.generate_content(
            model=config.SUMMARY_CONFIGS['combined']['model'],
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=500,
            )
        )

        # Extract response text
        if hasattr(response, 'text') and response.text:
            response_text = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                response_text = candidate.content.parts[0].text
            else:
                print(f"  ❌ Error: No content in response for '{book['title']}'")
                return []
        else:
            print(f"  ❌ Error: Empty response for '{book['title']}'")
            return []

        response_text = response_text.strip()

        # Extract JSON from response
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        # Parse JSON
        result = json.loads(response_text)

        if 'categories' not in result:
            print(f"  ❌ Error: Response does not contain 'categories' field")
            return []

        assigned_categories = result['categories']
        print(f"  ✓ Assigned {len(assigned_categories)} categories: {', '.join(assigned_categories)}")

        return assigned_categories

    except json.JSONDecodeError as e:
        print(f"  ❌ Error parsing JSON response: {e}")
        print(f"  Response: {response_text[:200]}")
        return []
    except Exception as e:
        print(f"  ❌ Error calling Gemini API: {e}")
        return []


def categorize_books_batch(book_id: int = None):
    """Categorize all books or a specific book."""

    # Initialize database
    db = Database()

    # Initialize Gemini client
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Get all categories
    categories = db.get_all_categories()

    if not categories:
        print("Error: No categories found in database. Run generate_master_categories.py first.")
        return

    print(f"Found {len(categories)} categories in database")

    # Get books to categorize
    if book_id:
        book = db.get_book(book_id)
        if not book:
            print(f"Error: Book with ID {book_id} not found")
            return
        books = [book]
        print(f"Categorizing book: {book['title']}")
    else:
        books = db.get_all_books()
        print(f"Found {len(books)} books to categorize")

    # Create category name to ID mapping
    category_name_to_id = {cat['name']: cat['id'] for cat in categories}

    # Categorize each book
    success_count = 0
    skip_count = 0

    for i, book in enumerate(books, 1):
        print(f"\n[{i}/{len(books)}] Processing: {book['title']}")

        # Check if book already has categories
        existing_categories = db.get_book_categories(book['id'])
        if existing_categories:
            print(f"  ℹ️  Book already has {len(existing_categories)} categories, skipping...")
            skip_count += 1
            continue

        # Categorize the book
        assigned_category_names = categorize_book(db, client, book, categories)

        if assigned_category_names:
            # Save categories to database
            for cat_name in assigned_category_names:
                if cat_name in category_name_to_id:
                    db.add_book_category(book['id'], category_name_to_id[cat_name])
                else:
                    print(f"  ⚠️  Warning: Category '{cat_name}' not found in database")

            success_count += 1
        else:
            print(f"  ⚠️  Failed to categorize '{book['title']}'")

        # Rate limiting: wait 2 seconds between API calls
        if i < len(books):
            time.sleep(2)

    print(f"\n{'='*60}")
    print(f"Categorization complete!")
    print(f"  ✓ Successfully categorized: {success_count} books")
    print(f"  ⊘ Skipped (already categorized): {skip_count} books")
    print(f"  ❌ Failed: {len(books) - success_count - skip_count} books")
    print(f"{'='*60}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Categorize books using their medium summaries')
    parser.add_argument('--book-id', type=int, help='Only categorize the specified book ID')

    args = parser.parse_args()

    categorize_books_batch(book_id=args.book_id)
