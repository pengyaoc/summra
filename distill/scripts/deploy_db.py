"""Send the local Distill content changes to the production VM, row by row.

Usage: python -m distill.scripts.deploy_db [--db PATH] [--config PATH]

Only rows that differ and media the VM lacks are sent; the site keeps running, and
books that exist only on the VM are left alone. Account/progress databases are backed
up but never changed. The one latest metadata archive is atomically refreshed.
"""
import argparse
from contextlib import closing
import tempfile
import hashlib
import json
import sqlite3
import subprocess
import sys
import shlex
from pathlib import Path

from distill import config
from distill.scripts.db_patch import build_patch, patch_size
from distill.scripts.media_transfer import media_archive, verify_media

DEFAULT_CONFIG = config.BASE_DIR / 'deploy' / 'distill' / 'deploy.local.env'
REQUIRED_KEYS = (
    'DISTILL_VM_INSTANCE', 'DISTILL_VM_ZONE', 'DISTILL_VM_PROJECT', 'DISTILL_VM_ACCOUNT',
    'DISTILL_VM_SERVICE_USER', 'DISTILL_VM_REMOTE_DB', 'DISTILL_VM_UNIT', 'DISTILL_VM_PORT',
)
REMOTE_PATCH = 'distill.patch.json'  # relative to the ssh user's home: the VM's /tmp is small
REMOTE_MEDIA_UPLOAD = 'distill-media.new.tar'


class DeployError(Exception):
    pass


def load_settings(path: Path) -> dict:
    """Parse a KEY=VALUE file; blank lines and # comments are skipped."""
    if not path.is_file():
        raise DeployError(f'deploy config not found: {path} (copy deploy/distill/deploy.local.env.example)')
    settings = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, value = line.partition('=')
            settings[key.strip()] = value.strip()
    return settings


def _gcloud_flags(settings: dict) -> list:
    return [f'--zone={settings["DISTILL_VM_ZONE"]}', f'--project={settings["DISTILL_VM_PROJECT"]}',
            f'--account={settings["DISTILL_VM_ACCOUNT"]}']


def _remote_media(settings: dict):
    """(media_transfer helper command on the VM, VM media directory)."""
    remote_db = settings['DISTILL_VM_REMOTE_DB']
    repo_root = Path(settings.get('DISTILL_VM_REPO_ROOT') or Path(remote_db).parent.parent)
    remote_media = settings.get('DISTILL_VM_MEDIA_DIR') or str(Path(remote_db).with_name(Path(remote_db).stem + '-media'))
    helper = (f'sudo env PYTHONPATH={shlex.quote(str(repo_root))} '
              f'{shlex.quote(str(repo_root / "venv/bin/python"))} -m distill.scripts.media_transfer')
    return helper, remote_media


def _remote_media_keys(settings: dict, run) -> frozenset:
    """Media keys the VM already holds, so a push uploads only new objects."""
    helper, remote_media = _remote_media(settings)
    result = run(['gcloud', 'compute', 'ssh', settings['DISTILL_VM_INSTANCE'],
                  f'--command={helper} list --media-dir {shlex.quote(remote_media)}', *_gcloud_flags(settings)],
                 capture_output=True, text=True)
    if result.returncode != 0:
        raise DeployError(f'listing VM media failed: {(result.stderr or result.stdout or "").strip()}')
    return frozenset(line.strip() for line in (result.stdout or '').splitlines() if line.strip())


def _deploy_db(db_path: Path, settings: dict, run, archive) -> None:
    instance = settings['DISTILL_VM_INSTANCE']
    svc = settings['DISTILL_VM_SERVICE_USER']
    remote_db = settings['DISTILL_VM_REMOTE_DB']
    port = settings['DISTILL_VM_PORT']
    gcloud_flags = _gcloud_flags(settings)

    def gcloud(verb: str, *args: str, what: str) -> str:
        result = run(['gcloud', 'compute', verb, *args, *gcloud_flags], capture_output=True, text=True)
        if result.returncode != 0:
            raise DeployError(f'{what} failed: {(result.stderr or result.stdout or "").strip()}')
        return result.stdout or ''

    def ssh(command: str, what: str) -> str:
        return gcloud('ssh', instance, f'--command={command}', what=what)

    def upload(local: Path, remote: str, what: str) -> None:
        digest = hashlib.sha256(local.read_bytes()).hexdigest()
        gcloud('scp', str(local), f'{instance}:{remote}', what=what)
        ssh(f'chmod 600 ~/{remote}', f'{what} permissions')
        if ssh(f'sha256sum ~/{remote}', f'{what} hash').split()[:1] != [digest]:
            raise DeployError(f'{what}: SHA256 mismatch after upload; live site unchanged')

    exists = run(['gcloud', 'compute', 'ssh', instance, f'--command=test -f {shlex.quote(remote_db)}', *gcloud_flags],
                 capture_output=True, text=True)
    if exists.returncode != 0:
        raise DeployError(f'no live database at {remote_db}: nothing to apply changes to')

    # What differs, before anything is uploaded: a conflict stops the deploy here.
    helper, remote_media = _remote_media(settings)
    repo_root = Path(settings.get('DISTILL_VM_REPO_ROOT') or Path(remote_db).parent.parent)
    patcher = (f'sudo -u {shlex.quote(svc)} env PYTHONPATH={shlex.quote(str(repo_root))} '
               f'{shlex.quote(str(repo_root / "venv/bin/python"))} -m distill.scripts.db_patch')
    live = json.loads(ssh(f'{patcher} hashes --db {shlex.quote(remote_db)}', 'reading live rows'))
    with closing(sqlite3.connect(db_path)) as snapshot:
        patch = build_patch(snapshot, live)

    # Install verified immutable media before activating any references to it.
    if archive is not None:
        upload(archive, REMOTE_MEDIA_UPLOAD, 'media upload')
        ssh(f'{helper} install ~/{REMOTE_MEDIA_UPLOAD} --media-dir {shlex.quote(remote_media)} '
            f'--owner {shlex.quote(svc)}', 'verified media installation')

    if patch_size(patch):
        # One consistent archive includes existing content/accounts/pairing DBs.
        ssh(f'{helper} backup --db {shlex.quote(remote_db)} --owner {shlex.quote(svc)}',
            'snapshot of the live database')
        patch_file = db_path.with_name('patch.json')
        patch_file.write_text(json.dumps(patch, ensure_ascii=False), encoding='utf-8')
        upload(patch_file, REMOTE_PATCH, 'patch upload')
        # Run as the service user, so SQLite's WAL files stay writable by the app.
        ssh(f'{patcher} apply --db {shlex.quote(remote_db)} < ~/{REMOTE_PATCH}', 'applying the patch')
        ssh(f'rm -f ~/{REMOTE_PATCH}', 'temporary patch cleanup')

    # Still up, and still behind auth.
    code = ssh(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/", 'local auth check').strip()
    if code != '401':
        raise DeployError(f'expected HTTP 401 from the app (up, auth required), got {code!r}')

    if archive is not None:
        ssh(f'rm -f ~/{REMOTE_MEDIA_UPLOAD}', 'temporary media upload cleanup')


def _ship_deploy_audio(snapshot) -> None:
    """Point the shipped DB's audio at the Opus files, so older chapters' AAC stays on the Mac."""
    if 'deploy_key' in {row[1] for row in snapshot.execute('PRAGMA table_info(chapter_audio)')}:
        with snapshot:
            snapshot.execute('UPDATE chapter_audio SET storage_key = deploy_key WHERE deploy_key IS NOT NULL')


def deploy_db(db_path: Path, settings: dict, run=subprocess.run) -> None:
    db_path = Path(db_path)
    missing = [key for key in REQUIRED_KEYS if not settings.get(key)]
    if missing:
        raise DeployError(f'missing deploy setting(s): {", ".join(missing)}')
    if not db_path.is_file():
        raise DeployError(f'database not found: {db_path}')
    try:
        # Verify local references before any upload or service mutation.
        with tempfile.TemporaryDirectory(prefix='distill-content-upload-') as temporary:
            snapshot = Path(temporary) / 'distill.db'
            with closing(sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(snapshot)) as target:
                    source.backup(target)
                    _ship_deploy_audio(target)
                    if target.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                        raise ValueError('Content snapshot integrity check failed')
            media_dir = config.media_dir_for(db_path)
            verify_media(snapshot, media_dir)  # before any remote call
            present = _remote_media_keys(settings, run)
            with media_archive(snapshot, media_dir=media_dir, exclude=present) as archive:
                _deploy_db(snapshot, settings, run, archive)
    except (ValueError, OSError, sqlite3.Error) as error:
        raise DeployError(f'Media preparation/deployment failed: {error}') from error


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description='Send local Distill content changes to the VM.')
    parser.add_argument('--db', type=Path, default=config.DATABASE_PATH)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        deploy_db(args.db, load_settings(args.config))
    except DeployError as e:
        print(f'Deploy failed: {e}', file=sys.stderr)
        return 1
    print('Deployed distill.db changes')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
