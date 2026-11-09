"""Render chapter audio for Distill books on the owner's Mac, then optionally deploy.

Usage:
  python -m distill.scripts.make_audio (--book SLUG | --all) [--dry-run] [--approve-voice] [--opus-only]
                                       [--jobs N] [--db PATH] [--config PATH] [--deploy]

Only chapters whose audio is missing or stale are rendered, so an interrupted run
resumes where it stopped. Every run first checks each voice against the approved
reference clip; --approve-voice records a new reference after you have listened.
"""
import argparse
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from distill import config
from shared.audio.assemble import encode_opus, render_chapter
from shared.audio.engines import (
    RenderFailed, VoiceMismatch, VoiceUnavailable, check_reference, engine_for,
)
from shared.audio.spoken import spoken_units
from distill.models import DistillDatabase
from distill.scripts.deploy_db import DEFAULT_CONFIG, DeployError, deploy_db, load_settings

CHARS_PER_SECOND = {'en': 15, 'zh': 4.5}


def _settings(path: Path) -> dict:
    """Deploy settings, with Siri paths resolved against the repo root."""
    try:
        settings = load_settings(path)
    except DeployError:
        settings = {}
    for key in ('DISTILL_SIRI_TTS_PATH', 'DISTILL_SIRI_PYTHON'):
        if settings.get(key):
            settings[key] = str((config.BASE_DIR / settings[key]).resolve())
    return settings


def _render_one(db_path: str, chapter_id: int, lang: str, settings: dict) -> tuple:
    """Render and save one chapter; returns (chapter_id, duration_ms, seconds taken)."""
    started = time.monotonic()
    db = DistillDatabase(Path(db_path))
    chapter = next(c for c in _chapters(db, chapter_id))
    engine = engine_for(lang, settings)
    with tempfile.TemporaryDirectory(prefix='distill-audio-') as work:
        opus, timings, duration_ms, checksum = render_chapter(chapter, engine, Path(work))
    db.save_chapter_audio(chapter_id, opus, timings, duration_ms, checksum, engine.voice_id(), engine.name,
                          getattr(engine, 'rate', None))
    db.set_deploy_audio(chapter_id, opus)  # the same file: new chapters keep no AAC
    return chapter_id, duration_ms, time.monotonic() - started


def _encode_missing_opus(db: DistillDatabase) -> int:
    """Make the Opus copy for every older chapter that has only AAC; no voices are used."""
    todo = db.missing_deploy_audio()
    with tempfile.TemporaryDirectory(prefix='distill-opus-') as work:
        for chapter_id in todo:
            key = db.get_chapter_audio_key(chapter_id)
            db.set_deploy_audio(chapter_id, encode_opus(db.media.get(key), Path(work)))
    return len(todo)


def _chapters(db: DistillDatabase, chapter_id: int):
    with db.get_connection() as conn:
        book_id = conn.execute('SELECT book_id FROM chapters WHERE id = ?', (chapter_id,)).fetchone()[0]
    return (c for c in db.get_chapters(book_id) if c['id'] == chapter_id)


def _spoken_chars(chapter: dict) -> int:
    return sum(len(part) for unit in spoken_units(chapter) for part in unit.parts)


def _render_book(db, db_path, book, todo, settings, jobs) -> bool:
    """Render `todo` chapter ids; stop the book on the first failure. True if all done."""
    print(f'{book["slug"]}: rendering {len(todo)} chapter(s)', flush=True)
    if jobs <= 1:
        for chapter_id in todo:
            try:
                _, ms, took = _render_one(str(db_path), chapter_id, book['lang'], settings)
            except RenderFailed as error:
                print(f'  chapter {chapter_id}: FAILED, stopping {book["slug"]}: {error}', file=sys.stderr)
                return False
            print(f'  chapter {chapter_id}: {ms / 1000:.0f}s of audio in {took:.0f}s', flush=True)
        return True
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(_render_one, str(db_path), cid, book['lang'], settings): cid for cid in todo}
        for future in as_completed(futures):
            try:
                _, ms, took = future.result()
            except RenderFailed as error:
                print(f'  chapter {futures[future]}: FAILED, stopping {book["slug"]}: {error}', file=sys.stderr)
                for other in futures:
                    other.cancel()
                return False
            print(f'  chapter {futures[future]}: {ms / 1000:.0f}s of audio in {took:.0f}s', flush=True)
    return True


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description='Render Distill chapter audio.')
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--book', help='book slug')
    target.add_argument('--all', action='store_true', help='every book')
    parser.add_argument('--dry-run', action='store_true', help='report what would be rendered; render nothing')
    parser.add_argument('--approve-voice', action='store_true', help='record the current voices as approved')
    parser.add_argument('--jobs', type=int, default=2, help='chapters rendered at once')
    parser.add_argument('--db', type=Path, default=config.DATABASE_PATH)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--opus-only', action='store_true',
                        help='only convert older AAC-only chapters to Opus; render nothing')
    parser.add_argument('--deploy', action='store_true', help='push the DB and new audio to the VM afterwards')
    args = parser.parse_args(argv)
    if args.deploy and args.dry_run:
        parser.error('--deploy cannot be combined with --dry-run')

    db = DistillDatabase(args.db)
    books = db.list_books() if args.all else [b for b in [db.get_book_by_slug(args.book)] if b]
    if not books:
        print(f'No such book: {args.book}', file=sys.stderr)
        return 1
    if args.opus_only:
        print(f'Encoded {_encode_missing_opus(db)} Opus copies.')
        return 0
    settings = _settings(args.config)
    plan = [(book, db.stale_or_missing_audio(book['id'])) for book in books]

    if args.dry_run:
        for book, todo in plan:
            chapters = db.get_chapters(book['id'])
            pending = [c for c in chapters if c['id'] in set(todo)]
            seconds = sum(_spoken_chars(c) for c in pending) / CHARS_PER_SECOND.get(book['lang'], 15)
            print(f'{book["slug"]} [{book["lang"]}]: {len(chapters)} chapters, '
                  f'{len(chapters) - len(todo)} current, {len(todo)} to render (~{seconds / 3600:.1f} h of audio)')
        return 0

    ref_dir = Path(args.db).parent / 'distill-voice-refs'
    try:
        for lang in sorted({book['lang'] for book, todo in plan if todo or args.approve_voice}):
            check_reference(engine_for(lang, settings), ref_dir, approve=args.approve_voice)
    except (VoiceMismatch, VoiceUnavailable, RenderFailed, ValueError, KeyError) as error:
        print(f'Voice check failed: {error}', file=sys.stderr)
        return 1

    ok = True
    for book, todo in plan:
        if todo:
            ok = _render_book(db, args.db, book, todo, settings, args.jobs) and ok

    if args.deploy:
        try:
            deploy_db(args.db, load_settings(args.config))
        except DeployError as error:
            print(f'Deploy failed: {error}', file=sys.stderr)
            return 1
        print('Deployed audio.')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
