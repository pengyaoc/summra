#!/usr/bin/env python3
"""
Offline TTS generation using Google Gemini 2.5 Flash TTS API

This script generates audio files for book summaries and chapters using the Gemini TTS API.
The generated audio files are stored in the same location as VITS TTS files and can be
played through the existing UI.

Usage:
    # Generate TTS for specific summary types
    python scripts/audio/generate_offline_tts.py --book "The Time Machine" --summaries concise medium

    # Generate TTS for comprehensive summary chapters
    python scripts/audio/generate_offline_tts.py --book "Alice's Adventures in Wonderland" --comprehensive-chapters 1-5

    # Generate TTS for all summaries of a book
    python scripts/audio/generate_offline_tts.py --book "Pride and Prejudice" --all-summaries

    # Specify custom voice
    python scripts/audio/generate_offline_tts.py --book "The Odyssey" --summaries concise --voice Charon

Available voices: Puck, Charon, Kore, Fenrir, Aoede, Sulafat
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from models import Database
from gemini_tts_handler import GeminiTTSHandler
import tts_utils  # Shared TTS utilities


def parse_chapter_range(chapter_str: str) -> list:
    """Parse chapter range string like '1-5' or '1,3,5-7' into list of chapter numbers"""
    chapters = []
    for part in chapter_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            chapters.extend(range(start, end + 1))
        else:
            chapters.append(int(part))
    return sorted(set(chapters))


def generate_summary_audio(db: Database, tts_handler: GeminiTTSHandler,
                          book_id: int, summary_type: str, dry_run: bool = False) -> bool:
    """Generate audio for a specific summary type"""
    print(f"\n{'='*60}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Generating TTS for {summary_type} summary")
    print(f"{'='*60}\n")

    # Get summary from database
    summary = db.get_summary(book_id, summary_type)
    if not summary:
        print(f"No {summary_type} summary found for this book")
        return False

    # Check if audio already exists
    existing_audio = db.get_audio_file(summary_id=summary['id'])
    if existing_audio:
        print(f"Audio already exists: {existing_audio['audio_path']}")
        if not dry_run:
            return True

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
        print(f"\n{'-'*60}")
        print(f"CLEANED TEXT PREVIEW (first 500 chars):")
        print(f"{'-'*60}")
        print(cleaned_text[:500])
        if len(cleaned_text) > 500:
            print(f"... ({len(cleaned_text) - 500} more characters)")
        print(f"\n{'-'*60}")
        print(f"FULL CLEANED TEXT:")
        print(f"{'-'*60}")
        print(cleaned_text)
        print(f"{'-'*60}\n")
        print(f"[DRY RUN] Would generate audio with ID: book_{book_id}_{summary_type}")
        return True

    # Generate audio
    audio_id = f"book_{book_id}_{summary_type}"
    audio_path = tts_handler.generate_audio(summary['content'], audio_id=audio_id)

    if audio_path:
        # Store in database (duration can be calculated later if needed)
        db.add_audio_file(
            summary_id=summary['id'],
            chapter_id=None,
            audio_path=audio_path,
            duration=0.0  # Can be calculated from WAV file if needed
        )
        print(f"✓ Successfully generated audio for {summary_type} summary")
        return True
    else:
        print(f"✗ Failed to generate audio for {summary_type} summary")
        return False


def generate_chapter_audio(db: Database, tts_handler: GeminiTTSHandler,
                          book_id: int, chapter_numbers: list, dry_run: bool = False) -> dict:
    """Generate audio for specific chapters"""
    print(f"\n{'='*60}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Generating TTS for chapters: {chapter_numbers}")
    print(f"{'='*60}\n")

    # Get all chapters for the book
    all_chapters = db.get_chapters(book_id)
    chapters_to_process = [ch for ch in all_chapters if ch['chapter_number'] in chapter_numbers]

    if not chapters_to_process:
        print(f"No matching chapters found")
        return {"success": 0, "failed": 0, "skipped": 0}

    stats = {"success": 0, "failed": 0, "skipped": 0}

    for chapter in chapters_to_process:
        print(f"\nChapter {chapter['chapter_number']}: {chapter['chapter_title']}")

        # Check if audio already exists
        existing_audio = db.get_audio_file(chapter_id=chapter['id'])
        if existing_audio:
            print(f"  Audio already exists: {existing_audio['audio_path']}")
            if not dry_run:
                stats["skipped"] += 1
                continue

        # Get cleaned text
        print(f"  Original content: {len(chapter['summary'])} characters")
        cleaned_text = tts_utils.clean_text_for_speech(chapter['summary'])
        print(f"  Cleaned content: {len(cleaned_text)} characters")

        # Calculate word count
        word_count = len(cleaned_text.split())
        print(f"  Word count: {word_count}")

        # Estimate tokens
        estimated_tokens = tts_handler.estimate_tokens(cleaned_text)
        print(f"  Estimated tokens: {estimated_tokens}")

        if dry_run:
            print(f"\n  {'-'*58}")
            print(f"  CLEANED TEXT PREVIEW (first 300 chars):")
            print(f"  {'-'*58}")
            preview = cleaned_text[:300].replace('\n', '\n  ')
            print(f"  {preview}")
            if len(cleaned_text) > 300:
                print(f"  ... ({len(cleaned_text) - 300} more characters)")
            print(f"  {'-'*58}\n")
            print(f"  [DRY RUN] Would generate audio with ID: book_{book_id}_chapter_{chapter['chapter_number']}")
            stats["success"] += 1
            continue

        # Generate audio
        audio_id = f"book_{book_id}_chapter_{chapter['chapter_number']}"
        audio_path = tts_handler.generate_audio(chapter['summary'], audio_id=audio_id)

        if audio_path:
            # Store in database
            db.add_audio_file(
                summary_id=None,
                chapter_id=chapter['id'],
                audio_path=audio_path,
                duration=0.0
            )
            print(f"  ✓ Successfully generated audio")
            stats["success"] += 1
        else:
            print(f"  ✗ Failed to generate audio")
            stats["failed"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Generate offline TTS using Gemini 2.5 Flash TTS API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Required arguments
    parser.add_argument('--book', required=True,
                       help='Book title or ID')

    # Summary generation options
    parser.add_argument('--summaries', nargs='+',
                       choices=['concise', 'medium', 'comprehensive'],
                       help='Summary types to generate TTS for')

    parser.add_argument('--all-summaries', action='store_true',
                       help='Generate TTS for all available summaries')

    # Chapter generation options
    parser.add_argument('--comprehensive-chapters',
                       help='Chapter numbers for comprehensive summary (e.g., "1-5" or "1,3,5-7")')

    # Voice option
    parser.add_argument('--voice',
                       choices=['Puck', 'Charon', 'Kore', 'Fenrir', 'Aoede', 'Sulafat'],
                       help='Voice to use for TTS (default: Sulafat)')

    # Dry run option
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview cleaned content without making API calls or storing to database')

    args = parser.parse_args()

    # Default mode: generate concise summary if nothing specified
    if not any([args.summaries, args.all_summaries, args.comprehensive_chapters]):
        args.summaries = ['concise']
        print("No generation mode specified - using default mode (concise summary only)")

    # Initialize database
    db = Database()

    # Find book
    print(f"\nSearching for book: {args.book}")
    books = db.get_all_books()

    book = None
    # Try exact title match first
    for b in books:
        if b['title'].lower() == args.book.lower():
            book = b
            break

    # Try ID match
    if not book and args.book.isdigit():
        book = db.get_book(int(args.book))

    # Try partial title match
    if not book:
        for b in books:
            if args.book.lower() in b['title'].lower():
                book = b
                break

    if not book:
        print(f"ERROR: Book not found: {args.book}")
        print(f"\nAvailable books:")
        for b in books[:10]:
            print(f"  - {b['title']} (ID: {b['id']})")
        return 1

    print(f"Found book: {book['title']} by {book['author']} (ID: {book['id']})")

    # Initialize TTS handler
    print(f"\nInitializing Gemini TTS handler...")
    tts_handler = GeminiTTSHandler(voice=args.voice)

    # Generate audio for summaries
    if args.all_summaries:
        summary_types = ['concise', 'medium', 'comprehensive']
    else:
        summary_types = args.summaries or []

    success_count = 0
    for summary_type in summary_types:
        if generate_summary_audio(db, tts_handler, book['id'], summary_type, dry_run=args.dry_run):
            success_count += 1

    # Generate audio for chapters
    if args.comprehensive_chapters:
        try:
            chapter_numbers = parse_chapter_range(args.comprehensive_chapters)
            stats = generate_chapter_audio(db, tts_handler, book['id'], chapter_numbers, dry_run=args.dry_run)
            print(f"\nChapter generation summary:")
            print(f"  Success: {stats['success']}")
            print(f"  Failed: {stats['failed']}")
            print(f"  Skipped (already exists): {stats['skipped']}")
        except ValueError as e:
            print(f"ERROR: Invalid chapter range: {e}")
            return 1

    print(f"\n{'='*60}")
    print(f"TTS generation complete!")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
