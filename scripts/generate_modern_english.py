#!/usr/bin/env python3
"""
Generate Modern English (No-Fear) Versions of Book Chapters

This script reads chapter text from the database and generates modern English translations
that preserve the original meaning while using contemporary language and simpler sentence structures.

The translation process:
1. Reads full chapter text from the database
2. Sends it to Gemini API with specialized prompt
3. Preserves exact sentence and paragraph structure
4. Modernizes vocabulary and simplifies complex syntax
5. Maintains the author's intended meaning and tone

Usage:
    # Generate modern English for a single chapter
    python generate_modern_english.py --book-id 1 --chapter 5

    # Generate for multiple chapters
    python generate_modern_english.py --book-id 1 --chapters "1,2,3"

    # Generate for all chapters in a book
    python generate_modern_english.py --book-id 1 --all-chapters

    # Dry run (preview only, no API calls)
    python generate_modern_english.py --book-id 1 --chapter 5 --dry-run

    # Batch process with custom batch size (up to 5 chapters per API call)
    python generate_modern_english.py --book-id 1 --all-chapters --batch-size 3
"""

import sys
import os
import argparse
import sqlite3
import re
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

import config
from backend.models import Database

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai package not found. Install with: pip install google-genai")
    sys.exit(1)


class ModernEnglishGenerator:
    """Generate modern English translations of classic literature chapters"""

    # Constants
    MAX_CHAPTERS_PER_BATCH = 10  # Maximum chapters to process in a single API call (matches generate_summaries.py)
    MAX_BATCH_CHARS = 60000     # Maximum characters per batch
    MAX_OUTPUT_TOKENS = 65535    # Maximum output tokens

    def __init__(self, api_key: str = None, model_name: str = None):
        """Initialize generator with API credentials

        Args:
            api_key: Google AI API key (defaults to config.GEMINI_API_KEY)
            model_name: Gemini model to use for generation (defaults to
                config.PLAIN_TEXT_MODEL — Flash-Lite for bulk rewrites)
        """
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("Gemini API key not found. Set GEMINI_API_KEY in environment or config.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name or config.PLAIN_TEXT_MODEL
        self.db = Database()

    def build_single_chapter_prompt(self, book_title: str, book_author: str,
                                    chapter_title: str, chapter_text: str) -> str:
        """Build the prompt for single chapter modern English translation

        Args:
            book_title: Title of the book
            book_author: Author name
            chapter_title: Title of the chapter
            chapter_text: Full original text of the chapter

        Returns:
            Complete prompt string for translation
        """

        prompt = f"""You are a literary translator specializing in creating "No-Fear" modern English versions of classic literature. Your task is to translate the following chapter from "{book_title}" by {book_author} into contemporary English.

CHAPTER: {chapter_title}

CRITICAL TRANSLATION RULES:

1. PRESERVE EXACT STRUCTURE:
   - Do NOT add or remove ANY sentences
   - Do NOT add or remove ANY paragraphs
   - Do NOT merge or split paragraphs
   - CRITICAL: Do NOT split a single paragraph into multiple paragraphs
   - CRITICAL: Do NOT merge multiple paragraphs into one
   - CRITICAL: Do NOT skip or omit any paragraph - every paragraph must be translated
   - CRITICAL: Do NOT skip or omit any sentence - every sentence must be translated
   - CRITICAL: Each original sentence must remain as ONE sentence in the translation
   - Maintain the exact same number of sentences and paragraphs as the original
   - Each original paragraph must remain as ONE paragraph in the translation
   - Keep dialogue markers and formatting exactly as they appear

2. MODERNIZE LANGUAGE:
   - Replace archaic words with modern equivalents (e.g., "thou" → "you", "doth" → "does")
   - Simplify complex Victorian/classical sentence structures
   - Use contemporary vocabulary while preserving literary quality
   - Make implicit meanings explicit when helpful for modern readers
   - Use PLAIN ENGLISH: avoid difficult, complex, or obscure words
   - Choose simple, common words over sophisticated vocabulary
   - Aim for accessibility while maintaining the story's essence

3. PRESERVE MEANING & TONE:
   - Keep the author's intended meaning completely intact
   - Maintain the emotional tone and atmosphere
   - Preserve literary devices like metaphors, imagery, and symbolism
   - Keep character voices and dialogue styles distinctive
   - Do not modernize proper nouns, character names, or place names

4. SIMPLIFY SYNTAX:
   - Break complex nested clauses into clearer structures
   - Reorder inverted sentence structures to standard modern order
   - Clarify ambiguous pronoun references
   - Make passive voice active where it improves clarity

5. QUALITY STANDARDS:
   - The result should read naturally to a modern audience
   - Target middle school reading level - use simple, everyday language
   - Replace difficult words with common alternatives
   - Preserve the literary merit and artistry of the original through clear storytelling
   - Prioritize clarity and accessibility over sophisticated vocabulary

EXAMPLE TRANSFORMATIONS:

Original: "It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife."
Modern: "Everyone knows that a wealthy single man must be looking for a wife."

Original: "I had scarcely laid the first tier of my masonry when I discovered that the intoxication of Fortunato had in a great measure worn off."
Modern: "I had barely finished the first layer of bricks when I realized that Fortunato was becoming much less drunk."

Original: "Methinks I see these things with parted eye, when every thing seems double."
Modern: "I think I'm seeing double right now—everything appears twice."

ORIGINAL CHAPTER TEXT:

{chapter_text}

IMPORTANT OUTPUT REQUIREMENTS:
- Output ONLY the translated text
- Do NOT include any preamble, commentary, or explanations
- Do NOT include markers like "Modern English Version:" or "Translation:"
- Begin immediately with the translated text
- Preserve all paragraph breaks exactly as shown in the original

Provide the complete modern English translation of this chapter now, following all rules above."""

        return prompt

    def build_bulk_translation_prompt(self, book_title: str, book_author: str,
                                     chapters_batch: List[Tuple[int, str, str]]) -> str:
        """Build prompt for bulk translation of multiple chapters

        Args:
            book_title: Title of the book
            book_author: Author name
            chapters_batch: List of (chapter_num, chapter_title, chapter_text) tuples

        Returns:
            Complete prompt string for batch translation
        """
        # Build chapter sections with sequential numbering
        chapters_text = []
        chapter_info = []

        for idx, (chapter_num, chapter_title, chapter_text) in enumerate(chapters_batch, start=1):
            chapter_info.append(f"  - Chapter {idx} (Book Chapter {chapter_num}: {chapter_title})")
            chapter_section = f"CHAPTER {idx} (Book Chapter {chapter_num}: {chapter_title})\n\n{chapter_text}"
            chapters_text.append(chapter_section)

        prompt = f"""You are a literary translator specializing in creating "No-Fear" modern English versions of classic literature. Your task is to translate the following {len(chapters_batch)} chapters from "{book_title}" by {book_author} into contemporary English.

CHAPTERS TO TRANSLATE:
{chr(10).join(chapter_info)}

CRITICAL TRANSLATION RULES:

1. PRESERVE EXACT STRUCTURE:
   - Do NOT add or remove ANY sentences in any chapter
   - Do NOT add or remove ANY paragraphs in any chapter
   - Do NOT merge or split paragraphs
   - Maintain the exact same number of sentences and paragraphs as the original for EACH chapter
   - Keep dialogue markers and formatting exactly as they appear

2. MODERNIZE LANGUAGE:
   - Replace archaic words with modern equivalents (e.g., "thou" → "you", "doth" → "does")
   - Simplify complex Victorian/classical sentence structures
   - Use contemporary vocabulary while preserving literary quality
   - Make implicit meanings explicit when helpful for modern readers
   - Use PLAIN ENGLISH: avoid difficult, complex, or obscure words
   - Choose simple, common words over sophisticated vocabulary
   - Aim for accessibility while maintaining the story's essence

3. PRESERVE MEANING & TONE:
   - Keep the author's intended meaning completely intact
   - Maintain the emotional tone and atmosphere
   - Preserve literary devices like metaphors, imagery, and symbolism
   - Keep character voices and dialogue styles distinctive
   - Do not modernize proper nouns, character names, or place names

4. SIMPLIFY SYNTAX:
   - Break complex nested clauses into clearer structures
   - Reorder inverted sentence structures to standard modern order
   - Clarify ambiguous pronoun references
   - Make passive voice active where it improves clarity

5. QUALITY STANDARDS:
   - The result should read naturally to a modern audience
   - Target middle school reading level - use simple, everyday language
   - Replace difficult words with common alternatives
   - Preserve the literary merit and artistry of the original through clear storytelling
   - Prioritize clarity and accessibility over sophisticated vocabulary

IMPORTANT OUTPUT FORMAT:
Format your response EXACTLY as shown below. Use sequential chapter numbers (1, 2, 3...) in your markers:

### CHAPTER 1
[Complete modern English translation of chapter 1, preserving all paragraph breaks]

### END CHAPTER 1

### CHAPTER 2
[Complete modern English translation of chapter 2, preserving all paragraph breaks]

### END CHAPTER 2

... and so on for all {len(chapters_batch)} chapters.

CHAPTERS TO TRANSLATE:

{"=" * 80}
{chr(10).join(chapters_text)}
{"=" * 80}

Now provide modern English translations for all {len(chapters_batch)} chapters above, following the exact format and rules specified. Use sequential numbers (1, 2, 3...) in the ### CHAPTER markers."""

        return prompt

    def parse_bulk_response(self, response_text: str, chapters_batch: List[Tuple[int, str, str]]) -> Dict[int, str]:
        """Parse bulk translation response into individual chapters

        Args:
            response_text: Raw API response text
            chapters_batch: Original batch of chapters

        Returns:
            Dictionary mapping chapter_number -> modern_english_text
        """
        translations = {}

        # Create index mapping (sequential index -> actual chapter number)
        index_to_chapter = {idx: chapter_num for idx, (chapter_num, _, _) in enumerate(chapters_batch, start=1)}

        # Pattern to match chapter sections: ### CHAPTER N ... ### END CHAPTER N
        pattern = r'###\s*CHAPTER\s+(\d+)\s*\n(.*?)(?=###\s*END\s+CHAPTER\s+\d+|$)'

        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)

        for match in matches:
            index_str = match[0].strip()
            translation_text = match[1].strip()

            # Convert index to integer
            index = int(index_str)

            # Remove the END CHAPTER marker if present
            translation_text = re.sub(r'###\s*END\s+CHAPTER\s+\d+\s*$', '', translation_text, flags=re.IGNORECASE).strip()

            # Map index back to actual chapter number
            if index in index_to_chapter:
                chapter_num = index_to_chapter[index]
                translations[chapter_num] = translation_text
            else:
                print(f"  ⚠️  Warning: Parsed index {index} not found in index_to_chapter mapping")

        # Verify we got all expected chapters
        expected_chapters = set(index_to_chapter.values())
        missing = expected_chapters - set(translations.keys())
        if missing:
            print(f"  ⚠️  Warning: Missing translations for chapters: {sorted(missing)}")

        return translations

    def generate_bulk_translation(self, book_id: int, chapters_batch: List[Tuple[int, str, str]],
                                 dry_run: bool = False) -> Dict[int, str]:
        """Generate modern English translations for multiple chapters in a single API call

        Args:
            book_id: Database ID of the book
            chapters_batch: List of (chapter_num, chapter_title, chapter_text) tuples
            dry_run: If True, only preview without making API calls

        Returns:
            Dictionary mapping chapter_number -> modern_english_text
        """
        # Get book metadata
        book = self.db.get_book(book_id)
        if not book:
            print(f"Error: Book with ID {book_id} not found")
            return {}

        chapter_numbers = [ch[0] for ch in chapters_batch]

        # Build prompt
        prompt = self.build_bulk_translation_prompt(
            book_title=book['title'],
            book_author=book['author'],
            chapters_batch=chapters_batch
        )

        # Calculate statistics
        total_words = sum(len(ch[2].split()) for ch in chapters_batch)
        total_chars = sum(len(ch[2]) for ch in chapters_batch)

        # Preview mode
        if dry_run:
            print(f"\n{'='*80}")
            print(f"DRY RUN: Bulk Modern English Generation")
            print(f"{'='*80}")
            print(f"Book: {book['title']} by {book['author']}")
            print(f"Chapters: {chapter_numbers}")
            print(f"Total input: {total_words:,} words (~{total_chars:,} chars)")
            print(f"Prompt length: {len(prompt):,} characters")
            print(f"\nPROMPT PREVIEW (first 1500 chars):")
            print(f"{'-'*80}")
            print(prompt[:1500])
            print(f"\n... [truncated, {len(prompt) - 1500:,} chars omitted]" if len(prompt) > 1500 else "")
            print(f"{'-'*80}")
            return {ch_num: f"[DRY RUN] Translation for chapter {ch_num}" for ch_num in chapter_numbers}

        # Make API call with retry logic
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Generating bulk modern English for {len(chapters_batch)} chapters: {chapter_numbers}")
        print(f"  Book: {book['title']} by {book['author']}")
        print(f"  Input: {total_words:,} words (~{total_chars:,} chars)")

        max_retries = 2
        retry_delay = 30  # seconds

        for attempt in range(max_retries + 1):
            response_text = ""
            error_msg = None
            start_time = time.time()

            try:
                if attempt > 0:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Retry attempt {attempt}/{max_retries}...")
                    time.sleep(retry_delay)

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,  # Lower temperature for more consistent translations
                        top_p=0.95,
                        max_output_tokens=self.MAX_OUTPUT_TOKENS,
                    )
                )

                response_text = response.text.strip()
                generation_time = time.time() - start_time

                # Parse the response
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Parsing response...")
                translations = self.parse_bulk_response(response_text, chapters_batch)

                # Validation checks for each chapter
                for chapter_num, modern_text in translations.items():
                    # Find original text
                    original_text = None
                    for ch_num, ch_title, ch_text in chapters_batch:
                        if ch_num == chapter_num:
                            original_text = ch_text
                            break

                    if original_text:
                        original_paragraphs = len(original_text.strip().split('\n\n'))
                        modern_paragraphs = len(modern_text.strip().split('\n\n'))

                        print(f"  Chapter {chapter_num}: {len(modern_text.split()):,} words, Paragraphs: Orig={original_paragraphs}, Modern={modern_paragraphs}")

                        # Warn if structure changed significantly
                        if abs(original_paragraphs - modern_paragraphs) > 2:
                            print(f"    ⚠️  WARNING: Paragraph count mismatch for chapter {chapter_num}")

                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Bulk generation complete ({len(translations)}/{len(chapters_batch)} chapters)")

                # Save LLM log (success case)
                self._save_llm_log(
                    book_id=book['id'],
                    book_title=book['title'],
                    book_author=book['author'],
                    chapters_batch=chapters_batch,
                    prompt=prompt,
                    response_text=response_text,
                    success=True,
                    generation_time=generation_time,
                    parsed_count=len(translations)
                )

                return translations

            except Exception as e:
                generation_time = time.time() - start_time
                error_msg = str(e)

                if attempt < max_retries:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Error on attempt {attempt + 1}: {e}")
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Will retry in {retry_delay} seconds...")
                    continue
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error generating bulk modern English after {max_retries + 1} attempts: {e}")

                    # Save LLM log (error case) only for final failure
                    self._save_llm_log(
                        book_id=book['id'],
                        book_title=book['title'],
                        book_author=book['author'],
                        chapters_batch=chapters_batch,
                        prompt=prompt,
                        response_text=response_text,
                        success=False,
                        error_msg=error_msg,
                        generation_time=generation_time,
                        parsed_count=0
                    )

                    return {}

    def generate_modern_english_chapter(self, book_id: int, chapter_number: int,
                                       dry_run: bool = False) -> Optional[str]:
        """Generate modern English version for a single chapter

        Args:
            book_id: Database ID of the book
            chapter_number: Chapter number to translate
            dry_run: If True, only preview the prompt without making API calls

        Returns:
            Modern English translation text, or None if failed
        """
        # Get book metadata
        book = self.db.get_book(book_id)
        if not book:
            print(f"Error: Book with ID {book_id} not found")
            return None

        # Get chapter data
        chapter = self.db.get_chapter(book_id, chapter_number)
        if not chapter:
            print(f"Error: Chapter {chapter_number} not found for book ID {book_id}")
            return None

        chapter_text = chapter.get('chapter_text')
        if not chapter_text:
            print(f"Error: Chapter {chapter_number} has no text stored in database")
            return None

        chapter_title = chapter.get('chapter_title', f"Chapter {chapter_number}")

        # Use bulk translation with single chapter
        chapters_batch = [(chapter_number, chapter_title, chapter_text)]
        translations = self.generate_bulk_translation(book_id, chapters_batch, dry_run)

        return translations.get(chapter_number)

    def generate_batch(self, book_id: int, chapter_numbers: List[int],
                      batch_size: int = 3, dry_run: bool = False,
                      save_to_db: bool = True) -> Dict[int, str]:
        """Generate modern English versions for multiple chapters using batch processing

        Args:
            book_id: Database ID of the book
            chapter_numbers: List of chapter numbers to process
            batch_size: Number of chapters to process per API call (max: MAX_CHAPTERS_PER_BATCH)
            dry_run: If True, only preview without making API calls
            save_to_db: If True, save translations to database (default: True)

        Returns:
            Dictionary mapping chapter_number -> modern_english_text
        """
        # Validate batch size
        if batch_size > self.MAX_CHAPTERS_PER_BATCH:
            print(f"Warning: batch_size {batch_size} exceeds maximum {self.MAX_CHAPTERS_PER_BATCH}, using {self.MAX_CHAPTERS_PER_BATCH}")
            batch_size = self.MAX_CHAPTERS_PER_BATCH

        all_results = {}

        print(f"\n{'='*80}")
        print(f"BATCH GENERATION: {len(chapter_numbers)} chapters")
        print(f"Chapters: {chapter_numbers}")
        print(f"Database saving: {'Enabled' if save_to_db else 'Disabled'}")
        print(f"{'='*80}")

        # Fetch all chapter data first
        chapters_to_process = []
        for chapter_num in chapter_numbers:
            chapter = self.db.get_chapter(book_id, chapter_num)
            if not chapter:
                print(f"  ⚠️  Warning: Chapter {chapter_num} not found, skipping")
                continue

            chapter_text = chapter.get('chapter_text')
            if not chapter_text:
                print(f"  ⚠️  Warning: Chapter {chapter_num} has no text, skipping")
                continue

            chapter_title = chapter.get('chapter_title', f"Chapter {chapter_num}")
            chapters_to_process.append((chapter_num, chapter_title, chapter_text))

        if not chapters_to_process:
            print("No valid chapters to process")
            return all_results

        # Smart batching: respect both MAX_CHAPTERS_PER_BATCH and MAX_BATCH_CHARS
        # This is similar to generate_summaries.py batching logic
        batches = []
        current_batch = []
        current_batch_chars = 0

        for chapter_num, chapter_title, chapter_text in chapters_to_process:
            chapter_chars = len(chapter_text)

            # If adding this chapter would exceed char limit or chapter limit, start new batch
            if current_batch and (current_batch_chars + chapter_chars > self.MAX_BATCH_CHARS or
                                 len(current_batch) >= batch_size):
                batches.append(current_batch)
                current_batch = []
                current_batch_chars = 0

            current_batch.append((chapter_num, chapter_title, chapter_text))
            current_batch_chars += chapter_chars

        # Add last batch
        if current_batch:
            batches.append(current_batch)

        print(f"  Split into {len(batches)} batch(es) based on character limits and batch size")

        # Process each batch
        for batch_idx, batch in enumerate(batches, 1):
            batch_chars = sum(len(ch[2]) for ch in batch)
            batch_chapter_nums = [ch[0] for ch in batch]

            print(f"\n--- Batch {batch_idx}/{len(batches)}: Chapters {batch_chapter_nums[0]}-{batch_chapter_nums[-1]} ({len(batch)} chapters, ~{batch_chars:,} chars) ---")

            # Generate translations for this batch
            batch_results = self.generate_bulk_translation(book_id, batch, dry_run)

            # Save results
            for chapter_num, modern_text in batch_results.items():
                all_results[chapter_num] = modern_text

                if not dry_run:
                    # Save to file
                    self._save_preview(book_id, chapter_num, modern_text)

                    # Save to database
                    if save_to_db:
                        try:
                            self.db.update_chapter_modern_english(book_id, chapter_num, modern_text)
                            print(f"  💾 Saved to database: Chapter {chapter_num}")
                        except Exception as e:
                            print(f"  ⚠️  Database save failed for chapter {chapter_num}: {e}")

            # Small delay between batches to be respectful to API
            if batch_idx < len(batches) and not dry_run:
                import time
                print(f"  Waiting 3 seconds before next batch...")
                time.sleep(3)

        print(f"\n{'='*80}")
        print(f"BATCH COMPLETE: {len(all_results)}/{len(chapters_to_process)} chapters successful")
        if save_to_db and not dry_run:
            print(f"Database: {len(all_results)} chapters saved")
        print(f"{'='*80}")

        return all_results

    def _save_preview(self, book_id: int, chapter_number: int, modern_text: str):
        """Save modern English text to a preview file

        Args:
            book_id: Database ID of the book
            chapter_number: Chapter number
            modern_text: Modern English translation
        """
        # Create output directory
        output_dir = Path(__file__).parent.parent / "data" / "log" / "modern_english"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create filename
        filename = f"book_{book_id}_chapter_{chapter_number}_modern.txt"
        filepath = output_dir / filename

        # Write to file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(modern_text)
            print(f"  💾 Saved to: {filepath}")
        except Exception as e:
            print(f"  ⚠️  Could not save preview file: {e}")

    def _save_llm_log(self, book_id: int, book_title: str, book_author: str,
                     chapters_batch: List[Tuple[int, str, str]], prompt: str,
                     response_text: str, success: bool, error_msg: str = None,
                     generation_time: float = 0.0, parsed_count: int = 0):
        """Save full LLM request/response log for debugging and auditing

        Args:
            book_id: Database ID of the book
            book_title: Title of the book
            book_author: Author name
            chapters_batch: List of (chapter_num, chapter_title, chapter_text) tuples
            prompt: Full prompt sent to LLM
            response_text: Raw response from LLM
            success: Whether the API call succeeded
            error_msg: Error message if failed
            generation_time: Time taken for generation in seconds
            parsed_count: Number of chapters successfully parsed from response
        """
        # Create logs directory
        logs_dir = Path(__file__).parent.parent / "data" / "log" / "gemini_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp and filename
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")

        chapter_nums = [ch[0] for ch in chapters_batch]
        if len(chapter_nums) == 1:
            chapter_range = str(chapter_nums[0])
        else:
            chapter_range = f"{min(chapter_nums)}-{max(chapter_nums)}"

        filename = f"{timestamp_str}_book_{book_id}_chapters_{chapter_range}.txt"
        filepath = logs_dir / filename

        # Build log content
        log_content = f"""{'='*80}
MODERN ENGLISH GENERATION LOG
{'='*80}
Timestamp: {timestamp.strftime("%Y-%m-%d %H:%M:%S")}
Book: {book_title} (ID: {book_id}) by {book_author}
Chapters: {chapter_nums}
Model: {self.model_name}
Batch Size: {len(chapters_batch)}
Temperature: 0.3
Max Output Tokens: {self.MAX_OUTPUT_TOKENS}

{'='*80}
PROMPT
{'='*80}
{prompt}

{'='*80}
RAW RESPONSE
{'='*80}
{response_text if response_text else '[NO RESPONSE - ERROR OCCURRED]'}

{'='*80}
METADATA
{'='*80}
Success: {success}
Response Length: {len(response_text):,} characters
Chapters Parsed: {parsed_count}/{len(chapters_batch)}
Generation Time: {generation_time:.2f} seconds
"""

        if error_msg:
            log_content += f"\nERROR:\n{error_msg}\n"

        log_content += f"{'='*80}\n"

        # Write to file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(log_content)
            print(f"  📋 LLM log saved: {filepath}")
        except Exception as e:
            print(f"  ⚠️  Could not save LLM log: {e}")


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description="Generate modern English (no-fear) versions of classic literature chapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate modern English for chapter 5 of book 1
  %(prog)s --book-id 1 --chapter 5

  # Generate for multiple chapters (comma-separated)
  %(prog)s --book-id 1 --chapters "1,2,3,4,5"

  # Generate for all chapters with batch size 3
  %(prog)s --book-id 1 --all-chapters --batch-size 3

  # Dry run (preview only)
  %(prog)s --book-id 1 --chapter 5 --dry-run

  # Use specific model
  %(prog)s --book-id 1 --chapter 5 --model gemini-2.0-flash-exp
        """
    )

    parser.add_argument('--book-id', type=int, required=True,
                       help='Database ID of the book')

    # Chapter selection (mutually exclusive)
    chapter_group = parser.add_mutually_exclusive_group(required=True)
    chapter_group.add_argument('--chapter', type=int,
                              help='Single chapter number to process')
    chapter_group.add_argument('--chapters', type=str,
                              help='Comma-separated list of chapter numbers (e.g., "1,2,3")')
    chapter_group.add_argument('--all-chapters', action='store_true',
                              help='Process all chapters in the book')

    parser.add_argument('--dry-run', action='store_true',
                       help='Preview prompts without making API calls')
    parser.add_argument('--model', type=str, default=config.PLAIN_TEXT_MODEL,
                       help=f'Gemini model to use (default: {config.PLAIN_TEXT_MODEL})')
    parser.add_argument('--batch-size', type=int, default=5,
                       help=f'Number of chapters to process per API call (default: 5, max: {ModernEnglishGenerator.MAX_CHAPTERS_PER_BATCH})')
    parser.add_argument('--save-to-db', action='store_true', default=True,
                       help='Save translations to database (default: True)')
    parser.add_argument('--no-save-to-db', dest='save_to_db', action='store_false',
                       help='Do not save translations to database')

    args = parser.parse_args()

    # Initialize generator
    try:
        generator = ModernEnglishGenerator(model_name=args.model)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Determine which chapters to process
    chapter_numbers = []

    if args.chapter:
        chapter_numbers = [args.chapter]
    elif args.chapters:
        try:
            chapter_numbers = [int(x.strip()) for x in args.chapters.split(',')]
        except ValueError:
            print("Error: --chapters must be comma-separated integers (e.g., '1,2,3')")
            sys.exit(1)
    elif args.all_chapters:
        # Get all chapters for the book
        db = Database()
        chapters = db.get_chapters_metadata(args.book_id)
        if not chapters:
            print(f"Error: No chapters found for book ID {args.book_id}")
            sys.exit(1)
        chapter_numbers = [ch['chapter_number'] for ch in chapters]
        print(f"Found {len(chapter_numbers)} chapters in book {args.book_id}")

    # Generate modern English
    generator.generate_batch(
        book_id=args.book_id,
        chapter_numbers=chapter_numbers,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        save_to_db=args.save_to_db
    )


if __name__ == '__main__':
    main()
