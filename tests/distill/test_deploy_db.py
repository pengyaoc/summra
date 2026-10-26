import hashlib
import sqlite3
import subprocess

import pytest

from distill.scripts import push_book
from distill.scripts.deploy_db import DeployError, deploy_db, load_settings

SETTINGS = {
    'DISTILL_VM_INSTANCE': 'vm-1', 'DISTILL_VM_ZONE': 'zone-a', 'DISTILL_VM_PROJECT': 'proj',
    'DISTILL_VM_ACCOUNT': 'me@example.com', 'DISTILL_VM_SERVICE_USER': 'svc',
    'DISTILL_VM_REMOTE_DB': '/opt/x/data/distill.db', 'DISTILL_VM_UNIT': 'distill.service',
    'DISTILL_VM_PORT': '5002', 'DISTILL_SITE_URL': 'https://example.com/distill',
}


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / 'distill.db'
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE t (x)')
    conn.execute('INSERT INTO t VALUES (1)')
    conn.commit()
    conn.close()
    return path


class FakeRun:
    """Records argv; scripted results are matched by a substring of the full command line."""

    def __init__(self, md5, overrides=None):
        self.md5 = md5
        self.overrides = overrides or {}
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        line = ' '.join(argv)
        for needle, (code, out) in self.overrides.items():
            if needle in line:
                return subprocess.CompletedProcess(argv, code, out, '')
        if 'md5sum' in line:
            return subprocess.CompletedProcess(argv, 0, f'{self.md5}  /home/u/distill.db.new\n', '')
        if 'curl' in line:
            return subprocess.CompletedProcess(argv, 0, '401', '')
        return subprocess.CompletedProcess(argv, 0, '', '')

    def lines(self):
        return [' '.join(c) for c in self.calls]

    def index(self, needle):
        return next(i for i, line in enumerate(self.lines()) if needle in line)

    def has(self, needle):
        return any(needle in line for line in self.lines())


def make_run(db_path, overrides=None):
    # deploy_db checkpoints first, so hash the file in its checkpointed state.
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    conn.close()
    return FakeRun(hashlib.md5(db_path.read_bytes()).hexdigest(), overrides)


def test_happy_path_command_sequence(db_path):
    run = make_run(db_path)

    deploy_db(db_path, SETTINGS, run=run)

    order = [run.index(n) for n in (
        'test -f /opt/x/data/distill.db',
        'sudo cp /opt/x/data/distill.db /opt/x/data/distill.db.bak-pre-push-',
        'compute scp', 'md5sum', 'systemctl --user stop distill.service',
        'curl', 'tail -n +3')]
    assert order == sorted(order)
    assert len(set(order)) == len(order)
    for call in run.calls:
        assert call[:3] in (['gcloud', 'compute', 'ssh'], ['gcloud', 'compute', 'scp'])
        assert '--zone=zone-a' in call and '--project=proj' in call and '--account=me@example.com' in call
    scp = run.calls[run.index('compute scp')]
    assert str(db_path) in scp and 'vm-1:distill.db.new' in scp
    service = run.lines()[run.index('systemctl --user stop')]
    for fragment in ('id -u svc', 'XDG_RUNTIME_DIR=/run/user/', 'sudo mv', 'chown svc:svc',
                     'chmod 664', 'systemctl --user start distill.service', 'sleep 3',
                     'systemctl --user is-active distill.service'):
        assert fragment in service
    assert 'http://127.0.0.1:5002/' in run.lines()[run.index('curl')]
    assert not run.has('distill_user.db')


def test_no_snapshot_when_remote_db_missing(db_path):
    run = make_run(db_path, {'test -f': (1, '')})

    deploy_db(db_path, SETTINGS, run=run)

    assert not run.has('sudo cp')
    assert run.has('systemctl --user stop')


def test_md5_mismatch_aborts_before_stop_or_mv(db_path):
    run = make_run(db_path)
    run.md5 = 'deadbeef'

    with pytest.raises(DeployError, match='md5'):
        deploy_db(db_path, SETTINGS, run=run)

    assert not run.has('systemctl')
    assert not run.has('sudo mv')


@pytest.mark.parametrize('key', [k for k in sorted(SETTINGS) if k != 'DISTILL_SITE_URL'])
def test_missing_setting_names_the_key(db_path, key):
    settings = {k: v for k, v in SETTINGS.items() if k != key}
    run = make_run(db_path)

    with pytest.raises(DeployError, match=key):
        deploy_db(db_path, settings, run=run)

    assert run.calls == []


def test_is_active_failure_raises(db_path):
    run = make_run(db_path, {'systemctl --user stop': (3, 'inactive')})

    with pytest.raises(DeployError, match='service'):
        deploy_db(db_path, SETTINGS, run=run)

    assert not run.has('curl')


def test_auth_check_not_401_raises(db_path):
    run = make_run(db_path, {'curl': (0, '200')})

    with pytest.raises(DeployError, match='401'):
        deploy_db(db_path, SETTINGS, run=run)


def test_prune_keeps_newest_two(db_path):
    run = make_run(db_path)

    deploy_db(db_path, SETTINGS, run=run)

    prune = run.lines()[run.index('tail -n +3')]
    assert 'ls -1t' in prune and 'bak-pre-push-*' in prune and 'rm -f' in prune


def test_missing_db_file_raises(tmp_path):
    with pytest.raises(DeployError, match='distill.db'):
        deploy_db(tmp_path / 'distill.db', SETTINGS, run=FakeRun('x'))


def test_load_settings_parses_and_reports_missing_file(tmp_path):
    cfg = tmp_path / 'deploy.env'
    cfg.write_text('# comment\n\nA=1\nB = two=2\n')

    assert load_settings(cfg) == {'A': '1', 'B': 'two=2'}
    with pytest.raises(DeployError, match='nope.env'):
        load_settings(tmp_path / 'nope.env')


def _write_config(tmp_path):
    cfg = tmp_path / 'deploy.env'
    cfg.write_text('\n'.join(f'{k}={v}' for k, v in SETTINGS.items()))
    return cfg


def test_push_book_deploy_calls_deploy_after_import_and_prints_url(
        sample_book, write_book, tmp_path, monkeypatch, capsys):
    folder = write_book(sample_book)
    db_path = tmp_path / 'distill.db'
    cfg = _write_config(tmp_path)
    seen = []
    monkeypatch.setattr(push_book, 'deploy_db', lambda path, settings: seen.append((path, db_path.exists())))

    assert push_book.main([str(folder), '--db', str(db_path), '--deploy', '--config', str(cfg)]) == 0

    assert seen == [(db_path, True)]  # DB already imported when deploy runs
    out = capsys.readouterr().out
    assert out.index('Imported') < out.index('https://example.com/distill/books/my-book')


def test_push_book_deploy_failure_returns_1(sample_book, write_book, tmp_path, monkeypatch, capsys):
    folder = write_book(sample_book)
    cfg = _write_config(tmp_path)

    def boom(path, settings):
        raise DeployError('kaboom')
    monkeypatch.setattr(push_book, 'deploy_db', boom)

    assert push_book.main([str(folder), '--db', str(tmp_path / 'd.db'), '--deploy', '--config', str(cfg)]) == 1
    out = capsys.readouterr()
    assert 'kaboom' in out.out + out.err
    assert 'https://' not in out.out


def test_push_book_deploy_with_dry_run_is_rejected(sample_book, write_book, tmp_path):
    folder = write_book(sample_book)

    with pytest.raises(SystemExit) as exc:
        push_book.main([str(folder), '--dry-run', '--deploy', '--db', str(tmp_path / 'd.db')])

    assert exc.value.code == 2
