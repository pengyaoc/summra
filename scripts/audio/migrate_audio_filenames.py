#!/usr/bin/env python3
"""
Migration script to rename audio files to new naming convention.

Old Gemini convention:
- summary_{book_id}_{type}_gemini.wav
- chapter_{book_id}_{num}_gemini.wav

New convention:
- book_{book_id}_{type}_gemini.wav
- book_{book_id}_chapter_{num}_gemini.wav

Old VITS convention:
- {hash}.wav (no provider suffix)
- {audio_id}.wav

New VITS convention:
- {hash}_vits.wav
- {audio_id}_vits.wav

Usage:
    python scripts/audio/migrate_audio_filenames.py          # Preview changes (dry run)
    python scripts/audio/migrate_audio_filenames.py --apply  # Apply changes
"""

import re
from pathlib import Path

project_root = Path(__file__).parent.parent.parent


from backend.models import Database
from backend import config


def find_audio_files():
    """Find all audio files in the TTS output directory"""
    audio_dir = config.TTS_OUTPUT_DIR
    if not audio_dir.exists():
        print(f"Audio directory does not exist: {audio_dir}")
        return []

    wav_files = list(audio_dir.glob("*.wav"))
    print(f"Found {len(wav_files)} WAV files in {audio_dir}")
    return wav_files


def analyze_filename(filename: str):
    """
    Analyze a filename and determine if it needs migration.

    Returns:
        (needs_migration, old_name, new_name, file_type)
        file_type: 'gemini_summary', 'gemini_chapter', 'vits', 'gemini_chunk', 'unknown'
    """
    # Gemini summary: summary_{book_id}_{type}_gemini.wav
    match = re.match(r'^summary_(\d+)_(concise|medium|comprehensive)_gemini\.wav$', filename)
    if match:
        book_id, summary_type = match.groups()
        new_name = f"book_{book_id}_{summary_type}_gemini.wav"
        return (True, filename, new_name, 'gemini_summary')

    # Gemini chapter: chapter_{book_id}_{num}_gemini.wav
    match = re.match(r'^chapter_(\d+)_(\d+)_gemini\.wav$', filename)
    if match:
        book_id, chapter_num = match.groups()
        new_name = f"book_{book_id}_chapter_{chapter_num}_gemini.wav"
        return (True, filename, new_name, 'gemini_chapter')

    # Gemini chunk files (temporary - can be deleted)
    match = re.match(r'^(summary|chapter)_\d+_(concise|medium|comprehensive|\d+)_chunk_\d+\.wav$', filename)
    if match:
        return (False, filename, None, 'gemini_chunk')

    # Already migrated Gemini files
    if re.match(r'^book_\d+_(concise|medium|comprehensive)_gemini\.wav$', filename):
        return (False, filename, None, 'gemini_summary_new')

    if re.match(r'^book_\d+_chapter_\d+_gemini\.wav$', filename):
        return (False, filename, None, 'gemini_chapter_new')

    # VITS files without _vits suffix
    match = re.match(r'^([a-f0-9]{32})\.wav$', filename)
    if match:
        md5_hash = match.group(1)
        new_name = f"{md5_hash}_vits.wav"
        return (True, filename, new_name, 'vits_hash')

    # VITS files already with _vits suffix
    if re.match(r'^[a-f0-9]{32}_vits\.wav$', filename):
        return (False, filename, None, 'vits_new')

    # VITS chunk files
    if re.match(r'^chunk_[a-f0-9]{32}(_vits)?\.wav$', filename):
        return (False, filename, None, 'vits_chunk')

    # Unknown format
    return (False, filename, None, 'unknown')


def migrate_files(dry_run=True):
    """
    Migrate audio files to new naming convention.

    Args:
        dry_run: If True, only show what would be renamed without making changes
    """
    db = Database()
    audio_files = find_audio_files()

    if not audio_files:
        print("No audio files found")
        return

    # Analyze all files
    to_migrate = []
    already_migrated = []
    chunks_to_delete = []
    unknown_files = []

    print(f"\n{'='*80}")
    print("ANALYZING AUDIO FILES")
    print(f"{'='*80}\n")

    for file_path in audio_files:
        filename = file_path.name
        needs_migration, old_name, new_name, file_type = analyze_filename(filename)

        if needs_migration:
            to_migrate.append((file_path, old_name, new_name, file_type))
        elif file_type == 'gemini_chunk':
            chunks_to_delete.append((file_path, filename))
        elif file_type in ['gemini_summary_new', 'gemini_chapter_new', 'vits_new']:
            already_migrated.append((filename, file_type))
        elif file_type == 'unknown':
            unknown_files.append(filename)

    # Report
    print(f"Files requiring migration: {len(to_migrate)}")
    print(f"Already migrated files: {len(already_migrated)}")
    print(f"Temporary chunks to delete: {len(chunks_to_delete)}")
    print(f"Unknown format files: {len(unknown_files)}")

    # Show details
    if to_migrate:
        print(f"\n{'-'*80}")
        print("FILES TO MIGRATE:")
        print(f"{'-'*80}\n")
        for file_path, old_name, new_name, file_type in to_migrate:
            print(f"  [{file_type:20s}] {old_name}")
            print(f"  {'':20s}  → {new_name}")
            print()

    if chunks_to_delete:
        print(f"\n{'-'*80}")
        print("TEMPORARY CHUNK FILES (will be deleted):")
        print(f"{'-'*80}\n")
        for file_path, filename in chunks_to_delete[:10]:
            print(f"  {filename}")
        if len(chunks_to_delete) > 10:
            print(f"  ... and {len(chunks_to_delete) - 10} more")
        print()

    if unknown_files:
        print(f"\n{'-'*80}")
        print("UNKNOWN FORMAT FILES (will be skipped):")
        print(f"{'-'*80}\n")
        for filename in unknown_files[:10]:
            print(f"  {filename}")
        if len(unknown_files) > 10:
            print(f"  ... and {len(unknown_files) - 10} more")
        print()

    # Apply changes if not dry run
    if dry_run:
        print(f"\n{'='*80}")
        print("DRY RUN - No changes made")
        print(f"{'='*80}\n")
        print("To apply changes, run: python scripts/audio/migrate_audio_filenames.py --apply")
        return

    print(f"\n{'='*80}")
    print("APPLYING MIGRATIONS")
    print(f"{'='*80}\n")

    # Rename files
    renamed_count = 0
    for file_path, old_name, new_name, file_type in to_migrate:
        old_path = file_path
        new_path = file_path.parent / new_name

        try:
            # Rename file
            old_path.rename(new_path)
            print(f"✓ Renamed: {old_name} → {new_name}")
            renamed_count += 1

            # Update database if it's a Gemini file
            if file_type in ['gemini_summary', 'gemini_chapter']:
                # Update audio_files table
                old_db_path = f"audio/{old_name}"
                new_db_path = f"audio/{new_name}"

                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE audio_files SET audio_path = ? WHERE audio_path = ?",
                    (new_db_path, old_db_path)
                )
                updated_rows = cursor.rowcount
                conn.commit()
                conn.close()

                if updated_rows > 0:
                    print(f"  Updated {updated_rows} database record(s)")

        except Exception as e:
            print(f"✗ Error renaming {old_name}: {e}")

    # Delete temporary chunk files
    deleted_count = 0
    for file_path, filename in chunks_to_delete:
        try:
            file_path.unlink()
            deleted_count += 1
        except Exception as e:
            print(f"✗ Error deleting {filename}: {e}")

    print(f"\n{'='*80}")
    print("MIGRATION COMPLETE")
    print(f"{'='*80}\n")
    print(f"Files renamed: {renamed_count}/{len(to_migrate)}")
    print(f"Chunks deleted: {deleted_count}/{len(chunks_to_delete)}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Migrate audio files to new naming convention',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--apply', action='store_true',
                       help='Apply changes (default is dry run)')

    args = parser.parse_args()

    migrate_files(dry_run=not args.apply)


if __name__ == "__main__":
    main()
