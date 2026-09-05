#!/usr/bin/env python3
"""
Shared categorization module for Summra.

This module provides common functionality for categorizing books using LLM analysis
of their medium summaries. It's used by both:
1. generate_summaries.py - For automatic categorization of new books
2. categorize_books_batch.py - For bulk backfill of existing books

Design principles:
- DRY: Single source of truth for categorization logic
- Maximum 5 categories per book
- Uses only predefined categories from database
- Minimizes incorrect categorization through careful prompting
"""

import json
import time
from typing import List, Dict, Optional

from google import genai
from backend import config
from backend import models


def categorize_single_book(client: genai.Client, db: models.Database,
                           book: dict, categories: list,
                           medium_summary: str = None) -> list:
    """
    Categorize a single book using its medium summary.

    Args:
        client: Gemini API client
        db: Database instance
        book: Book dict with keys: id, title, author
        categories: List of category dicts with keys: name, description
        medium_summary: Optional pre-loaded medium summary (if None, will fetch from DB)

    Returns:
        List of category names (2-5 categories)
    """
    # Get medium summary if not provided
    if medium_summary is None:
        summary = db.get_summary(book['id'], 'medium')
        if not summary:
            print(f"  ⚠️  No medium summary found for book {book['id']}")
            return []
        medium_summary = summary['content']

    # Truncate summary to 3000 words for efficient processing
    summary_words = medium_summary.split()
    if len(summary_words) > 3000:
        medium_summary = ' '.join(summary_words[:3000])

    # Prepare category list for prompt
    category_list = "\n".join([f"- {cat['name']}: {cat['description']}" for cat in categories])

    prompt = f"""You are a literary expert. Based on the book summary below, assign the most appropriate categories from the provided list.

Book Title: {book['title']}
Author: {book['author']}

Summary:
{medium_summary}

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

    try:
        response = client.models.generate_content(
            model=config.SUMMARY_CONFIGS['combined']['model'],
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=2000,  # Increased to accommodate thinking tokens
            )
        )

        # Parse JSON response - handle both text attribute and candidates
        response_text = None
        if hasattr(response, 'text') and response.text:
            response_text = response.text.strip()
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                response_text = candidate.content.parts[0].text.strip()

        if not response_text:
            print(f"  ❌ No content in response")
            return []

        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])  # Remove first and last line

        data = json.loads(response_text)
        category_names = data.get('categories', [])

        # Validate categories exist in database and limit to 5
        valid_categories = []
        category_name_set = {cat['name'] for cat in categories}

        for cat_name in category_names[:5]:  # Maximum 5
            if cat_name in category_name_set:
                valid_categories.append(cat_name)
            else:
                print(f"  ⚠️  Warning: Category '{cat_name}' not in database, skipping")

        return valid_categories

    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parsing error: {e}")
        print(f"  Response was: {response.text[:200]}")
        return []
    except Exception as e:
        print(f"  ❌ Error categorizing book: {e}")
        return []


def categorize_books_bulk(client: genai.Client, db: models.Database,
                          books: List[dict], categories: list,
                          batch_size: int = 10) -> Dict[int, List[str]]:
    """
    Categorize multiple books in batches using a single LLM request per batch.

    This is optimized for bulk backfill operations where we want to minimize API calls
    while maintaining accuracy.

    Args:
        client: Gemini API client
        db: Database instance
        books: List of book dicts with keys: id, title, author
        categories: List of category dicts with keys: name, description
        batch_size: Number of books to process per LLM request (default: 10)

    Returns:
        Dict mapping book_id -> list of category names
    """
    results = {}

    # Process books in batches
    for i in range(0, len(books), batch_size):
        batch = books[i:i + batch_size]
        batch_ids = [book['id'] for book in batch]

        print(f"\n  Processing batch {i//batch_size + 1}/{(len(books) + batch_size - 1)//batch_size}: Books {batch_ids}")

        # Build batch prompt with all books
        book_summaries = []
        book_id_to_index = {}  # Map book ID to 1-based index for response parsing

        for idx, book in enumerate(batch, start=1):
            # Get medium summary
            summary = db.get_summary(book['id'], 'medium')
            if not summary:
                print(f"    ⚠️  No medium summary for book {book['id']}, skipping")
                continue

            # Truncate to 1500 words per book (to fit ~10 books in one request)
            summary_words = summary['content'].split()
            if len(summary_words) > 1500:
                summary_text = ' '.join(summary_words[:1500])
            else:
                summary_text = summary['content']

            book_id_to_index[book['id']] = idx
            book_summaries.append(f"""
BOOK {idx}:
Title: {book['title']}
Author: {book['author']}
Summary: {summary_text}
""")

        if not book_summaries:
            print("    No books with summaries in this batch, skipping")
            continue

        # Prepare category list
        category_list = "\n".join([f"- {cat['name']}: {cat['description']}" for cat in categories])

        # Build bulk categorization prompt
        prompt = f"""You are a literary expert. Categorize the following {len(book_summaries)} books based on their summaries.

For each book, assign the most appropriate categories from the provided list.

Available Categories:
{category_list}

Books to Categorize:
{"".join(book_summaries)}

Requirements:
1. Assign between 2-5 categories per book that genuinely fit
2. Only assign categories that are clearly relevant based on each summary
3. Only use categories from the provided list (exact name match)
4. Quality over quantity - it's better to have 2-3 highly relevant categories than to pad with less relevant ones
5. Consider both primary genre AND thematic content
6. Do NOT assign a category unless it's clearly applicable to the book

Respond with a JSON object in this exact format:
{{
  "1": ["Category 1", "Category 2"],
  "2": ["Category 1", "Category 3"],
  ...
}}

Use the BOOK numbers (1, 2, 3...) as keys. Only respond with valid JSON, no additional text."""

        try:
            response = client.models.generate_content(
                model=config.SUMMARY_CONFIGS['combined']['model'],
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=8000,  # Increased to accommodate thinking tokens
                )
            )

            # Parse JSON response - handle both text attribute and candidates
            response_text = None
            if hasattr(response, 'text') and response.text:
                response_text = response.text.strip()
            elif hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                    response_text = candidate.content.parts[0].text.strip()

            if not response_text:
                print(f"    ❌ No content in response")
                for book_id in book_id_to_index.keys():
                    results[book_id] = []
                return results

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])

            data = json.loads(response_text)

            # Map indices back to book IDs and validate categories
            category_name_set = {cat['name'] for cat in categories}

            for book_id, idx in book_id_to_index.items():
                idx_str = str(idx)
                if idx_str in data:
                    category_names = data[idx_str]

                    # Validate and limit to 5
                    valid_categories = []
                    for cat_name in category_names[:5]:
                        if cat_name in category_name_set:
                            valid_categories.append(cat_name)
                        else:
                            print(f"    ⚠️  Book {book_id}: Category '{cat_name}' not found, skipping")

                    results[book_id] = valid_categories
                    print(f"    ✓ Book {book_id}: {len(valid_categories)} categories")
                else:
                    print(f"    ⚠️  Book {book_id}: No categories in response")
                    results[book_id] = []

        except json.JSONDecodeError as e:
            print(f"    ❌ JSON parsing error: {e}")
            print(f"    Response was: {response.text[:200]}")
            # Mark all books in batch as failed
            for book_id in book_id_to_index.keys():
                results[book_id] = []
        except Exception as e:
            print(f"    ❌ Error processing batch: {e}")
            # Mark all books in batch as failed
            for book_id in book_id_to_index.keys():
                results[book_id] = []

        # Rate limiting: wait between batches to avoid hitting API limits
        if i + batch_size < len(books):
            print("    Waiting 2 seconds before next batch...")
            time.sleep(2)

    return results


def save_book_categories(db: models.Database, book_id: int, category_names: List[str]):
    """
    Save categories for a book to the database.

    Clears existing categories and replaces with new ones.

    Args:
        db: Database instance
        book_id: Book ID
        category_names: List of category names to assign
    """
    # Clear existing categories
    db.clear_book_categories(book_id)

    # Add new categories
    for cat_name in category_names:
        category = db.get_category_by_name(cat_name)
        if category:
            db.add_book_category(book_id, category['id'])
