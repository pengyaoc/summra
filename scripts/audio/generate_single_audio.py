#!/usr/bin/env python3
"""
Generate Gemini TTS audio for a single book's summary

Usage:
    python scripts/audio/generate_single_audio.py --book-id 46 --summary-type medium
    python scripts/audio/generate_single_audio.py --book-id 46 --summary-type concise --dry-run
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
import tts_utils


def main():
    parser = argparse.ArgumentParser(description='Generate Gemini TTS audio for a single book summary')
    parser.add_argument('--book-id', type=int, required=True, help='Book ID to generate audio for')
    parser.add_argument('--summary-type', choices=['concise', 'medium'], required=True,
                        help='Type of summary to generate audio for')
    parser.add_argument('--voice', choices=['Puck', 'Charon', 'Kore', 'Fenrir', 'Aoede', 'Sulafat'],
                        default='Kore', help='Voice to use for TTS (default: Kore)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without actually generating audio')

    args = parser.parse_args()

    # Initialize database and TTS handler
    db = Database()
    tts_handler = GeminiTTSHandler(voice=args.voice)

    # Get book and summary info
    book = db.get_book(args.book_id)
    if not book:
        print(f"Error: Book with ID {args.book_id} not found")
        sys.exit(1)

    summary = db.get_summary(args.book_id, args.summary_type)
    if not summary:
        print(f"Error: {args.summary_type.capitalize()} summary not found for book {args.book_id}")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Generating Gemini TTS audio")
    print(f"Book: {book['title']} by {book['author']}")
    print(f"Book ID: {args.book_id}")
    print(f"Summary Type: {args.summary_type}")
    print(f"Voice: {args.voice}")
    print(f"{'='*80}\n")

    # Get summary text
    summary_text = summary['content']

    # Check audio file
    audio_dir = project_root / "frontend" / "static" / "audio"
    audio_path = audio_dir / f"book_{args.book_id}_{args.summary_type}_gemini.wav"

    if audio_path.exists():
        print(f"⚠️  Audio file already exists: {audio_path}")
        print("Skipping generation (delete file first if you want to regenerate)")
        return

    if args.dry_run:
        print(f"[DRY RUN] Would generate audio for {args.summary_type} summary")
        print(f"[DRY RUN] Summary length: {len(summary_text)} characters")
        print(f"[DRY RUN] Output file: {audio_path}")
        return

    # Generate audio
    print(f"Generating audio for {args.summary_type} summary...")
    print(f"Summary length: {len(summary_text)} characters")

    try:
        # Generate audio using TTS handler
        audio_data = tts_handler.generate_audio(summary_text)

        # Save audio file
        audio_dir.mkdir(parents=True, exist_ok=True)
        with open(audio_path, 'wb') as f:
            f.write(audio_data)

        # Get file info
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)

        # Get audio duration
        duration_seconds = tts_utils.get_audio_duration(str(audio_path))
        duration_str = tts_utils.format_duration(duration_seconds)

        print(f"\n✅ Audio generated successfully!")
        print(f"   File: {audio_path}")
        print(f"   Size: {file_size_mb:.2f} MB")
        print(f"   Duration: {duration_str}")

        # Update database with audio metadata
        db.update_summary_audio(
            summary['id'],
            f"book_{args.book_id}_{args.summary_type}_gemini.wav",
            duration_seconds
        )
        print(f"   Database updated with audio metadata")

    except Exception as e:
        print(f"\n❌ Error generating audio: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
