"""Copy the local Distill content DB to the production VM and restart the service.

Usage: python -m distill.scripts.deploy_db [--db PATH] [--config PATH]

Content metadata and referenced media are pushed. Account/progress databases are
backed up but never replaced. The one latest metadata archive is atomically refreshed.
"""
import argparse
from contextlib import closing
import tempfile
import hashlib
import sqlite3
import subprocess
import sys
import shlex
from pathlib import Path

from distill import config
from distill.scripts.media_transfer import media_archive

DEFAULT_CONFIG = config.BASE_DIR / 'deploy' / 'distill' / 'deploy.local.env'
REQUIRED_KEYS = (
    'DISTILL_VM_INSTANCE', 'DISTILL_VM_ZONE', 'DISTILL_VM_PROJECT', 'DISTILL_VM_ACCOUNT',
    'DISTILL_VM_SERVICE_USER', 'DISTILL_VM_REMOTE_DB', 'DISTILL_VM_UNIT', 'DISTILL_VM_PORT',
)
REMOTE_UPLOAD = 'distill.db.new'  # relative to the ssh user's home: the VM's /tmp is small
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


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _deploy_db(db_path: Path, settings: dict, run, archive) -> None:
    missing = [key for key in REQUIRED_KEYS if not settings.get(key)]
    if missing:
        raise DeployError(f'missing deploy setting(s): {", ".join(missing)}')
    if not db_path.is_file():
        raise DeployError(f'database not found: {db_path}')

    instance = settings['DISTILL_VM_INSTANCE']
    svc = settings['DISTILL_VM_SERVICE_USER']
    remote_db = settings['DISTILL_VM_REMOTE_DB']
    unit = settings['DISTILL_VM_UNIT']
    port = settings['DISTILL_VM_PORT']
    gcloud_flags = [f'--zone={settings["DISTILL_VM_ZONE"]}', f'--project={settings["DISTILL_VM_PROJECT"]}',
                    f'--account={settings["DISTILL_VM_ACCOUNT"]}']

    def gcloud(verb: str, *args: str, what: str) -> str:
        result = run(['gcloud', 'compute', verb, *args, *gcloud_flags], capture_output=True, text=True)
        if result.returncode != 0:
            raise DeployError(f'{what} failed: {(result.stderr or result.stdout or "").strip()}')
        return result.stdout or ''

    def ssh(command: str, what: str) -> str:
        return gcloud('ssh', instance, f'--command={command}', what=what)

    # 1. Fold the WAL into the main file so the copy is complete, then fingerprint it.
    conn = sqlite3.connect(db_path)
    try:
        conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    finally:
        conn.close()
    local_md5 = _md5(db_path)

    # Install verified immutable media before activating any references to it.
    repo_root = Path(settings.get('DISTILL_VM_REPO_ROOT') or Path(remote_db).parent.parent)
    remote_media = settings.get('DISTILL_VM_MEDIA_DIR') or str(Path(remote_db).with_name(Path(remote_db).stem + '-media'))
    helper = (f'sudo env PYTHONPATH={shlex.quote(str(repo_root))} '
              f'{shlex.quote(str(repo_root / "venv/bin/python"))} -m distill.scripts.media_transfer')
    if archive is not None:
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        gcloud('scp', str(archive), f'{instance}:{REMOTE_MEDIA_UPLOAD}', what='media upload')
        ssh(f'chmod 600 ~/{REMOTE_MEDIA_UPLOAD}', 'private media upload permissions')
        uploaded_sha = ssh(f'sha256sum ~/{REMOTE_MEDIA_UPLOAD}', 'media upload hash').split()[:1]
        if uploaded_sha != [archive_sha]:
            raise DeployError('media SHA256 mismatch after upload; service untouched')
        ssh(f'{helper} install ~/{REMOTE_MEDIA_UPLOAD} --media-dir {shlex.quote(remote_media)} '
            f'--owner {shlex.quote(svc)}', 'verified media installation')

    # One consistent archive includes existing content/accounts/pairing DBs.
    exists = run(['gcloud', 'compute', 'ssh', instance, f'--command=test -f {shlex.quote(remote_db)}', *gcloud_flags],
                 capture_output=True, text=True)
    if exists.returncode == 0:
        ssh(f'{helper} backup --db {shlex.quote(remote_db)} --owner {shlex.quote(svc)}',
            'snapshot of the live database')

    # 3-4. Upload, then verify before touching the service.
    gcloud('scp', str(db_path), f'{instance}:{REMOTE_UPLOAD}', what='scp of the database')
    remote_md5 = ssh(f'md5sum ~/{REMOTE_UPLOAD}', 'remote md5sum').split()[:1]
    if remote_md5 != [local_md5]:
        raise DeployError(f'md5 mismatch after upload (local {local_md5}, remote {remote_md5}); service untouched')

    # 5. Swap the file in while the service is stopped.
    ctl = f'sudo -u {svc} XDG_RUNTIME_DIR=/run/user/$(id -u {svc}) systemctl --user'
    swap = ' && '.join([
        f'{ctl} stop {unit}',
        f'sudo rm -f {shlex.quote(remote_db + "-wal")} {shlex.quote(remote_db + "-shm")}',
        f'sudo mv ~/{REMOTE_UPLOAD} {shlex.quote(remote_db)}',
        f'sudo chown {shlex.quote(svc + ":" + svc)} {shlex.quote(remote_db)}',
        f'sudo chmod 664 {shlex.quote(remote_db)}',
        f'{ctl} start {unit}',
        'sleep 3',
        f'{ctl} is-active {unit}',
    ])
    ssh(swap, f'service swap/restart of {unit}')

    # 6. Up, and still behind auth.
    code = ssh(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/", 'local auth check').strip()
    if code != '401':
        raise DeployError(f'expected HTTP 401 from the app (up, auth required), got {code!r}')

    if archive is not None:
        ssh(f'rm -f ~/{REMOTE_MEDIA_UPLOAD}', 'temporary media upload cleanup')


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
                    if target.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                        raise ValueError('Content snapshot integrity check failed')
            with media_archive(snapshot, media_dir=config.media_dir_for(db_path)) as archive:
                _deploy_db(snapshot, settings, run, archive)
    except (ValueError, OSError, sqlite3.Error) as error:
        raise DeployError(f'Media preparation/deployment failed: {error}') from error


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description='Push the local Distill DB to the VM.')
    parser.add_argument('--db', type=Path, default=config.DATABASE_PATH)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        deploy_db(args.db, load_settings(args.config))
    except DeployError as e:
        print(f'Deploy failed: {e}', file=sys.stderr)
        return 1
    print('Deployed distill.db')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
