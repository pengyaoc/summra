"""Write the reviewed book metadata into a database.

    PYTHONPATH=. venv/bin/python scripts/content/apply_book_metadata.py [--db PATH] [--dry-run]

Reads scripts/content/book_metadata.json (built by build_book_metadata.py):
categories become exactly the BISAC-based groupings listed there (old ad-hoc
categories and their links are removed), and each book gets its audience,
ATOS reading level, interest level and school reading lists. Idempotent:
a second run changes nothing. Safe to run on the prod VM after a deploy —
it only touches categories, book_categories and those four books columns.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend import models  # noqa: E402

METADATA = Path(__file__).resolve().parent / 'book_metadata.json'


def _book_values(book):
    level = book.get('reading_level') or {}
    return (
        book['audience'],
        level.get('atos'),
        level.get('interest'),
        json.dumps(book['school_lists'], ensure_ascii=False) if book['school_lists'] else None,
    )


def apply_metadata(db, meta, dry_run=False):
    """Apply `meta` to `db`. Returns {'changed': n, 'missing': [slugs not in db]}."""
    conn = db.get_connection()
    changed = 0
    try:
        existing = {row['name']: row['id'] for row in conn.execute('SELECT id, name FROM categories')}
        for name, info in meta['categories'].items():
            if name not in existing:
                cur = conn.execute('INSERT INTO categories (name, description) VALUES (?, ?)', (name, info['description']))
                existing[name] = cur.lastrowid
                changed += 1
            else:
                cur = conn.execute('UPDATE categories SET description = ? WHERE id = ? AND description IS NOT ?',
                                   (info['description'], existing[name], info['description']))
                changed += cur.rowcount
        wanted_ids = {existing[name] for name in meta['categories']}

        slugs = {row['slug']: row['id'] for row in conn.execute('SELECT id, slug FROM books WHERE slug IS NOT NULL')}
        missing = sorted(slug for slug in meta['books'] if slug not in slugs)
        for slug, book in meta['books'].items():
            book_id = slugs.get(slug)
            if book_id is None:
                continue
            cur = conn.execute(
                '''UPDATE books SET audience = ?, atos_level = ?, interest_level = ?, school_lists = ?
                   WHERE id = ? AND (audience IS NOT ? OR atos_level IS NOT ? OR interest_level IS NOT ? OR school_lists IS NOT ?)''',
                (*_book_values(book), book_id, *_book_values(book)))
            changed += cur.rowcount
            want = {existing[name] for name in book['categories']}
            have = {row[0] for row in conn.execute('SELECT category_id FROM book_categories WHERE book_id = ?', (book_id,))}
            for category_id in have - want:
                conn.execute('DELETE FROM book_categories WHERE book_id = ? AND category_id = ?', (book_id, category_id))
                changed += 1
            for category_id in want - have:
                conn.execute('INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)', (book_id, category_id))
                changed += 1

        stale = [cid for name, cid in existing.items() if cid not in wanted_ids]
        for category_id in stale:
            conn.execute('DELETE FROM book_categories WHERE category_id = ?', (category_id,))
            conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
            changed += 1

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()
    return {'changed': changed, 'missing': missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--db', help='database path (default: the app database)')
    parser.add_argument('--dry-run', action='store_true', help='report what would change, write nothing')
    args = parser.parse_args()
    db = models.Database(db_path=args.db) if args.db else models.Database()
    report = apply_metadata(db, json.loads(METADATA.read_text()), dry_run=args.dry_run)
    print(f"{'Would change' if args.dry_run else 'Changed'} {report['changed']} row(s).")
    if report['missing']:
        print(f"Not in this database (skipped): {', '.join(report['missing'])}")


if __name__ == '__main__':
    main()
