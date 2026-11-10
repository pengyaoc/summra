"""Record chapter audio on the owner's Mac for either app, in English or Chinese.

Usage:
  python -m shared.audio.make_audio --app {distill,plainly} (--book SLUG | --all) [--mode MODE] [--dry-run]
                                    [--approve-voice] [--opus-only] [--jobs N] [--db PATH] [--config PATH] [--deploy]

Each app describes itself in <app>/audio_app.py; a book's `lang` picks the voice (English if it has none).

Only chapters whose audio is missing or stale are rendered, so an interrupted run
resumes where it stopped. Every run first checks each voice against the approved
reference clip; --approve-voice records a new reference after you have listened.
"""
import argparse
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from importlib import import_module
from pathlib import Path

from shared.audio.assemble import encode_opus, render_chapter
from shared.audio.engines import (
    RenderFailed, VoiceMismatch, VoiceUnavailable, check_reference, engine_for,
)

CHARS_PER_SECOND = {'en': 15, 'zh': 4.5}


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / 'deploy' / 'distill' / 'deploy.local.env'
SIRI_KEYS = ('DISTILL_SIRI_TTS_PATH', 'DISTILL_SIRI_PYTHON')


def _voice_settings(path: Path) -> dict:
    """The Chinese voice's paths from the local settings file, resolved against the repo root."""
    if not Path(path).is_file():
        return {}
    found = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        key, _, value = line.partition('=')
        if key.strip() in SIRI_KEYS and value.strip():
            found[key.strip()] = str((REPO_ROOT / value.strip().strip('"\'')).resolve())
    return found


def _app(name: str):
    return import_module(f'{name}.audio_app')


def _lang(book: dict) -> str:
    return book.get('lang') or 'en'


def _render_one(app_name: str, db_path: str, book_id: int, chapter_id: int, lang: str, settings: dict, mode: str) -> tuple:
    """Render and save one chapter; returns (chapter_id, duration_ms, seconds taken)."""
    started = time.monotonic()
    db = _app(app_name).open_db(Path(db_path))
    chapter = next(c for c in db.get_chapters(book_id) if c['id'] == chapter_id)
    engine = engine_for(lang, settings)
    with tempfile.TemporaryDirectory(prefix='book-audio-') as work:
        opus, timings, duration_ms, checksum = render_chapter(db.audio_spoken_units(chapter, mode), engine, Path(work))
    db.save_chapter_audio(chapter_id, opus, timings, duration_ms, checksum, engine.voice_id(), engine.name,
                          getattr(engine, 'rate', None), mode=mode)
    db.set_deploy_audio(chapter_id, opus, mode=mode)  # the same file: new chapters keep no AAC
    return chapter_id, duration_ms, time.monotonic() - started


def _encode_missing_opus(db) -> int:
    """Make the Opus copy for every older chapter that has only AAC; no voices are used."""
    todo = db.missing_deploy_audio()
    with tempfile.TemporaryDirectory(prefix='distill-opus-') as work:
        for chapter_id in todo:
            key = db.get_chapter_audio_key(chapter_id)
            db.set_deploy_audio(chapter_id, encode_opus(db.media.get(key), Path(work)))
    return len(todo)


def _spoken_chars(db, chapter: dict, mode: str) -> int:
    return sum(len(part) for unit in db.audio_spoken_units(chapter, mode) for part in unit.parts)


def _render_book(app_name, db_path, book, todo, settings, jobs, mode) -> bool:
    """Render `todo` chapter ids; stop the book on the first failure. True if all done."""
    print(f'{book["slug"]} [{mode}]: rendering {len(todo)} chapter(s)', flush=True)
    if jobs <= 1:
        for chapter_id in todo:
            try:
                _, ms, took = _render_one(app_name, str(db_path), book['id'], chapter_id, _lang(book), settings, mode)
            except RenderFailed as error:
                print(f'  chapter {chapter_id}: FAILED, stopping {book["slug"]}: {error}', file=sys.stderr)
                return False
            print(f'  chapter {chapter_id}: {ms / 1000:.0f}s of audio in {took:.0f}s', flush=True)
        return True
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(_render_one, app_name, str(db_path), book['id'], cid, _lang(book), settings, mode): cid for cid in todo}
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
    parser = argparse.ArgumentParser(description='Record chapter audio.')
    parser.add_argument('--app', required=True, choices=('distill', 'plainly'))
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--book', help='book slug')
    target.add_argument('--all', action='store_true', help='every book')
    parser.add_argument('--dry-run', action='store_true', help='report what would be rendered; render nothing')
    parser.add_argument('--approve-voice', action='store_true', help='record the current voices as approved')
    parser.add_argument('--jobs', type=int, default=2, help='chapters rendered at once')
    parser.add_argument('--mode', help="one reading mode, e.g. Plainly's original or plain; default: all of the app's")
    parser.add_argument('--db', type=Path)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--opus-only', action='store_true',
                        help='only convert older AAC-only chapters to Opus; render nothing')
    parser.add_argument('--deploy', action='store_true', help='push the DB and new audio to the VM afterwards')
    args = parser.parse_args(argv)
    if args.deploy and args.dry_run:
        parser.error('--deploy cannot be combined with --dry-run')

    app = _app(args.app)
    if args.deploy and app.deploy is None:
        print(f'--deploy is not available for {args.app} yet', file=sys.stderr)
        return 2
    modes = (args.mode,) if args.mode else app.MODES
    db_path = args.db or app.DEFAULT_DB
    db = app.open_db(db_path)
    books = app.books(db) if args.all else [b for b in [db.get_book_by_slug(args.book)] if b]
    if not books:
        print(f'No such book: {args.book}', file=sys.stderr)
        return 1
    if args.opus_only:
        print(f'Encoded {_encode_missing_opus(db)} Opus copies.')
        return 0
    settings = _voice_settings(args.config)
    plan = [(book, mode, db.stale_or_missing_audio(book['id'], mode)) for book in books for mode in modes]

    if args.dry_run:
        for book, mode, todo in plan:
            chapters = db.get_chapters(book['id'])
            pending = [c for c in chapters if c['id'] in set(todo)]
            seconds = sum(_spoken_chars(db, c, mode) for c in pending) / CHARS_PER_SECOND.get(_lang(book), 15)
            print(f'{book["slug"]} [{_lang(book)}, {mode}]: {len(chapters)} chapters, '
                  f'{len(chapters) - len(todo)} current or empty, {len(todo)} to render (~{seconds / 3600:.1f} h of audio)')
        return 0

    ref_dir = Path(db_path).parent / 'distill-voice-refs'
    try:
        for lang in sorted({_lang(book) for book, _, todo in plan if todo or args.approve_voice}):
            check_reference(engine_for(lang, settings), ref_dir, approve=args.approve_voice)
    except (VoiceMismatch, VoiceUnavailable, RenderFailed, ValueError, KeyError) as error:
        print(f'Voice check failed: {error}', file=sys.stderr)
        return 1

    ok = True
    for book, mode, todo in plan:
        if todo:
            ok = _render_book(args.app, db_path, book, todo, settings, args.jobs, mode) and ok

    if args.deploy:
        try:
            app.deploy(db_path, args.config)
        except Exception as error:
            print(f'Deploy failed: {error}', file=sys.stderr)
            return 1
        print('Deployed audio.')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
