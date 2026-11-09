"""Update the VM's checkout to the pushed main branch and restart Distill.

Usage: python -m distill.scripts.deploy_code [--config PATH]

Refuses unpushed local commits and a VM checkout that has diverged. Content goes
through deploy_db instead. Plainly restarts and pip installs stay manual; the script
says when a change needs them.
"""
import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from distill.scripts.deploy_db import DEFAULT_CONFIG, REQUIRED_KEYS, DeployError, _gcloud_flags, load_settings


def _notes(changed: list) -> list:
    notes = []
    python_or_template = lambda p: p.endswith('.py') or p.startswith('shared/templates/')
    if any(p.startswith('plainly/') or (p.startswith('shared/') and python_or_template(p)) for p in changed):
        notes.append('This change also affects Plainly: restart it separately.')
    if any(Path(p).name == 'requirements.txt' for p in changed):
        notes.append('A requirements file changed: run pip install on the VM, then deploy again.')
    return notes


def deploy_code(settings: dict, run=subprocess.run) -> list:
    """Return messages for the operator."""
    missing = [key for key in REQUIRED_KEYS if not settings.get(key)]
    if missing:
        raise DeployError(f'missing deploy setting(s): {", ".join(missing)}')

    def local(*args: str) -> str:
        result = run(['git', *args], capture_output=True, text=True)
        if result.returncode != 0:
            raise DeployError(f'git {args[0]} failed: {(result.stderr or "").strip()}')
        return (result.stdout or '').strip()

    local('fetch', 'origin', '--quiet')
    head = local('rev-parse', 'HEAD')
    if head != local('rev-parse', 'origin/main'):
        raise DeployError('local HEAD is not origin/main: push it first; VM untouched')

    svc = shlex.quote(settings['DISTILL_VM_SERVICE_USER'])
    unit = settings['DISTILL_VM_UNIT']
    remote_db = settings['DISTILL_VM_REMOTE_DB']
    repo = shlex.quote(str(settings.get('DISTILL_VM_REPO_ROOT') or Path(remote_db).parent.parent))
    git = f'sudo -u {svc} git -C {repo}'

    def ssh(command: str, what: str) -> str:
        result = run(['gcloud', 'compute', 'ssh', settings['DISTILL_VM_INSTANCE'], f'--command={command}',
                      *_gcloud_flags(settings)], capture_output=True, text=True)
        if result.returncode != 0:
            raise DeployError(f'{what} failed: {(result.stderr or result.stdout or "").strip()}')
        return (result.stdout or '').strip()

    ssh(f'{git} fetch origin --quiet', 'VM git fetch')
    before = ssh(f'{git} rev-parse HEAD', 'reading the VM commit')
    notes = []
    if before == head:
        notes.append(f'VM is already at {head[:7]}: no restart.')
    else:
        ssh(f'{git} merge-base --is-ancestor HEAD origin/main', 'VM checkout has diverged from origin/main; ancestry check')
        ssh(f'{git} pull --ff-only origin main', 'VM git pull')
        after = ssh(f'{git} rev-parse HEAD', 'reading the VM commit')
        if after != head:
            raise DeployError(f'VM landed on {after[:7]}, expected {head[:7]}; Distill not restarted')
        changed = ssh(f'{git} diff --name-only {before} {head}', 'listing changed files').split()
        ctl = f'sudo -u {svc} XDG_RUNTIME_DIR=/run/user/$(id -u {svc}) systemctl --user'
        ssh(f'{ctl} restart {unit} && sleep 3 && {ctl} is-active {unit}', f'restart of {unit}')
        notes.append(f'VM updated {before[:7]} -> {head[:7]} and {unit} restarted.')
        notes.extend(_notes(changed))

    port = settings['DISTILL_VM_PORT']
    code = ssh(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/", 'local auth check')
    if code != '401':
        raise DeployError(f'expected HTTP 401 from the app (up, auth required), got {code!r}')
    return notes


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="Update the VM's code and restart Distill.")
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        for note in deploy_code(load_settings(args.config)):
            print(note)
    except DeployError as e:
        print(f'Deploy failed: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
