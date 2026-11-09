import hashlib
import json
import sqlite3
import subprocess
import tarfile

import pytest

from distill.scripts import push_book
from distill.scripts.db_patch import row_hashes
from distill.scripts.deploy_db import DeployError, deploy_db, load_settings

SETTINGS = {
    'DISTILL_VM_INSTANCE': 'vm-1', 'DISTILL_VM_ZONE': 'zone-a', 'DISTILL_VM_PROJECT': 'proj',
    'DISTILL_VM_ACCOUNT': 'me@example.com', 'DISTILL_VM_SERVICE_USER': 'svc',
    'DISTILL_VM_REMOTE_DB': '/opt/x/data/distill.db', 'DISTILL_VM_UNIT': 'distill.service',
    'DISTILL_VM_PORT': '5002', 'DISTILL_SITE_URL': 'https://example.com/distill',
}


@pytest.fixture
def db_path(tmp_path, sample_book, write_book):
    from distill.models import DistillDatabase
    db = DistillDatabase(tmp_path / 'distill.db')
    db.import_book(write_book(sample_book))
    return db.db_path


EMPTY_LIVE = json.dumps({'tables': {}, 'slugs': {}})


class FakeRun:
    """Records argv; scripted results are matched by a substring of the full command line."""

    def __init__(self, overrides=None):
        self.overrides = overrides or {}
        self.calls = []
        self.media_sha = None
        self.media_members = []
        self.patch_sha = None
        self.patch = None
        self.after_patch = None  # the VM's row hashes once the patch has been applied
        self.applied = False
        self.installed = []
        self.lose_media = False

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        line = ' '.join(argv)
        self.applied = self.applied or 'db_patch apply' in line
        if 'db_patch hashes' in line and self.applied and self.after_patch is not None:
            return subprocess.CompletedProcess(argv, 0, self.after_patch, '')
        if 'media_transfer install' in line and not self.lose_media:
            self.installed = [name.split('/')[-1] for name in self.media_members]
        if 'media_transfer list' in line and 'media_transfer list' not in self.failing():
            held = self.overrides.get('media_transfer list', (0, ''))[1].split()
            return subprocess.CompletedProcess(argv, 0, '\n'.join([*held, *self.installed]), '')
        for needle, (code, out) in self.overrides.items():
            if needle in line:
                return subprocess.CompletedProcess(argv, code, out, '')
        if argv[:3] == ['gcloud', 'compute', 'scp'] and argv[4].endswith(':distill-media.new.tar'):
            from pathlib import Path
            self.media_sha = hashlib.sha256(Path(argv[3]).read_bytes()).hexdigest()
            with tarfile.open(argv[3]) as tar:
                self.media_members = tar.getnames()
        if argv[:3] == ['gcloud', 'compute', 'scp'] and argv[4].endswith(':distill.patch.json'):
            from pathlib import Path
            self.patch_sha = hashlib.sha256(Path(argv[3]).read_bytes()).hexdigest()
            self.patch = json.loads(Path(argv[3]).read_text())
            if self.after_patch is None:  # a healthy VM ends up exactly like the snapshot
                with sqlite3.connect(Path(argv[3]).with_name('distill.db')) as snapshot:
                    self.after_patch = json.dumps(row_hashes(snapshot))
        if 'sha256sum' in line:
            sha = self.patch_sha if 'distill.patch.json' in line else self.media_sha
            return subprocess.CompletedProcess(argv, 0, f'{sha}  upload', '')
        if 'db_patch hashes' in line:
            return subprocess.CompletedProcess(argv, 0, EMPTY_LIVE, '')
        if 'curl' in line:
            return subprocess.CompletedProcess(argv, 0, '401', '')
        return subprocess.CompletedProcess(argv, 0, '', '')

    def failing(self):
        return [needle for needle, (code, _) in self.overrides.items() if code != 0]

    def audio(self):
        change = self.patch['upsert']['chapter_audio']
        return [(dict(zip(change['columns'], row))['storage_key'], dict(zip(change['columns'], row))['deploy_key'])
                for row in change['rows']]

    def lines(self):
        return [' '.join(c) for c in self.calls]

    def index(self, needle):
        return next(i for i, line in enumerate(self.lines()) if needle in line)

    def has(self, needle):
        return any(needle in line for line in self.lines())


def make_run(db_path, overrides=None):
    return FakeRun(overrides)


def test_happy_path_sends_a_patch_without_touching_the_service(db_path):
    run = make_run(db_path)

    deploy_db(db_path, SETTINGS, run=run)

    order = [run.index(n) for n in (
        'test -f /opt/x/data/distill.db', 'db_patch hashes',
        'media_transfer backup --db /opt/x/data/distill.db',
        'vm-1:distill.patch.json', 'sha256sum ~/distill.patch.json', 'db_patch apply', 'curl')]
    assert order == sorted(order)
    assert len(set(order)) == len(order)
    for call in run.calls:
        assert call[:3] in (['gcloud', 'compute', 'ssh'], ['gcloud', 'compute', 'scp'])
        assert '--zone=zone-a' in call and '--project=proj' in call and '--account=me@example.com' in call
    apply = run.lines()[run.index('db_patch apply')]
    assert 'sudo -u svc' in apply and '< ~/distill.patch.json' in apply  # WAL files stay the service's
    assert 'http://127.0.0.1:5002/' in run.lines()[run.index('curl')]
    assert not run.has('systemctl') and not run.has('sudo mv') and not run.has('distill.db.new')
    assert run.has('rm -f ~/distill.patch.json')


def test_nothing_changed_sends_nothing(db_path):
    with sqlite3.connect(db_path) as conn:
        live = json.dumps(row_hashes(conn))
    run = make_run(db_path, {'db_patch hashes': (0, live), 'media_transfer list': (0, '')})

    deploy_db(db_path, SETTINGS, run=run)

    assert not run.has('db_patch apply') and not run.has('media_transfer backup')
    assert not run.has('distill.patch.json')


def test_missing_live_db_is_refused(db_path):
    run = make_run(db_path, {'test -f': (1, '')})

    with pytest.raises(DeployError, match='live database'):
        deploy_db(db_path, SETTINGS, run=run)

    assert not run.has('db_patch apply')


def test_conflicting_live_book_stops_before_any_upload(db_path):
    with sqlite3.connect(db_path) as conn:
        live = row_hashes(conn)
    live['slugs'] = {book_id: 'someone-else' for book_id in live['slugs']}
    run = make_run(db_path, {'db_patch hashes': (0, json.dumps(live))})

    with pytest.raises(DeployError, match='someone-else'):
        deploy_db(db_path, SETTINGS, run=run)

    assert not run.has('compute scp') and not run.has('db_patch apply')


def test_sha_mismatch_aborts_before_apply(db_path):
    run = make_run(db_path, {'sha256sum ~/distill.patch.json': (0, 'deadbeef x')})

    with pytest.raises(DeployError, match='SHA256'):
        deploy_db(db_path, SETTINGS, run=run)

    assert not run.has('db_patch apply')


@pytest.mark.parametrize('key', [k for k in sorted(SETTINGS) if k != 'DISTILL_SITE_URL'])
def test_missing_setting_names_the_key(db_path, key):
    settings = {k: v for k, v in SETTINGS.items() if k != key}
    run = make_run(db_path)

    with pytest.raises(DeployError, match=key):
        deploy_db(db_path, settings, run=run)

    assert run.calls == []


def test_apply_failure_raises(db_path):
    run = make_run(db_path, {'db_patch apply': (1, 'boom')})

    with pytest.raises(DeployError, match='patch'):
        deploy_db(db_path, SETTINGS, run=run)

    assert not run.has('curl')


def test_auth_check_not_401_raises(db_path):
    run = make_run(db_path, {'curl': (0, '200')})

    with pytest.raises(DeployError, match='401'):
        deploy_db(db_path, SETTINGS, run=run)


def test_backup_uses_one_latest_app_archive(db_path):
    run = make_run(db_path)

    deploy_db(db_path, SETTINGS, run=run)

    assert run.has('media_transfer backup --db /opt/x/data/distill.db --owner svc')
    assert not run.has('bak-pre-push')
    assert not run.has('tail -n')


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


@pytest.fixture
def file_media_db(tmp_path, sample_book, write_book):
    from distill.models import DistillDatabase
    db = DistillDatabase(tmp_path / 'distill.db')
    db.import_book(write_book(sample_book))
    return db


def test_media_verified_and_installed_before_database_activation(file_media_db):
    db = file_media_db
    run = make_run(db.db_path)
    deploy_db(db.db_path, SETTINGS, run=run)
    assert sorted(run.media_members) == [f'{key[:2]}/{key}' for key in db.media_keys()]
    assert run.index('sha256sum') < run.index('media_transfer install') < run.index('db_patch apply')
    assert run.has('--media-dir /opt/x/data/distill-media')
    assert run.has('rm -f ~/distill-media.new.tar')


@pytest.mark.parametrize('failure', ['sha256sum', 'media_transfer install'])
def test_bad_media_upload_never_stops_service(file_media_db, failure):
    run = make_run(file_media_db.db_path, {failure: (1, 'failed')})
    with pytest.raises(DeployError):
        deploy_db(file_media_db.db_path, SETTINGS, run=run)
    assert not run.has('db_patch apply')


def test_missing_local_media_aborts_without_remote_calls(file_media_db):
    db = file_media_db
    db.media.path(db.media_keys()[0]).unlink()
    run = make_run(db.db_path)
    with pytest.raises(DeployError, match='Media'):
        deploy_db(db.db_path, SETTINGS, run=run)
    assert run.calls == []


def test_deploy_uploads_only_missing(file_media_db):
    db = file_media_db
    keys = db.media_keys()
    assert len(keys) >= 2
    run = make_run(db.db_path, {'media_transfer list': (0, keys[0] + '\n')})
    deploy_db(db.db_path, SETTINGS, run=run)
    assert sorted(run.media_members) == [f'{k[:2]}/{k}' for k in keys[1:]]
    assert run.index('media_transfer list') < run.index('distill-media.new.tar')


def test_deploy_skips_media_upload_when_vm_has_everything(file_media_db):
    db = file_media_db
    run = make_run(db.db_path, {'media_transfer list': (0, '\n'.join(db.media_keys()) + '\n')})
    deploy_db(db.db_path, SETTINGS, run=run)
    assert not run.has('distill-media.new.tar')
    assert run.has('db_patch apply')


def test_remote_media_list_failure_never_stops_service(file_media_db):
    run = make_run(file_media_db.db_path, {'media_transfer list': (1, 'boom')})
    with pytest.raises(DeployError):
        deploy_db(file_media_db.db_path, SETTINGS, run=run)
    assert not run.has('db_patch apply')


def test_deploy_ships_opus_not_master(file_media_db):
    db = file_media_db
    chapter_id = db.get_chapters(db.list_books()[0]['id'])[0]['id']
    master = db.save_chapter_audio(chapter_id, b'aac-master', [], 1, 'c', 'say:system', 'say', None)
    opus = db.set_deploy_audio(chapter_id, b'opus-copy')
    run = make_run(db.db_path)
    deploy_db(db.db_path, SETTINGS, run=run)
    assert f'{opus[:2]}/{opus}' in run.media_members
    assert f'{master[:2]}/{master}' not in run.media_members
    assert run.audio() == [(opus, opus)]
    assert db.get_chapter_audio_key(chapter_id) == master  # local master untouched


def test_deploy_ships_master_when_no_opus_yet(file_media_db):
    db = file_media_db
    chapter_id = db.get_chapters(db.list_books()[0]['id'])[0]['id']
    master = db.save_chapter_audio(chapter_id, b'aac-master', [], 1, 'c', 'say:system', 'say', None)
    run = make_run(db.db_path)
    deploy_db(db.db_path, SETTINGS, run=run)
    assert f'{master[:2]}/{master}' in run.media_members
    assert run.audio() == [(master, None)]


def test_every_deploy_rereads_the_vm_after_applying(db_path):
    run = make_run(db_path)

    summary = deploy_db(db_path, SETTINGS, run=run)

    apply = run.index('db_patch apply')
    check = run.index('db_patch check')
    assert apply < check
    assert 'sudo -u svc' in run.lines()[check] and '--db /opt/x/data/distill.db' in run.lines()[check]
    assert sum('db_patch hashes' in line for line in run.lines()) == 2
    assert [i for i, line in enumerate(run.lines()) if 'db_patch hashes' in line][-1] > apply
    assert summary['changed'] > 0 and summary['rows'] >= summary['changed']


def test_rerun_with_no_changes_still_verifies_the_vm(db_path):
    with sqlite3.connect(db_path) as conn:
        live = json.dumps(row_hashes(conn))
    run = make_run(db_path, {'db_patch hashes': (0, live)})

    summary = deploy_db(db_path, SETTINGS, run=run)

    assert run.has('db_patch check') and not run.has('db_patch apply')
    assert summary['changed'] == 0 and summary['rows'] > 0


def test_vm_rows_that_still_differ_after_applying_fail_the_deploy(db_path):
    run = make_run(db_path)
    run.after_patch = EMPTY_LIVE  # the patch "applied" but the rows are not there

    with pytest.raises(DeployError, match=r'row\(s\) still differ'):
        deploy_db(db_path, SETTINGS, run=run)


def test_vm_integrity_failure_fails_the_deploy(db_path):
    run = make_run(db_path, {'db_patch check': (1, 'foreign key problem')})

    with pytest.raises(DeployError, match='foreign key problem'):
        deploy_db(db_path, SETTINGS, run=run)


def test_media_missing_on_the_vm_after_install_fails_the_deploy(file_media_db):
    run = make_run(file_media_db.db_path)
    run.lose_media = True

    with pytest.raises(DeployError, match=r'media file\(s\) missing'):
        deploy_db(file_media_db.db_path, SETTINGS, run=run)


def test_main_reports_what_was_verified(db_path, monkeypatch, capsys):
    from distill.scripts import deploy_db as module
    monkeypatch.setattr(module, 'deploy_db', lambda *a, **k: {'changed': 3, 'rows': 40, 'media': 7})
    monkeypatch.setattr(module, 'load_settings', lambda path: SETTINGS)

    assert module.main(['--db', str(db_path)]) == 0

    out = capsys.readouterr().out
    assert '3 row(s) changed' in out and '40 rows match' in out and '7 media files' in out


def _old_audio_db():
    import sqlite3
    conn = sqlite3.connect(':memory:')
    conn.execute('''CREATE TABLE chapter_audio (chapter_id INTEGER PRIMARY KEY, storage_key TEXT NOT NULL,
        text_checksum TEXT NOT NULL, duration_ms INTEGER NOT NULL, voice TEXT NOT NULL, engine TEXT NOT NULL,
        rate REAL, timings TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, deploy_key TEXT)''')
    conn.execute("INSERT INTO chapter_audio (chapter_id, storage_key, text_checksum, duration_ms, voice, engine, timings, deploy_key) "
                 "VALUES (7, 'a.m4a', 'c', 1, 'v', 'e', '[]', 'a.opus')")
    return conn


def test_a_snapshot_with_the_old_audio_key_is_migrated_before_comparing():
    from distill.scripts.deploy_db import _ship_deploy_audio
    conn = _old_audio_db()
    _ship_deploy_audio(conn)
    key = [row[1] for row in sorted((r for r in conn.execute('PRAGMA table_info(chapter_audio)') if r[5]), key=lambda r: r[5])]
    assert key == ['chapter_id', 'mode']
    assert conn.execute('SELECT mode, storage_key FROM chapter_audio').fetchall() == [('summary', 'a.opus')]


def test_migrating_an_up_to_date_snapshot_changes_nothing():
    from distill.scripts.deploy_db import _ship_deploy_audio
    conn = _old_audio_db()
    _ship_deploy_audio(conn)
    _ship_deploy_audio(conn)
    assert conn.execute('SELECT COUNT(*) FROM chapter_audio').fetchone() == (1,)
