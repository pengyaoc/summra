"""Legacy extraction safety, byte compatibility and separate media deployment."""
from contextlib import closing
import hashlib
import io
from pathlib import Path
import shutil
import sqlite3
import tarfile

import pytest

from distill.media import MediaStore
from distill.models import DistillDatabase
from distill.scripts.media_transfer import backup_metadata, install_archive, media_archive


@pytest.fixture
def legacy(tmp_path, sample_book, write_book):
    folder = write_book(sample_book)
    # Valid JPEG with a large trailer makes compaction measurable.
    cover = folder / 'images/cover.jpg'
    cover.write_bytes(cover.read_bytes() + b'x' * (2 * 1024 * 1024))
    db = DistillDatabase(tmp_path / 'distill.db')
    bid = db.import_book(folder)
    db.ensure_reader_content(bid)
    with closing(db.get_connection()) as conn:
        originals = [(r['id'], r['book_id'], r['name'], r['mime'], db.media.get(r['storage_key']))
                     for r in conn.execute('SELECT * FROM images')]
        thumbs = [(r['image_id'], r['format'], r['token'], r['source_checksum'], r['mime'],
                   db.media.get(r['storage_key'])) for r in conn.execute('SELECT * FROM cover_thumbnails')]
        preserved = {table: [tuple(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY 1,2')]
                     for table in ('books', 'chapters', 'reader_unit', 'reader_revision')}
        conn.execute('PRAGMA foreign_keys=OFF')
        with conn:
            conn.execute('CREATE TABLE legacy_images (id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, name TEXT NOT NULL, mime TEXT NOT NULL, data BLOB NOT NULL, UNIQUE(book_id,name))')
            conn.execute('CREATE TABLE legacy_thumbnails (image_id INTEGER NOT NULL REFERENCES legacy_images(id) ON DELETE CASCADE, format TEXT NOT NULL, token TEXT NOT NULL, source_checksum TEXT NOT NULL, mime TEXT NOT NULL, data BLOB NOT NULL, PRIMARY KEY(image_id,format))')
            conn.executemany('INSERT INTO legacy_images VALUES (?,?,?,?,?)', originals)
            conn.execute("UPDATE sqlite_sequence SET seq=1000 WHERE name='legacy_images'")
            conn.executemany('INSERT INTO legacy_thumbnails VALUES (?,?,?,?,?,?)', thumbs)
            conn.execute('DROP TABLE cover_thumbnails')
            conn.execute('DROP TABLE images')
            conn.execute('ALTER TABLE legacy_images RENAME TO images')
            conn.execute('ALTER TABLE legacy_thumbnails RENAME TO cover_thumbnails')
    shutil.rmtree(db.media.root)
    return db.db_path, bid, originals, thumbs, preserved


def test_legacy_migration_preserves_bytes_ids_tokens_and_reader_state(legacy):
    path, bid, images, thumbs, preserved = legacy
    before = path.stat().st_size
    db = DistillDatabase(path)
    assert db.verify_media() == 4
    for _, _, name, mime, data in images:
        assert db.get_image(bid, name) == (mime, data)
    for _, fmt, token, _, mime, data in thumbs:
        assert db.get_cover_thumbnail('my-book', token, fmt) == (mime, data)
    with closing(db.get_connection()) as conn:
        for table, rows in preserved.items():
            assert [tuple(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY 1,2')] == rows
        assert list(conn.execute('PRAGMA foreign_key_check')) == []
        assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name='images'").fetchone()[0] == 1000
        for table in ('images', 'cover_thumbnails'):
            assert 'data' not in {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
    db.compact()
    assert path.stat().st_size < before / 2
    assert DistillDatabase(path).verify_media() == 4  # restart/idempotent
    assert db.generate_cover_thumbnails() == 0


def test_file_failure_rolls_back_legacy_schema_and_blobs(legacy, monkeypatch):
    path, _, images, thumbs, _ = legacy
    original_put = MediaStore.put
    count = 0
    def disk_full(self, data):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('simulated disk full')
        return original_put(self, data)
    with monkeypatch.context() as patch:
        patch.setattr(MediaStore, 'put', disk_full)
        with pytest.raises(OSError, match='disk full'):
            DistillDatabase(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute('SELECT * FROM images').fetchall() == images
        assert conn.execute('SELECT * FROM cover_thumbnails').fetchall() == thumbs
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    assert DistillDatabase(path).verify_media() == 4


def test_new_import_is_file_only_deduplicated_and_missing_files_return_none(tmp_path, sample_book, write_book):
    db = DistillDatabase(tmp_path / 'd.db')
    folder = write_book(sample_book)
    bid = db.import_book(folder)
    keys = db.media_keys()
    assert len(keys) == 4
    db.import_book(folder)
    assert db.media_keys() == keys
    assert len([p for p in db.media.root.rglob('*') if p.is_file()]) == 4
    with closing(db.get_connection()) as conn:
        key = conn.execute('SELECT storage_key FROM images').fetchone()[0]
    db.media.path(key).unlink()
    assert db.get_image(bid, 'cover.jpg') is None
    with pytest.raises(FileNotFoundError):
        db.verify_media()


def test_store_rejects_path_traversal_and_existing_corruption(tmp_path):
    store = MediaStore(tmp_path / 'media')
    with pytest.raises(ValueError):
        store.get('../outside')
    key = store.put(b'original')
    store.path(key).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='checksum'):
        store.put(b'original')


def test_separate_archive_installs_all_references(tmp_path, sample_book, write_book):
    db = DistillDatabase(tmp_path / 'source.db')
    db.import_book(write_book(sample_book))
    destination = MediaStore(tmp_path / 'received')
    with media_archive(db.db_path) as archive:
        assert archive.stat().st_mode & 0o777 == 0o600
        assert install_archive(archive, destination.root) == len(db.media_keys())
    for key in db.media_keys():
        assert destination.get(key) == db.media.get(key)


@pytest.mark.parametrize('kind', ['traversal', 'symlink', 'bad_hash'])
def test_archive_rejects_unsafe_or_corrupt_members(tmp_path, kind):
    archive = tmp_path / 'bad.tar'
    key = hashlib.sha256(b'expected').hexdigest()
    with tarfile.open(archive, 'w') as tar:
        member = tarfile.TarInfo('../outside' if kind == 'traversal' else f'{key[:2]}/{key}')
        if kind == 'symlink':
            member.type = tarfile.SYMTYPE
            member.linkname = '/outside'
            tar.addfile(member)
        else:
            member.size = 3
            tar.addfile(member, io.BytesIO(b'bad'))
    with pytest.raises(ValueError):
        install_archive(archive, tmp_path / 'media')
    assert not (tmp_path / 'outside').exists()


def test_backup_keeps_one_verified_metadata_archive_and_preserves_accounts(tmp_path, sample_book, write_book):
    db = DistillDatabase(tmp_path / 'distill.db')
    db.import_book(write_book(sample_book))
    for name in ('distill_user.db', 'distill_pairing.db'):
        with sqlite3.connect(tmp_path / name) as conn:
            conn.execute('CREATE TABLE saved (value)')
            conn.execute("INSERT INTO saved VALUES ('keep me')")
    expected = {name: (tmp_path / name).read_bytes() for name in ('distill_user.db', 'distill_pairing.db')}
    first = backup_metadata(db.db_path)
    second = backup_metadata(db.db_path)
    assert first == second and list(first.parent.glob('*.tar.gz')) == [first]
    with tarfile.open(first) as tar:
        assert set(tar.getnames()) == {'distill.db', 'distill_user.db', 'distill_pairing.db', 'manifest.json'}
        assert not any('/' in name for name in tar.getnames())
    assert all((tmp_path / name).read_bytes() == data for name, data in expected.items())
