#!/usr/bin/env python3
"""
Regenerate medium summary for a specific book from database.
"""

import os
import sys
import time
import re
from pathlib import Path

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)

from google import genai
from dotenv import load_dotenv
import models
import config

def regenerate_medium_summary(book_id: int):
    """Regenerate medium summary for a book."""

    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables")
        sys.exit(1)

    # Initialize Gemini client
    client = genai.Client(api_key=api_key)

    # Initialize database
    db = models.Database()

    # Get book from database
    book = db.get_book(book_id)
    if not book:
        print(f"Error: Book with ID {book_id} not found")
        sys.exit(1)

    print(f"Book: {book['title']} by {book['author']}")

    # Get full text
    full_text = book.get('full_text')
    if not full_text:
        print("Error: Book has no full_text in database")
        sys.exit(1)

    # Limit text to first 200,000 characters for medium summary
    max_chars = 200000
    text = full_text[:max_chars]

    print(f"Text length: {len(text):,} characters")
    print("\nGenerating medium summary...")

    # Get model from config
    model_name = config.SUMMARY_CONFIGS['medium']['model']

    # Generate medium summary using Gemini
    prompt = f"""Generate a comprehensive 2000-3000 word summary of this book.

BOOK TITLE: {book['title']}
AUTHOR: {book['author']}

Cover all major plot points, themes, and character developments in chronological order. Discuss the author's writing style and analyze major themes. Spoilers are acceptable. For non-fiction, cover all main arguments, evidence, and conclusions.

BOOK TEXT:
{text}"""

    # Make API call with retry logic for rate limits
    max_retries = 3
    retry_count = 0
    medium_summary = None

    while retry_count <= max_retries:
        try:
            print(f"\n[Attempt {retry_count + 1}/{max_retries + 1}] Generating medium summary using {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            medium_summary = response.text.strip()
            print(f"✓ Generated medium summary ({len(medium_summary.split())} words)")
            break  # Success - exit retry loop

        except Exception as e:
            error_message = str(e)
            print(f"❌ API call failed: {type(e).__name__}")

            # Check if error is retriable (rate limit)
            is_retriable = ('429' in error_message or 'RESOURCE_EXHAUSTED' in error_message or
                           '503' in error_message or 'UNAVAILABLE' in error_message)

            # Extract retry delay from error message if present
            wait_time = 10  # Default
            if '429' in error_message or 'RESOURCE_EXHAUSTED' in error_message:
                retry_match = re.search(r'Please retry in ([\d.]+)([ms])', error_message)
                if retry_match:
                    delay_value = float(retry_match.group(1))
                    delay_unit = retry_match.group(2)
                    wait_time = int(delay_value) + 1 if delay_unit == 's' else int(delay_value / 1000) + 1
                    print(f"→ Suggested retry delay: {delay_value}{delay_unit}")
                else:
                    wait_time = 60  # Default to 1 minute for rate limits

            if is_retriable and retry_count < max_retries:
                retry_count += 1
                print(f"⚠️  Rate limit exceeded - retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                if retry_count > 0:
                    print(f"❌ Max retries exceeded")
                print(f"Error: {error_message[:200]}")
                sys.exit(1)

    if not medium_summary:
        print("Error: Failed to generate medium summary")
        sys.exit(1)

    # Save to database
    db.add_summary(book_id, 'medium', medium_summary)
    print("✓ Saved to database")

    # Display preview
    print("\n" + "="*60)
    print("MEDIUM SUMMARY PREVIEW:")
    print("="*60)
    print(medium_summary[:500] + "..." if len(medium_summary) > 500 else medium_summary)
    print("="*60)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python regenerate_medium_summary.py <book_id>")
        sys.exit(1)

    try:
        book_id = int(sys.argv[1])
    except ValueError:
        print("Error: book_id must be an integer")
        sys.exit(1)

    regenerate_medium_summary(book_id)
