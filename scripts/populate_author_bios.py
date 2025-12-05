#!/usr/bin/env python3
"""
Populate author biographies using LLM batch generation.

This script generates comprehensive author data using Google's Gemini API:
1. Short bio (75-100 words)
2. Long bio (500 words)
3. Top 10 books
4. Country of origin

Authors are processed in batches of 25 for efficiency.

Usage:
    python populate_author_bios.py [--dry-run] [--author "Author Name"] [--batch-size 25]
"""

import os
import sys
import time
import argparse
import json
from pathlib import Path
from typing import Optional, Dict, List

# Add backend directory to path
backend_dir = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))

import models
import config

# Import genai lazily (only when needed)
genai = None


class AuthorBioGenerator:
    """Generate author biographies using LLM batch processing"""

    def __init__(self, dry_run: bool = False, batch_size: int = 25):
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.db = models.Database()

        # Initialize Gemini client (skip in dry-run mode)
        if not dry_run:
            # Import genai only when needed
            global genai
            if genai is None:
                from google import genai as genai_module
                genai = genai_module

            api_key = os.getenv('GEMINI_API_KEY') or config.GEMINI_API_KEY
            if not api_key:
                raise ValueError("GEMINI_API_KEY not set in environment or config")
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None

        self.model_name = 'gemini-2.5-flash'

        # Statistics
        self.stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }

    def _parse_structured_response(self, response_text: str) -> Dict[str, Dict]:
        """
        Parse structured text response into author data dictionary.

        Format:
        AUTHOR: Name
        COUNTRY: Country
        SHORT_BIO: Bio text
        LONG_BIO: Bio text
        TOP_BOOKS:
        - Book 1
        - Book 2
        ---

        Args:
            response_text: Raw response text from LLM

        Returns:
            Dictionary mapping author names to their data
        """
        batch_data = {}

        # Split by author separator
        author_sections = response_text.split('---')

        for section in author_sections:
            section = section.strip()
            if not section:
                continue

            # Initialize author data
            author_data = {
                'short_bio': '',
                'long_bio': '',
                'top_books': [],
                'country': ''
            }

            # Parse fields
            author_name = None
            current_field = None
            books_section = False

            for line in section.split('\n'):
                line = line.strip()

                if line.startswith('AUTHOR:'):
                    author_name = line.replace('AUTHOR:', '').strip()
                    current_field = None
                    books_section = False

                elif line.startswith('COUNTRY:'):
                    author_data['country'] = line.replace('COUNTRY:', '').strip()
                    current_field = None
                    books_section = False

                elif line.startswith('SHORT_BIO:'):
                    author_data['short_bio'] = line.replace('SHORT_BIO:', '').strip()
                    current_field = 'short_bio'
                    books_section = False

                elif line.startswith('LONG_BIO:'):
                    author_data['long_bio'] = line.replace('LONG_BIO:', '').strip()
                    current_field = 'long_bio'
                    books_section = False

                elif line.startswith('TOP_BOOKS:'):
                    current_field = None
                    books_section = True

                elif books_section and line.startswith('-'):
                    # Extract book title (remove leading "- ")
                    book_title = line[1:].strip()
                    if book_title:
                        author_data['top_books'].append(book_title)

                elif current_field and line:
                    # Continue previous field (multi-line content)
                    author_data[current_field] += ' ' + line

            # Add to batch data if we have an author name
            if author_name:
                # Clean up any extra whitespace
                author_data['short_bio'] = ' '.join(author_data['short_bio'].split())
                author_data['long_bio'] = ' '.join(author_data['long_bio'].split())
                batch_data[author_name] = author_data

        return batch_data

    def generate_batch_bios(self, author_names: List[str]) -> Dict[str, Dict]:
        """
        Generate bios for a batch of authors using a single LLM call.

        Args:
            author_names: List of author names to process

        Returns:
            Dictionary mapping author names to their bio data
        """
        if not author_names:
            return {}

        print(f"\n→ Generating bios for batch of {len(author_names)} authors...")

        # Create prompt for batch generation
        authors_list = '\n'.join([f"{i+1}. {name}" for i, name in enumerate(author_names)])

        prompt = f"""Generate comprehensive biographical data for the following authors. For each author, provide the information using this format:

AUTHOR: [Author Name]
COUNTRY: [Country of origin]
SHORT_BIO: [75-100 word concise biography covering key contributions and significance]
LONG_BIO: [Approximately 500 word detailed biography covering life, works, writing style, themes, and cultural impact]
TOP_BOOKS:
- [Book 1]
- [Book 2]
- [Book 3]
- [Book 4]
- [Book 5]
- [Book 6]
- [Book 7]
- [Book 8]
- [Book 9]
- [Book 10]
---

Authors to process:
{authors_list}

Guidelines:
- Use the exact author names as provided above after "AUTHOR:"
- Keep SHORT_BIO between 75-100 words
- Keep LONG_BIO around 500 words (450-550 acceptable)
- List up to 10 books in TOP_BOOKS (or fewer if the author has written fewer than 10 notable works)
- Use standard country names (e.g., "United States" not "USA", "United Kingdom" not "England")
- Focus on factual, informative content
- Include birth/death dates if known in the biographies
- Highlight literary significance and major themes
- Separate each author's data with "---"
- Each book should be on its own line starting with "- "

Example format:
AUTHOR: Jane Austen
COUNTRY: United Kingdom
SHORT_BIO: Jane Austen (1775-1817) was an English novelist known for her witty social commentary and romantic plots. Her six major novels, including Pride and Prejudice and Emma, explore themes of love, marriage, and social class in Georgian England. Austen's sharp observations and ironic narrative voice have made her one of the most beloved and influential writers in English literature.
LONG_BIO: [500 word biography here...]
TOP_BOOKS:
- Pride and Prejudice
- Sense and Sensibility
- Emma
- Mansfield Park
- Northanger Abbey
- Persuasion
---"""

        # In dry-run mode, print the prompt and return
        if self.dry_run:
            print("\n" + "="*60)
            print("DRY RUN - PROMPT PREVIEW")
            print("="*60)
            print(f"\nModel: {self.model_name}")
            print(f"Temperature: 0.3")
            print(f"Max output tokens: 8000")
            print(f"\n{prompt}")
            print("\n" + "="*60)
            print("END OF PROMPT")
            print("="*60)
            return {}

        try:
            # Make API call with retry logic
            max_retries = 3
            retry_count = 0

            while retry_count <= max_retries:
                try:
                    print(f"  [API Call] Attempt {retry_count + 1}/{max_retries + 1}...")

                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config={
                            'temperature': 0.3,  # Lower temperature for factual content
                            'max_output_tokens': 8000,  # Allow for batch response
                        }
                    )

                    # Extract and parse structured text response
                    response_text = response.text.strip()

                    # Parse the structured text format
                    batch_data = self._parse_structured_response(response_text)

                    if batch_data:
                        print(f"  ✓ Successfully generated bios for {len(batch_data)} authors")
                        return batch_data
                    else:
                        raise ValueError("No author data parsed from response")

                except ValueError as e:
                    print(f"  ✗ Parsing error: {str(e)}")
                    if retry_count < max_retries:
                        print(f"  → Retrying in 2 seconds...")
                        time.sleep(2)
                        retry_count += 1
                    else:
                        print(f"  ✗ Failed after {max_retries + 1} attempts")
                        return {}

                except Exception as e:
                    print(f"  ✗ API error: {str(e)}")
                    if retry_count < max_retries:
                        print(f"  → Retrying in 2 seconds...")
                        time.sleep(2)
                        retry_count += 1
                    else:
                        print(f"  ✗ Failed after {max_retries + 1} attempts")
                        return {}

        except Exception as e:
            print(f"  ✗ Unexpected error: {str(e)}")
            return {}

    def populate_author(self, author_name: str, author_id: int, bio_data: Dict) -> bool:
        """
        Populate bio data for a single author.

        Args:
            author_name: Name of the author
            author_id: Database ID of the author
            bio_data: Dictionary containing short_bio, long_bio, top_books, country

        Returns:
            True if successful, False otherwise
        """
        print(f"\n  Processing: {author_name}")
        self.stats['total'] += 1

        if not bio_data:
            print(f"    ✗ No bio data provided")
            self.stats['failed'] += 1
            return False

        # Validate data
        short_bio = bio_data.get('short_bio', '').strip()
        long_bio = bio_data.get('long_bio', '').strip()
        top_books = bio_data.get('top_books', [])
        country = bio_data.get('country', '').strip()

        # Word count validation
        short_bio_words = len(short_bio.split())
        long_bio_words = len(long_bio.split())

        print(f"    Short bio: {short_bio_words} words")
        print(f"    Long bio: {long_bio_words} words")
        print(f"    Top books: {len(top_books)} titles")
        print(f"    Country: {country}")

        # Update database
        if self.dry_run:
            print(f"    [DRY RUN] Would update database with:")
            print(f"      - Short bio ({short_bio_words} words)")
            print(f"      - Long bio ({long_bio_words} words)")
            print(f"      - Country: {country}")
            print(f"      - Books: {', '.join(top_books[:3])}{'...' if len(top_books) > 3 else ''}")
        else:
            try:
                conn = self.db.get_connection()
                cursor = conn.cursor()

                # Prepare update
                updates = []
                params = []

                if short_bio:
                    updates.append('short_bio = ?')
                    params.append(short_bio)

                if long_bio:
                    updates.append('long_bio = ?')
                    params.append(long_bio)

                if country:
                    updates.append('country = ?')
                    params.append(country)

                if top_books:
                    # Store as JSON array to handle book titles with commas
                    top_books_json = json.dumps(top_books[:10])
                    updates.append('other_books = ?')
                    params.append(top_books_json)

                if updates:
                    params.append(author_id)
                    query = f"UPDATE authors SET {', '.join(updates)} WHERE id = ?"
                    cursor.execute(query, params)
                    conn.commit()

                conn.close()

                print(f"    ✓ Database updated successfully")
                self.stats['successful'] += 1
                return True

            except Exception as e:
                print(f"    ✗ Database update failed: {str(e)}")
                self.stats['failed'] += 1
                return False

    def populate_all_authors(self):
        """Populate bios for all authors in database using batch processing"""
        # Get all authors with their data
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, short_bio, long_bio, country, other_books
            FROM authors
            ORDER BY name
        """)

        authors = cursor.fetchall()
        conn.close()

        # Filter authors that need bios
        authors_to_process = []
        for author in authors:
            # Check if all four fields are populated
            has_short_bio = author['short_bio'] and author['short_bio'].strip()
            has_long_bio = author['long_bio'] and author['long_bio'].strip()
            has_country = author['country'] and author['country'].strip()
            has_books = author['other_books'] and author['other_books'].strip()

            if has_short_bio and has_long_bio and has_country and has_books:
                print(f"\nSkipping: {author['name']} (already has all data)")
                self.stats['skipped'] += 1
            else:
                # Show which fields are missing
                missing = []
                if not has_short_bio:
                    missing.append('short_bio')
                if not has_long_bio:
                    missing.append('long_bio')
                if not has_country:
                    missing.append('country')
                if not has_books:
                    missing.append('books')

                if missing:
                    print(f"\nQueuing: {author['name']} (missing: {', '.join(missing)})")

                authors_to_process.append(author)

        print(f"\n{'='*60}")
        print(f"Found {len(authors)} total authors in database")
        print(f"Processing {len(authors_to_process)} authors without complete bios")
        print(f"Batch size: {self.batch_size}")
        print(f"{'='*60}")

        if not authors_to_process:
            print("\nNo authors to process!")
            return

        # Process in batches
        for i in range(0, len(authors_to_process), self.batch_size):
            batch = authors_to_process[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(authors_to_process) + self.batch_size - 1) // self.batch_size

            print(f"\n{'='*60}")
            print(f"BATCH {batch_num}/{total_batches}")
            print(f"{'='*60}")

            # Get author names for this batch
            author_names = [author['name'] for author in batch]

            # Generate bios for batch
            batch_bios = self.generate_batch_bios(author_names)

            # Update each author in the batch
            for author in batch:
                author_name = author['name']
                author_id = author['id']

                # Get bio data for this author (try exact match first, then case-insensitive)
                bio_data = batch_bios.get(author_name)
                if not bio_data:
                    # Try case-insensitive match
                    for key in batch_bios.keys():
                        if key.lower() == author_name.lower():
                            bio_data = batch_bios[key]
                            break

                if bio_data:
                    self.populate_author(author_name, author_id, bio_data)
                else:
                    print(f"\n  ✗ No bio data returned for: {author_name}")
                    self.stats['failed'] += 1
                    self.stats['total'] += 1

            # Rate limiting between batches
            if i + self.batch_size < len(authors_to_process):
                print(f"\n→ Waiting 6 seconds before next batch...")
                time.sleep(6)

        # Print statistics
        self.print_statistics()

    def populate_single_author(self, author_name: str):
        """Populate bio for a single author by name"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name FROM authors WHERE name = ?", (author_name,))
        author = cursor.fetchone()
        conn.close()

        if not author:
            print(f"Error: Author '{author_name}' not found in database")
            return False

        # Generate bio for single author (batch of 1)
        batch_bios = self.generate_batch_bios([author['name']])

        if author['name'] in batch_bios:
            return self.populate_author(author['name'], author['id'], batch_bios[author['name']])
        else:
            print(f"Failed to generate bio for {author['name']}")
            return False

    def print_statistics(self):
        """Print summary statistics"""
        print("\n" + "=" * 60)
        print("SUMMARY STATISTICS")
        print("=" * 60)
        print(f"Total authors processed: {self.stats['total']}")
        print(f"  ✓ Successful: {self.stats['successful']}")
        print(f"  ✗ Failed: {self.stats['failed']}")
        print(f"  ⊘ Skipped (already has bio): {self.stats['skipped']}")

        if self.stats['total'] > 0:
            success_rate = (self.stats['successful'] / self.stats['total']) * 100
            print(f"\nSuccess rate: {success_rate:.1f}%")

        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Populate author biographies using LLM batch generation'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating database'
    )
    parser.add_argument(
        '--author',
        type=str,
        help='Populate single author by name'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=25,
        help='Number of authors to process in each batch (default: 25)'
    )

    args = parser.parse_args()

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made to database")
        print("=" * 60)
        print()

    generator = AuthorBioGenerator(dry_run=args.dry_run, batch_size=args.batch_size)

    if args.author:
        generator.populate_single_author(args.author)
        generator.print_statistics()
    else:
        generator.populate_all_authors()


if __name__ == '__main__':
    main()
