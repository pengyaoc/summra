"""Verified media transfer and one consistent metadata backup per Distill app."""
import argparse
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import pwd
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone

from distill import config
from distill.media import MediaStore


def media_keys(db_path):
    with closing(sqlite3.connect(f'file:{Path(db_path)}?mode=ro', uri=True)) as db:
        keys = set()
        for table in ('images', 'cover_thumbnails'):
            columns = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
            if not columns:
                continue
            if 'storage_key' not in columns:
                raise ValueError('Legacy image BLOBs: run distill.scripts.migrate_media first')
            keys.update(row[0] for row in db.execute(f'SELECT storage_key FROM {table}'))
        return sorted(keys)


@contextmanager
def media_archive(db_path, media_dir=None):
    store = MediaStore(media_dir if media_dir is not None else config.media_dir_for(db_path))
    keys = media_keys(db_path)
    for key in keys:
        store.verify(key)
    if not keys:
        yield None
        return
    with tempfile.TemporaryDirectory(prefix='distill-media-upload-') as temporary:
        archive = Path(temporary) / 'media.tar'
        with tarfile.open(archive, 'w') as tar:
            for key in keys:
                tar.add(store.path(key), arcname=f'{key[:2]}/{key}', recursive=False)
        archive.chmod(0o600)
        yield archive


def _owner(path, owner):
    if owner:
        account = pwd.getpwnam(owner)
        os.chown(path, account.pw_uid, account.pw_gid)


def install_archive(archive, media_dir, owner=None):
    """Install only verified hash-named regular files; never delete old objects."""
    store = MediaStore(media_dir)
    count = 0
    with tarfile.open(archive, 'r:') as tar:
        for member in tar:
            key = member.name.rsplit('/', 1)[-1]
            path = store.path(key)  # validates a lowercase SHA256 key
            if not member.isfile() or member.name != f'{key[:2]}/{key}':
                raise ValueError('Invalid media archive member')
            with tar.extractfile(member) as source:
                data = source.read()
            if hashlib.sha256(data).hexdigest() != key:
                raise ValueError('Media archive checksum mismatch')
            store.put(data)
            for item in (store.root, path.parent, path):
                _owner(item, owner)
            count += 1
    return count


def backup_metadata(db_path, owner=None):
    """Atomically replace the one app archive after verifying SQLite snapshots.

    File media is additive/immutable and backed up separately; old objects stay
    available when restoring this metadata snapshot. No account/progress writes.
    """
    db_path = Path(db_path)
    destination = db_path.parent / 'backups' / f'{db_path.stem}-latest.tar.gz'
    destination.parent.mkdir(parents=True, exist_ok=True)
    sources = [db_path, db_path.with_name(db_path.stem + '_user.db'),
               db_path.with_name(db_path.stem + '_pairing.db')]
    with tempfile.TemporaryDirectory(prefix='.distill-snapshot-', dir=destination.parent) as temporary:
        temporary = Path(temporary)
        manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'files': {}}
        for path in sources:
            if not path.is_file():
                continue
            snapshot = temporary / path.name
            with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(snapshot)) as target:
                    source.backup(target)
                    if target.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                        raise ValueError('Snapshot integrity check failed')
            snapshot.chmod(0o600)
            manifest['files'][path.name] = {'sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                                           'bytes': snapshot.stat().st_size}
        (temporary / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        pending = temporary / 'snapshot.tar.gz'
        with tarfile.open(pending, 'w:gz') as tar:
            for name in [*manifest['files'], 'manifest.json']:
                tar.add(temporary / name, arcname=name, recursive=False)
        pending.chmod(0o600)
        with tarfile.open(pending, 'r:gz') as tar:
            if set(tar.getnames()) != set(manifest['files']) | {'manifest.json'}:
                raise ValueError('Unexpected snapshot archive members')
            for name, entry in manifest['files'].items():
                if hashlib.sha256(tar.extractfile(name).read()).hexdigest() != entry['sha256']:
                    raise ValueError('Snapshot archive checksum mismatch')
        _owner(pending, owner)
        os.replace(pending, destination)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    install = commands.add_parser('install')
    install.add_argument('archive', type=Path)
    install.add_argument('--media-dir', type=Path, required=True)
    install.add_argument('--owner')
    backup = commands.add_parser('backup')
    backup.add_argument('--db', type=Path, required=True)
    backup.add_argument('--owner')
    args = parser.parse_args(argv)
    if args.command == 'install':
        print('Verified media objects:', install_archive(args.archive, args.media_dir, args.owner))
    else:
        print('Verified metadata backup:', backup_metadata(args.db, args.owner))


if __name__ == '__main__':
    main()
