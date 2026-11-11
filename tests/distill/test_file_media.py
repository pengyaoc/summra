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


def test_list_keys_empty_dir(tmp_path):
    from distill.scripts.media_transfer import list_keys
    assert list_keys(tmp_path / 'missing') == []


def test_list_keys_returns_stored(tmp_path):
    from distill.scripts.media_transfer import list_keys
    store = MediaStore(tmp_path / 'media')
    keys = sorted([store.put(b'one'), store.put(b'two')])
    assert list_keys(store.root) == keys


def test_archive_excludes_present_keys(tmp_path, sample_book, write_book):
    import tarfile
    db = DistillDatabase(tmp_path / 'source.db')
    db.import_book(write_book(sample_book))
    keys = db.media_keys()
    with media_archive(db.db_path, exclude=frozenset(keys[:1])) as archive:
        with tarfile.open(archive) as tar:
            assert sorted(tar.getnames()) == [f'{k[:2]}/{k}' for k in keys[1:]]
    with media_archive(db.db_path, exclude=frozenset(keys)) as archive:
        assert archive is None


def test_media_transfer_keys_include_chapter_audio(tmp_path, sample_book, write_book):
    from distill.scripts.media_transfer import media_keys
    db = DistillDatabase(tmp_path / 'source.db')
    bid = db.import_book(write_book(sample_book))
    key = db.save_chapter_audio(db.get_chapters(bid)[0]['id'], b'sound', [], 1, 'c', 'say:system', 'say', None)
    assert key in media_keys(db.db_path)


def test_media_keys_keep_master_and_deploy_copy(tmp_path, sample_book, write_book):
    from distill.scripts.media_transfer import media_keys
    db = DistillDatabase(tmp_path / 'source.db')
    bid = db.import_book(write_book(sample_book))
    chapter_id = db.get_chapters(bid)[0]['id']
    master = db.save_chapter_audio(chapter_id, b'master', [], 1, 'c', 'say:system', 'say', None)
    opus = db.set_deploy_audio(chapter_id, b'opus')
    assert {master, opus} <= set(db.media_keys())
    assert {master, opus} <= set(media_keys(db.db_path))
    assert db.missing_deploy_audio() == []


def test_missing_deploy_audio_lists_chapters_without_opus(tmp_path, sample_book, write_book):
    db = DistillDatabase(tmp_path / 'source.db')
    bid = db.import_book(write_book(sample_book))
    chapter_id = db.get_chapters(bid)[0]['id']
    assert db.missing_deploy_audio() == []
    db.save_chapter_audio(chapter_id, b'master', [], 1, 'c', 'say:system', 'say', None)
    assert db.missing_deploy_audio() == [chapter_id]


def _age(store, key, seconds):
    import os, time
    path = store.path(key)
    old = time.time() - seconds
    os.utime(path, (old, old))


def test_prune_removes_only_media_unused_by_live_db_and_its_backup(tmp_path, sample_book, write_book):
    from distill.scripts.media_transfer import prune_media
    db = DistillDatabase(tmp_path / 'distill.db')
    db.import_book(write_book(sample_book))
    live = set(db.media_keys())
    backed_up = db.media.put(b'only the backup references this')
    with closing(db.get_connection()) as conn, conn:
        conn.execute("UPDATE images SET storage_key=? WHERE id=(SELECT MIN(id) FROM images)", (backed_up,))
    backup_metadata(db.db_path)  # the one backup now references `backed_up`
    with closing(db.get_connection()) as conn, conn:  # live DB moves back to the original key
        conn.execute("UPDATE images SET storage_key=? WHERE storage_key=?", (sorted(live)[0], backed_up))
    orphan = db.media.put(b'replaced narration nobody references')
    fresh = db.media.put(b'just written by the app, not yet referenced')
    for key in [*live, backed_up, orphan]:
        _age(db.media, key, 2 * 86400)

    removed, freed = prune_media(db.db_path)

    assert (removed, freed) == (1, len(b'replaced narration nobody references'))
    assert not db.media.path(orphan).exists()
    for key in [*live, backed_up, fresh]:
        assert db.media.path(key).exists()


def test_prune_without_a_backup_keeps_live_media(tmp_path, sample_book, write_book):
    from distill.scripts.media_transfer import prune_media
    db = DistillDatabase(tmp_path / 'distill.db')
    db.import_book(write_book(sample_book))
    orphan = db.media.put(b'orphan')
    for key in [*db.media_keys(), orphan]:
        _age(db.media, key, 2 * 86400)
    assert prune_media(db.db_path)[0] == 1
    assert db.verify_media() == len(db.media_keys())


def test_prune_refuses_an_unreadable_backup(tmp_path, sample_book, write_book):
    from distill.scripts.media_transfer import prune_media
    db = DistillDatabase(tmp_path / 'distill.db')
    db.import_book(write_book(sample_book))
    orphan = db.media.put(b'orphan')
    _age(db.media, orphan, 2 * 86400)
    (tmp_path / 'backups').mkdir()
    (tmp_path / 'backups' / 'distill-latest.tar.gz').write_bytes(b'not a tarball')
    with pytest.raises(Exception):
        prune_media(db.db_path)
    assert db.media.path(orphan).exists()
