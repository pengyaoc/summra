"""Validate a Distill book folder and import it into the content database.

Usage: python -m distill.scripts.push_book <folder> [--dry-run | --deploy] [--db PATH] [--config PATH]
"""
import argparse
import sys
from pathlib import Path

from distill import config
from distill.book_format import block_text, iter_chapters, list_images, load_book, validate_book, word_count
from distill.models import DistillDatabase
from distill.scripts.deploy_db import DEFAULT_CONFIG, DeployError, deploy_db, load_settings


def _print_summary(book: dict, folder: Path) -> None:
    chapters = iter_chapters(book)
    words = sum(word_count(block_text(block)) for _, _, blocks in chapters for block in blocks)
    images = list_images(folder)
    print(f'Title: {book["title"]}')
    print(f'Chapters: {len(chapters)}')
    print(f'Words: {words}')
    print(f'Images: {len(images)}')
    print(f'Image bytes: {sum(p.stat().st_size for p in images)}')


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description='Import a Distill book folder.')
    parser.add_argument('folder', type=Path)
    parser.add_argument('--dry-run', action='store_true', help='validate and summarize without writing to the DB')
    parser.add_argument('--db', type=Path, default=config.DATABASE_PATH, help='content database path')
    parser.add_argument('--deploy', action='store_true', help='after importing, copy the DB to the VM and restart')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG, help='deploy settings file (with --deploy)')
    args = parser.parse_args(argv)
    if args.deploy and args.dry_run:
        parser.error('--deploy cannot be combined with --dry-run')

    book = load_book(args.folder)
    errors = validate_book(book, args.folder)
    if errors:
        print('Invalid book:')
        for error in errors:
            print(f'  {error}')
        return 1

    _print_summary(book, args.folder)
    if args.dry_run:
        return 0

    settings = None
    if args.deploy:
        try:  # fail before importing if the deploy config is unusable
            settings = load_settings(args.config)
            if not settings.get('DISTILL_SITE_URL'):
                raise DeployError('missing deploy setting(s): DISTILL_SITE_URL')
        except DeployError as e:
            print(f'Deploy failed: {e}', file=sys.stderr)
            return 1

    book_id = DistillDatabase(args.db).import_book(args.folder)
    print(f'Imported {book["slug"]} as book {book_id}')
    if args.deploy:
        try:
            deploy_db(args.db, settings)
        except DeployError as e:
            print(f'Deploy failed: {e}', file=sys.stderr)
            return 1
        print(f'Deployed: {settings["DISTILL_SITE_URL"].rstrip("/")}/books/{book["slug"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
