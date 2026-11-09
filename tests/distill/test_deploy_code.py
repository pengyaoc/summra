import subprocess

import pytest

from distill.scripts.deploy_code import deploy_code
from distill.scripts.deploy_db import DeployError

NEW, OLD = 'a' * 40, 'b' * 40
SETTINGS = {
    'DISTILL_VM_INSTANCE': 'vm-1', 'DISTILL_VM_ZONE': 'zone-a', 'DISTILL_VM_PROJECT': 'proj',
    'DISTILL_VM_ACCOUNT': 'me@example.com', 'DISTILL_VM_SERVICE_USER': 'svc',
    'DISTILL_VM_REMOTE_DB': '/opt/x/data/distill.db', 'DISTILL_VM_UNIT': 'distill.service',
    'DISTILL_VM_PORT': '5002',
}


class FakeRun:
    def __init__(self, overrides=None, changed='distill/routes.py\n'):
        self.calls = []
        self.vm_head = OLD
        self.overrides = overrides or {}
        self.changed = changed

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        line = ' '.join(argv)
        for needle, (code, out) in self.overrides.items():
            if needle in line:
                return subprocess.CompletedProcess(argv, code, out, 'failed')
        out = ''
        if argv[0] == 'git' and 'rev-parse' in argv:
            out = NEW + '\n'
        elif 'pull --ff-only' in line:
            self.vm_head = NEW
        elif 'rev-parse HEAD' in line:
            out = self.vm_head + '\n'
        elif 'diff --name-only' in line:
            out = self.changed
        elif 'curl' in line:
            out = '401'
        return subprocess.CompletedProcess(argv, 0, out, '')

    def lines(self):
        return [' '.join(c) for c in self.calls]

    def has(self, needle):
        return any(needle in line for line in self.lines())

    def index(self, needle):
        return next(i for i, line in enumerate(self.lines()) if needle in line)


def test_pulls_then_restarts_then_checks_auth():
    run = FakeRun()
    deploy_code(SETTINGS, run=run)
    order = [run.index(n) for n in ('compute ssh vm-1 --command=sudo -u svc git -C /opt/x fetch', 'merge-base --is-ancestor',
                                    'pull --ff-only origin main', 'restart distill.service', 'curl')]
    assert order == sorted(order) and len(set(order)) == len(order)
    restart = run.lines()[run.index('restart distill.service')]
    assert 'XDG_RUNTIME_DIR=/run/user/' in restart and 'is-active distill.service' in restart


def test_unpushed_local_commit_is_refused_before_touching_the_vm():
    run = FakeRun({'origin/main': (0, OLD + '\n')})
    with pytest.raises(DeployError, match='push'):
        deploy_code(SETTINGS, run=run)
    assert not run.has('compute ssh')


def test_already_current_does_not_restart():
    run = FakeRun()
    run.vm_head = NEW
    assert 'already' in deploy_code(SETTINGS, run=run)[0]
    assert not run.has('pull --ff-only') and not run.has('restart distill.service')
    assert run.has('curl')


def test_diverged_vm_is_refused_without_pulling():
    run = FakeRun({'merge-base --is-ancestor': (1, '')})
    with pytest.raises(DeployError, match='diverged'):
        deploy_code(SETTINGS, run=run)
    assert not run.has('pull --ff-only') and not run.has('restart')


def test_pull_landing_on_a_different_commit_stops_before_restart():
    run = FakeRun()
    run.__class__ = type('Stale', (FakeRun,), {})
    original = FakeRun.__call__

    def stale(self, argv, **kwargs):
        result = original(self, argv, **kwargs)
        self.vm_head = OLD
        return result

    run.__class__.__call__ = stale
    with pytest.raises(DeployError, match='landed'):
        deploy_code(SETTINGS, run=run)
    assert not run.has('restart')


def test_failed_restart_raises_and_skips_auth_check():
    run = FakeRun({'restart distill.service': (3, 'inactive')})
    with pytest.raises(DeployError, match='restart'):
        deploy_code(SETTINGS, run=run)
    assert not run.has('curl')


def test_app_not_behind_auth_raises():
    run = FakeRun({'curl': (0, '200')})
    with pytest.raises(DeployError, match='401'):
        deploy_code(SETTINGS, run=run)


@pytest.mark.parametrize('changed,word', [('shared/web.py\n', 'Plainly'), ('plainly/app.py\n', 'Plainly'),
                                          ('distill/requirements.txt\n', 'requirements')])
def test_warns_about_what_it_does_not_handle(changed, word):
    assert any(word in note for note in deploy_code(SETTINGS, run=FakeRun(changed=changed)))


def test_no_warning_for_distill_only_or_shared_static_changes():
    notes = deploy_code(SETTINGS, run=FakeRun(changed='distill/routes.py\nshared/static/js/listen.js\ndocs/ERD.md\n'))
    assert not any('Plainly' in n or 'requirements' in n for n in notes)


def test_missing_setting_names_the_key():
    settings = {k: v for k, v in SETTINGS.items() if k != 'DISTILL_VM_UNIT'}
    run = FakeRun()
    with pytest.raises(DeployError, match='DISTILL_VM_UNIT'):
        deploy_code(settings, run=run)
    assert run.calls == []
