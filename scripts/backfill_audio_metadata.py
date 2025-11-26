#!/usr/bin/env python3
"""
Backfill audio file metadata to database

This script finds all Gemini-generated concise summary audio files in the
frontend/static/audio directory and adds their metadata to the database.

Usage:
    python scripts/backfill_audio_metadata.py
    python scripts/backfill_audio_metadata.py --dry-run
"""

import sys
import wave
import argparse
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from models import Database


def find_gemini_audio_files(audio_dir: Path) -> list:
    """Find all Gemini concise summary audio files"""
    pattern = "book_*_concise_gemini.wav"
    audio_files = sorted(audio_dir.glob(pattern))

    results = []
    for audio_file in audio_files:
        # Extract book_id from filename: book_{book_id}_concise_gemini.wav
        filename = audio_file.stem  # Remove .wav extension
        parts = filename.split('_')
        if len(parts) >= 2 and parts[0] == 'book':
            try:
                book_id = int(parts[1])
                results.append({
                    'book_id': book_id,
                    'audio_path': str(audio_file),
                    'filename': audio_file.name
                })
            except ValueError:
                print(f"⚠️  Warning: Could not extract book_id from {audio_file.name}")

    return results


def calculate_audio_duration(audio_path: str) -> float:
    """Calculate duration of a WAV file in seconds"""
    try:
        with wave.open(audio_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / float(rate)
            return duration
    except Exception as e:
        print(f"⚠️  Warning: Could not read audio file {audio_path}: {e}")
        return 0.0


def backfill_audio_file(db: Database, audio_info: dict, dry_run: bool = False) -> bool:
    """Backfill a single audio file to the database"""
    book_id = audio_info['book_id']
    audio_path = audio_info['audio_path']
    filename = audio_info['filename']

    # Get the summary_id for this book's concise summary
    summary = db.get_summary(book_id, 'concise')
    if not summary:
        print(f"❌ Book ID {book_id}: No concise summary found (file: {filename})")
        return False

    summary_id = summary['id']

    # Check if this audio file is already in the database
    existing_audio = db.get_audio_file(summary_id=summary_id)
    if existing_audio:
        print(f"⏭️  Book ID {book_id}: Audio already in database (file: {filename})")
        return False

    # Calculate duration
    duration = calculate_audio_duration(audio_path)

    if dry_run:
        print(f"[DRY RUN] Book ID {book_id}: Would add to database")
        print(f"  Summary ID: {summary_id}")
        print(f"  Audio path: {audio_path}")
        print(f"  Duration: {duration:.2f}s")
        return True

    # Add to database
    try:
        db.add_audio_file(
            summary_id=summary_id,
            chapter_id=None,
            audio_path=audio_path,
            duration=duration
        )
        print(f"✅ Book ID {book_id}: Added to database (duration: {duration:.2f}s, file: {filename})")
        return True
    except Exception as e:
        print(f"❌ Book ID {book_id}: Failed to add to database: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Backfill Gemini concise audio file metadata to database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually updating the database'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("Backfill Audio File Metadata to Database")
    print("=" * 80)

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No database changes will be made\n")

    # Initialize database
    print("\nInitializing database...")
    db = Database()

    # Find audio files
    audio_dir = project_root / "frontend" / "static" / "audio"
    print(f"Scanning audio directory: {audio_dir}\n")

    audio_files = find_gemini_audio_files(audio_dir)

    if not audio_files:
        print("✅ No Gemini concise audio files found.")
        return

    print(f"Found {len(audio_files)} Gemini concise audio file(s)\n")

    # Process each audio file
    added = 0
    skipped = 0
    failed = 0

    for audio_info in audio_files:
        result = backfill_audio_file(db, audio_info, dry_run=args.dry_run)

        if result:
            added += 1
        elif result is False and audio_info.get('skipped'):
            skipped += 1
        else:
            # Check if it was skipped due to existing entry
            book_id = audio_info['book_id']
            summary = db.get_summary(book_id, 'concise')
            if summary and db.get_audio_file(summary_id=summary['id']):
                skipped += 1
            else:
                failed += 1

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total audio files found: {len(audio_files)}")
    print(f"✅ {'Would be added' if args.dry_run else 'Added'}: {added}")
    print(f"⏭️  Skipped (already in database): {skipped}")
    print(f"❌ Failed: {failed}")
    print(f"{'=' * 80}\n")

    if args.dry_run:
        print("Run without --dry-run to actually update the database.")
    elif failed > 0:
        print("⚠️  Some files could not be added. Check the output above for details.")
    else:
        print("🎉 Backfill completed successfully!")


if __name__ == "__main__":
    main()
