"""Send only the content rows that differ between the local DB and the VM.

`hashes` and `apply` run on the VM. Only books present in the local DB can lose rows,
so a book that exists only on the live site is never touched. The reader index is
left out: triggers mark changed books and the VM rebuilds it on demand.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing

# How to find each row's owning book, parents first.
OWNER = {
    'books': ('books', 'id'),
    'images': ('images', 'book_id'),
    'cover_thumbnails': ('cover_thumbnails JOIN images ON images.id = cover_thumbnails.image_id', 'images.book_id'),
    'chapters': ('chapters', 'book_id'),
    'chapter_audio': ('chapter_audio JOIN chapters ON chapters.id = chapter_audio.chapter_id', 'chapters.book_id'),
}


def _columns(conn, table):
    info = conn.execute(f'PRAGMA table_info({table})').fetchall()
    return [row[1] for row in info], [row[1] for row in sorted((r for r in info if r[5]), key=lambda r: r[5])]


def _rows(conn, table):
    """Yield (key, row hash, owning book id, row values)."""
    columns, pk = _columns(conn, table)
    source, owner = OWNER[table]
    selected = ', '.join(f'{table}.{name}' for name in columns)
    for *values, book_id in conn.execute(f'SELECT {selected}, {owner} FROM {source}'):
        record = dict(zip(columns, values))
        digest = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        yield json.dumps([record[name] for name in pk]), digest, book_id, values


def row_hashes(conn) -> dict:
    return {'tables': {table: {key: [digest, book_id] for key, digest, book_id, _ in _rows(conn, table)} for table in OWNER},
            'slugs': {str(book_id): slug for book_id, slug in conn.execute('SELECT id, slug FROM books')}}


def _refuse_mismatched_books(local_slugs, remote_slugs):
    remote_ids = {slug: book_id for book_id, slug in remote_slugs.items()}
    for book_id, slug in local_slugs.items():
        if book_id in remote_slugs and remote_slugs[book_id] != slug:
            raise ValueError(f'Book {book_id} is {slug!r} locally but {remote_slugs[book_id]!r} on the live site')
        if book_id not in remote_slugs and slug in remote_ids:
            raise ValueError(f'{slug!r} is already live as book {remote_ids[slug]}, but is book {book_id} locally')


def build_patch(local, remote: dict) -> dict:
    local_slugs = {str(book_id): slug for book_id, slug in local.execute('SELECT id, slug FROM books')}
    _refuse_mismatched_books(local_slugs, remote['slugs'])
    patch = {'upsert': {}, 'delete': {}}
    for table in OWNER:
        theirs = remote['tables'].get(table, {})
        ours, changed = set(), []
        for key, digest, _, values in _rows(local, table):
            ours.add(key)
            if theirs.get(key, [None])[0] != digest:
                changed.append(values)
        if changed:
            patch['upsert'][table] = {'columns': _columns(local, table)[0], 'rows': changed}
        gone = [json.loads(key) for key, (_, book_id) in theirs.items()
                if key not in ours and str(book_id) in local_slugs]
        if gone:
            patch['delete'][table] = gone
    return patch


def patch_size(patch: dict) -> int:
    return sum(len(t['rows']) for t in patch['upsert'].values()) + sum(len(keys) for keys in patch['delete'].values())


def apply_patch(db_path, patch: dict) -> None:
    """All of it or none of it, with the site still running."""
    with closing(sqlite3.connect(db_path, timeout=30, isolation_level=None)) as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('BEGIN IMMEDIATE')
        try:
            conn.execute('PRAGMA defer_foreign_keys = ON')  # books and images refer to each other
            for table in reversed(list(OWNER)):
                pk = _columns(conn, table)[1]
                where = ' AND '.join(f'{name} = ?' for name in pk)
                conn.executemany(f'DELETE FROM {table} WHERE {where}', patch['delete'].get(table, []))
            for table in OWNER:
                if table in patch['upsert']:
                    _upsert(conn, table, patch['upsert'][table])
            conn.execute('COMMIT')
        except sqlite3.IntegrityError as error:
            conn.execute('ROLLBACK')
            raise ValueError(f'Patch broke a foreign key or uniqueness rule, nothing changed: {error}') from error
        except BaseException:
            conn.execute('ROLLBACK')
            raise


def _upsert(conn, table, change):
    columns, rows = change['columns'], change['rows']
    pk = _columns(conn, table)[1]
    if table == 'chapters':  # free the (book, ordinal) slots so chapters can swap places
        conn.executemany('UPDATE chapters SET ordinal = -id WHERE id = ?', [(row[columns.index('id')],) for row in rows])
    updates = ', '.join(f'{name} = excluded.{name}' for name in columns if name not in pk)
    conn.executemany(f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({", ".join("?" * len(columns))}) '
                     f'ON CONFLICT({", ".join(pk)}) DO UPDATE SET {updates}', rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('hashes', 'apply'))
    parser.add_argument('--db', required=True)
    args = parser.parse_args(argv)
    if args.command == 'hashes':
        with closing(sqlite3.connect(f'file:{args.db}?mode=ro', uri=True)) as conn:
            json.dump(row_hashes(conn), sys.stdout)
    else:
        patch = json.load(sys.stdin)
        apply_patch(args.db, patch)
        print('Applied rows:', patch_size(patch))


if __name__ == '__main__':
    main()
