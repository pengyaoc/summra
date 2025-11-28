#!/usr/bin/env python3
"""
Batch generate Gemini TTS audio for book summaries

This script finds all books that don't have Gemini-generated summary audio
and generates them sequentially while respecting the Gemini API rate limits.

The free tier allows 3 requests per minute, so we wait 20 seconds between each request.

Usage:
    # Check what's missing (dry run)
    python scripts/generate_gemini_audio_batch_offline.py --summary-type concise --dry-run
    python scripts/generate_gemini_audio_batch_offline.py --summary-type medium --dry-run

    # Generate missing audio for all books
    python scripts/generate_gemini_audio_batch_offline.py --summary-type concise
    python scripts/generate_gemini_audio_batch_offline.py --summary-type medium

    # Generate audio for a specific book
    python scripts/generate_gemini_audio_batch_offline.py --summary-type medium --book-id 46
"""

import sys
import time
import argparse
import wave
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from models import Database
from gemini_tts_handler import GeminiTTSHandler
import tts_utils


def find_books_without_audio(db: Database, summary_type: str) -> list:
    """Find all books that have summaries but no audio file on disk

    Args:
        db: Database instance
        summary_type: 'concise' or 'medium'

    Returns:
        List of dicts with book info: {book_id, title, author, summary_id}
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    # Query for books with specified summary type
    query = """
    SELECT
        b.id,
        b.title,
        b.author,
        s.id as summary_id
    FROM books b
    INNER JOIN summaries s ON b.id = s.book_id AND s.summary_type = ?
    ORDER BY b.title
    """

    cursor.execute(query, (summary_type,))
    results = cursor.fetchall()

    books = []
    # Check if audio file exists on disk for each book
    audio_dir = project_root / "frontend" / "static" / "audio"
    for row in results:
        book_id = row[0]
        audio_path = audio_dir / f"book_{book_id}_{summary_type}_gemini.wav"

        # Only include books that don't have audio file on disk
        if not audio_path.exists():
            books.append({
                'book_id': book_id,
                'title': row[1],
                'author': row[2],
                'summary_id': row[3]
            })

    return books


def generate_audio_for_book(db: Database, tts_handler: GeminiTTSHandler,
                            book: dict, summary_type: str, dry_run: bool = False) -> bool:
    """Generate audio for a single book's summary

    Args:
        db: Database instance
        tts_handler: GeminiTTSHandler instance
        book: Book info dict
        summary_type: 'concise' or 'medium'
        dry_run: If True, don't actually generate audio

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Processing: {book['title']} by {book['author']}")
    print(f"Book ID: {book['book_id']}, Summary ID: {book['summary_id']}")
    print(f"{'='*80}\n")

    # Get summary from database
    summary = db.get_summary(book['book_id'], summary_type)
    if not summary:
        print(f"❌ No {summary_type} summary found for book ID {book['book_id']}")
        return False

    # Get cleaned text
    print(f"Original content: {len(summary['content'])} characters")
    cleaned_text = tts_utils.clean_text_for_speech(summary['content'])
    print(f"Cleaned content: {len(cleaned_text)} characters")

    # Calculate word count
    word_count = len(cleaned_text.split())
    print(f"Word count: {word_count}")

    # Estimate tokens
    estimated_tokens = tts_handler.estimate_tokens(cleaned_text)
    print(f"Estimated tokens: {estimated_tokens}")

    if dry_run:
        print(f"\n[DRY RUN] Would generate audio with ID: book_{book['book_id']}_{summary_type}")
        print(f"[DRY RUN] Cleaned text preview (first 500 chars):\n{cleaned_text[:500]}")
        return True

    # Generate audio
    audio_id = f"book_{book['book_id']}_{summary_type}"

    try:
        audio_path = tts_handler.generate_audio(
            text=cleaned_text,
            audio_id=audio_id
        )

        if audio_path:
            print(f"✅ Generated audio: {audio_path}")

            # Calculate duration and save to database
            try:
                with wave.open(audio_path, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    duration = frames / float(rate)

                # Save to database
                db.add_audio_file(
                    summary_id=book['summary_id'],
                    chapter_id=None,
                    audio_path=audio_path,
                    duration=duration
                )
                print(f"✅ Saved audio file to database (duration: {duration:.2f}s)")
            except Exception as db_error:
                print(f"⚠️  Warning: Failed to save to database: {db_error}")
                # Don't fail the whole operation if database save fails

            return True
        else:
            print(f"❌ Failed to generate audio")
            return False

    except Exception as e:
        print(f"❌ Error generating audio: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Batch generate Gemini TTS audio for book summaries'
    )
    parser.add_argument(
        '--summary-type',
        required=True,
        choices=['concise', 'medium'],
        help='Type of summary to generate audio for (required)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually generating audio'
    )
    parser.add_argument(
        '--voice',
        default='Kore',
        choices=['Puck', 'Charon', 'Kore', 'Fenrir', 'Aoede', 'Sulafat'],
        help='Voice to use for TTS (default: Kore)'
    )
    parser.add_argument(
        '--delay',
        type=int,
        default=20,
        help='Delay in seconds between requests (default: 20 for 3 req/min limit)'
    )
    parser.add_argument(
        '--book-id',
        type=int,
        help='Process only this specific book ID (optional)'
    )

    args = parser.parse_args()

    summary_type = args.summary_type
    summary_type_display = summary_type.capitalize()

    print("="*80)
    print(f"Batch Generate Gemini TTS Audio for {summary_type_display} Summaries")
    print("="*80)

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No audio will be generated\n")

    # Initialize database and TTS handler
    print("\nInitializing database...")
    db = Database()

    print("Initializing Gemini TTS handler...")
    tts_handler = GeminiTTSHandler(voice=args.voice)
    print(f"Using voice: {args.voice}")
    print(f"Delay between requests: {args.delay} seconds")

    # Find books without audio
    if args.book_id:
        # Process only the specified book
        print(f"\nProcessing specific book ID: {args.book_id}")

        # Get book info
        book = db.get_book(args.book_id)
        if not book:
            print(f"❌ Book with ID {args.book_id} not found")
            sys.exit(1)

        # Get summary info
        summary = db.get_summary(args.book_id, summary_type)
        if not summary:
            print(f"❌ {summary_type.capitalize()} summary not found for book ID {args.book_id}")
            sys.exit(1)

        # Check if audio already exists
        audio_dir = project_root / "frontend" / "static" / "audio"
        audio_path = audio_dir / f"book_{args.book_id}_{summary_type}_gemini.wav"

        if audio_path.exists() and not args.dry_run:
            print(f"⚠️  Audio file already exists: {audio_path}")
            print("Skipping generation (delete file first if you want to regenerate)")
            return

        books = [{
            'book_id': args.book_id,
            'title': book['title'],
            'author': book['author'],
            'summary_id': summary['id']
        }]

        print(f"\nProcessing: {book['title']} by {book['author']}")
    else:
        # Find all books without audio
        print(f"\nFinding books without Gemini {summary_type} summary audio...")
        books = find_books_without_audio(db, summary_type)

        if not books:
            print(f"\n✅ All books with {summary_type} summaries already have audio!")
            return

        print(f"\nFound {len(books)} book(s) without audio:\n")
        for i, book in enumerate(books, 1):
            print(f"  {i}. {book['title']} by {book['author']}")

    if args.dry_run:
        print("\n[DRY RUN] Would process these books with delays...")
        for i, book in enumerate(books, 1):
            generate_audio_for_book(db, tts_handler, book, summary_type, dry_run=True)
            if i < len(books):
                print(f"\n[DRY RUN] Would wait {args.delay} seconds before next request...")
        print("\n[DRY RUN] Complete!")
        return

    # Process each book sequentially
    print(f"\nStarting sequential audio generation...")
    print(f"Rate limit: 3 requests per minute (waiting {args.delay}s between requests)\n")

    successful = 0
    failed = 0

    for i, book in enumerate(books, 1):
        print(f"\n{'='*80}")
        print(f"Progress: {i}/{len(books)}")
        print(f"{'='*80}")

        success = generate_audio_for_book(db, tts_handler, book, summary_type, dry_run=False)

        if success:
            successful += 1
        else:
            failed += 1

        # Wait before next request (except for the last one)
        if i < len(books):
            print(f"\n⏳ Waiting {args.delay} seconds before next request...")
            print(f"   (Rate limit: 3 requests per minute)")
            time.sleep(args.delay)

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total books processed: {len(books)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"{'='*80}\n")

    if failed > 0:
        print("⚠️  Some books failed to generate audio. Check the output above for details.")
        sys.exit(1)
    else:
        print("🎉 All audio files generated successfully!")


if __name__ == "__main__":
    main()
