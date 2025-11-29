#!/usr/bin/env python3
"""
Script to generate a master category list for the book library.

This script:
1. Fetches all books with their medium summaries
2. Uses Gemini API to analyze the books and suggest a unified category list (<30 categories)
3. Saves the categories to the database

Usage:
    python scripts/generate_master_categories.py
"""

import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from models import Database
import config
from google import genai
from google.genai import types


def generate_master_categories():
    """Generate master category list by analyzing all books."""

    # Initialize database
    db = Database()

    # Get all books
    books = db.get_all_books()

    if not books:
        print("No books found in database.")
        return

    print(f"Found {len(books)} books in library")

    # Fetch medium summaries for all books
    book_summaries = []
    for book in books:
        summary = db.get_summary(book['id'], 'medium')
        if summary:
            book_summaries.append({
                'id': book['id'],
                'title': book['title'],
                'author': book['author'],
                'summary': summary['content'][:2000]  # Limit to 2000 chars to save tokens
            })

    print(f"Found {len(book_summaries)} books with medium summaries")

    if not book_summaries:
        print("No books with medium summaries found. Generate summaries first.")
        return

    # Prepare prompt for Gemini
    books_text = "\n\n".join([
        f"Book {i+1}:\nTitle: {b['title']}\nAuthor: {b['author']}\nSummary excerpt: {b['summary'][:500]}..."
        for i, b in enumerate(book_summaries[:50])  # Limit to 50 books to avoid token limits
    ])

    prompt = f"""You are a literary expert analyzing a classic book library. Based on the book summaries below, create a comprehensive but concise category system.

Requirements:
1. Generate between 20-30 categories that cover all the books
2. Categories should be mutually exclusive where possible (though books can belong to multiple categories)
3. Use clear, standard category names (e.g., "Classic Fiction", "Gothic Horror", "Romance", "Adventure", "Philosophy")
4. Include both genre-based categories (Fiction, Mystery, Romance) and theme-based categories (Coming of Age, Social Commentary)
5. For each category, provide a brief 1-sentence description

Book Library Sample:
{books_text}

Respond with a JSON object in this exact format:
{{
  "categories": [
    {{
      "name": "Category Name",
      "description": "Brief description of what books fit this category"
    }},
    ...
  ]
}}

Only respond with valid JSON, no additional text."""

    print("\nAnalyzing books with Gemini API...")
    print(f"Using model: {config.SUMMARY_CONFIGS['medium']['model']}")

    # Call Gemini API
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)

        response = client.models.generate_content(
            model=config.SUMMARY_CONFIGS['medium']['model'],
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8000,  # Increased to accommodate thinking tokens
            )
        )

        # Debug: Check response structure
        print(f"Finish reason: {response.candidates[0].finish_reason if response.candidates else 'N/A'}")
        print(f"Usage metadata: {response.usage_metadata}")

        # Try to access the response text
        try:
            if hasattr(response, 'text') and response.text:
                response_text = response.text
            elif hasattr(response, 'candidates') and response.candidates:
                # Try accessing via candidates
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                    response_text = candidate.content.parts[0].text
                else:
                    print(f"Error: Candidate has no content parts")
                    print(f"Candidate: {candidate}")
                    return
            else:
                print(f"Error: Cannot extract text from response")
                return

            if not response_text:
                print("Error: Response text is empty")
                return

            response_text = response_text.strip()
            print(f"Successfully extracted response ({len(response_text)} chars)")
        except Exception as e:
            print(f"Error extracting response text: {e}")
            print(f"Response candidates: {response.candidates if hasattr(response, 'candidates') else 'N/A'}")
            return

        # Extract JSON from response (might be wrapped in markdown code blocks)
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        categories_data = json.loads(response_text)

        if 'categories' not in categories_data:
            print("Error: Response does not contain 'categories' field")
            print(f"Response: {response_text}")
            return

        categories = categories_data['categories']
        print(f"\nGenerated {len(categories)} categories:")

        # Save categories to database
        saved_count = 0
        for category in categories:
            name = category['name']
            description = category.get('description', '')

            print(f"  - {name}: {description}")

            category_id = db.add_category(name, description)
            if category_id:
                saved_count += 1

        print(f"\nSuccessfully saved {saved_count} categories to database!")

        # Verify categories were saved
        all_categories = db.get_all_categories()
        print(f"\nTotal categories in database: {len(all_categories)}")

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Response text: {response_text}")
        return
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return


if __name__ == '__main__':
    generate_master_categories()
