"""Copy the local Distill content DB to the production VM and restart the service.

Usage: python -m distill.scripts.deploy_db [--db PATH] [--config PATH]

Only the content DB is pushed. distill_user.db holds reading progress and is never touched.
"""
import argparse
import hashlib
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from distill import config

DEFAULT_CONFIG = config.BASE_DIR / 'deploy' / 'distill' / 'deploy.local.env'
REQUIRED_KEYS = (
    'DISTILL_VM_INSTANCE', 'DISTILL_VM_ZONE', 'DISTILL_VM_PROJECT', 'DISTILL_VM_ACCOUNT',
    'DISTILL_VM_SERVICE_USER', 'DISTILL_VM_REMOTE_DB', 'DISTILL_VM_UNIT', 'DISTILL_VM_PORT',
)
REMOTE_UPLOAD = 'distill.db.new'  # relative to the ssh user's home: the VM's /tmp is small
SNAPSHOT_MARK = 'bak-pre-push'
SNAPSHOTS_KEPT = 2


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


def deploy_db(db_path: Path, settings: dict, run=subprocess.run) -> None:
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

    # 2. Snapshot the live DB (nothing to snapshot on a first push).
    exists = run(['gcloud', 'compute', 'ssh', instance, f'--command=test -f {remote_db}', *gcloud_flags],
                 capture_output=True, text=True)
    if exists.returncode == 0:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        ssh(f'sudo cp {remote_db} {remote_db}.{SNAPSHOT_MARK}-{stamp}', 'snapshot of the live database')

    # 3-4. Upload, then verify before touching the service.
    gcloud('scp', str(db_path), f'{instance}:{REMOTE_UPLOAD}', what='scp of the database')
    remote_md5 = ssh(f'md5sum ~/{REMOTE_UPLOAD}', 'remote md5sum').split()[:1]
    if remote_md5 != [local_md5]:
        raise DeployError(f'md5 mismatch after upload (local {local_md5}, remote {remote_md5}); service untouched')

    # 5. Swap the file in while the service is stopped.
    ctl = f'sudo -u {svc} XDG_RUNTIME_DIR=/run/user/$(id -u {svc}) systemctl --user'
    swap = ' && '.join([
        f'{ctl} stop {unit}',
        f'sudo rm -f {remote_db}-wal {remote_db}-shm',
        f'sudo mv ~/{REMOTE_UPLOAD} {remote_db}',
        f'sudo chown {svc}:{svc} {remote_db}',
        f'sudo chmod 664 {remote_db}',
        f'{ctl} start {unit}',
        'sleep 3',
        f'{ctl} is-active {unit}',
    ])
    ssh(swap, f'service swap/restart of {unit}')

    # 6. Up, and still behind auth.
    code = ssh(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/", 'local auth check').strip()
    if code != '401':
        raise DeployError(f'expected HTTP 401 from the app (up, auth required), got {code!r}')

    # 7. Keep only the newest snapshots.
    ssh(f'ls -1t {remote_db}.{SNAPSHOT_MARK}-* 2>/dev/null | tail -n +{SNAPSHOTS_KEPT + 1} | xargs -r sudo rm -f',
        'snapshot pruning (deploy itself succeeded)')


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
