"""Validate a Distill book folder and import it into the content database.

Usage: python -m distill.scripts.push_book <folder> [--dry-run] [--db PATH]
"""
import argparse
import sys
from pathlib import Path

from distill import config
from distill.book_format import block_text, iter_chapters, list_images, load_book, validate_book, word_count
from distill.models import DistillDatabase


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
    args = parser.parse_args(argv)

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

    book_id = DistillDatabase(args.db).import_book(args.folder)
    print(f'Imported {book["slug"]} as book {book_id}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
