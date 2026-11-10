"""Record book summaries on the owner's Mac, as files the Listen button finds.

Usage:
  python -m plainly.scripts.audio.record_summaries (--book SLUG | --all) [--type {concise,medium}]
                                                   [--dry-run] [--force] [--approve-voice] [--db PATH]

A summary that already has a recording is skipped unless --force is given.
Older Gemini files stay in place; a new recording takes priority over them.
"""
import argparse
import sys
import tempfile
from pathlib import Path

from plainly import config, tts_utils
from plainly.models import Database
from shared.audio.assemble import render_chapter
from shared.audio.engines import RenderFailed, VoiceMismatch, VoiceUnavailable, check_reference, engine_for
from shared.audio.spoken import SpokenUnit

TYPES = ('concise', 'medium')


def summary_units(content: str, book_id: int, summary_type: str) -> list:
    parts = [tts_utils.clean_text_for_speech(p) for p in content.split('\n\n')]
    return [SpokenUnit(f'{book_id}.{summary_type}.{i}', [p]) for i, p in enumerate(part for part in parts if part)]


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description='Record Plainly book summaries.')
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--book', help='book slug')
    target.add_argument('--all', action='store_true', help='every book')
    parser.add_argument('--type', choices=TYPES, help='one summary length; default: both')
    parser.add_argument('--dry-run', action='store_true', help='report what would be recorded; record nothing')
    parser.add_argument('--force', action='store_true', help='record again even if a recording exists')
    parser.add_argument('--approve-voice', action='store_true', help='record the current voice as approved')
    parser.add_argument('--db', type=Path, default=config.DATABASE_PATH)
    args = parser.parse_args(argv)

    db = Database(db_path=str(args.db))
    books = db.get_all_books() if args.all else [b for b in [db.get_book_by_slug(args.book)] if b]
    if not books:
        print(f'No such book: {args.book}', file=sys.stderr)
        return 1

    todo = []
    for book in books:
        for kind in ((args.type,) if args.type else TYPES):
            summary = db.get_summary(book['id'], kind)
            target = config.TTS_OUTPUT_DIR / f'book_{book["id"]}_{kind}.m4a'
            if summary and summary['content'] and (args.force or not target.exists()):
                todo.append((book, kind, summary['content'], target))

    if args.dry_run:
        print(f'{len(todo)} summaries to record')
        for book, kind, _, _ in todo:
            print(f'  {book["slug"]}: {kind}')
        return 0
    if not todo:
        return 0

    engine = engine_for('en', {})
    try:
        check_reference(engine, Path(args.db).parent / 'distill-voice-refs', approve=args.approve_voice)
    except (VoiceMismatch, VoiceUnavailable, RenderFailed, ValueError) as error:
        print(f'Voice check failed: {error}', file=sys.stderr)
        return 1

    for book, kind, content, target in todo:
        with tempfile.TemporaryDirectory(prefix='summary-audio-') as work:
            try:
                audio, _, duration_ms, _ = render_chapter(summary_units(content, book['id'], kind), engine, Path(work))
            except RenderFailed as error:
                print(f'{book["slug"]} {kind}: FAILED: {error}', file=sys.stderr)
                return 1
        target.write_bytes(audio)
        print(f'{book["slug"]} {kind}: {duration_ms / 1000:.0f}s of audio', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
