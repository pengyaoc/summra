import pytest

from shared.audio.engines import RenderFailed, VoiceMismatch
from shared.audio import make_audio
from shared.audio.spoken import spoken_checksum, spoken_units
from distill.models import DistillDatabase


class FakeEngine:
    name, lang, repeatable = 'fake', 'en', True

    def voice_id(self):
        return 'fake-voice'


@pytest.fixture
def env(tmp_path, monkeypatch, sample_book, write_book):
    db_path = tmp_path / 'distill.db'
    db = DistillDatabase(db_path)
    first = db.import_book(write_book(sample_book))
    second_book = {**sample_book, 'slug': 'other-book', 'title': 'Other'}
    second = db.import_book(write_book(second_book))
    rendered, checks = [], []
    monkeypatch.setattr(make_audio, 'engine_for', lambda lang, settings: FakeEngine())
    monkeypatch.setattr(make_audio, 'check_reference', lambda engine, ref_dir, approve=False: checks.append(approve))

    def fake_render(units, engine, work_dir):
        chapter_id = int(units[0].paragraph_id.split('.')[0])
        rendered.append(chapter_id)
        return b'm4a-' + str(chapter_id).encode(), [], 10, spoken_checksum(units)

    monkeypatch.setattr(make_audio, 'render_chapter', fake_render)
    monkeypatch.setattr(make_audio, 'encode_opus', lambda aac, work_dir: b'opus-' + aac)
    return db, db_path, first, second, rendered, checks


def run(db_path, *args):
    return make_audio.main(['--app', 'distill', '--db', str(db_path), '--jobs', '1', '--config', '/nonexistent', *args])


def test_dry_run_writes_nothing(env, capsys):
    db, db_path, first, _, rendered, checks = env
    assert run(db_path, '--book', 'my-book', '--dry-run') == 0
    assert rendered == [] and checks == []
    assert db.book_audio(first) == []
    assert 'to render' in capsys.readouterr().out


def test_renders_then_skips_current_chapters(env):
    db, db_path, first, _, rendered, checks = env
    assert run(db_path, '--book', 'my-book') == 0
    count = len(db.get_chapters(first))
    assert len(rendered) == count and len(db.book_audio(first)) == count
    assert db.book_audio(first)[0]['timings'] == []
    rendered.clear()
    assert run(db_path, '--book', 'my-book') == 0
    assert rendered == []


def test_voice_mismatch_aborts_before_render(env, monkeypatch):
    _, db_path, _, _, rendered, _ = env

    def mismatch(engine, ref_dir, approve=False):
        raise VoiceMismatch('changed')

    monkeypatch.setattr(make_audio, 'check_reference', mismatch)
    assert run(db_path, '--all') == 1
    assert rendered == []


def test_approve_voice_is_passed_through(env):
    _, db_path, _, _, _, checks = env
    assert run(db_path, '--book', 'my-book', '--approve-voice') == 0
    assert checks == [True]


def test_render_failure_stops_book_continues_next(env, monkeypatch):
    db, db_path, first, second, rendered, _ = env
    first_ids = {c['id'] for c in db.get_chapters(first)}

    def flaky(units, engine, work_dir):
        chapter_id = int(units[0].paragraph_id.split('.')[0])
        rendered.append(chapter_id)
        if chapter_id in first_ids:
            raise RenderFailed('siri down')
        return b'x' + str(chapter_id).encode(), [], 10, spoken_checksum(units)

    monkeypatch.setattr(make_audio, 'render_chapter', flaky)
    assert run(db_path, '--all') == 1
    assert len([c for c in rendered if c in first_ids]) == 1
    assert len(db.book_audio(second)) == len(db.get_chapters(second))


def test_unknown_book_fails(env):
    assert run(env[1], '--book', 'nope') == 1


def test_deploy_with_dry_run_rejected(env):
    with pytest.raises(SystemExit):
        run(env[1], '--book', 'my-book', '--dry-run', '--deploy')


def test_render_stores_only_the_opus_file(env, monkeypatch):
    db, db_path, first, _, _, _ = env
    monkeypatch.setattr(make_audio, 'encode_opus', lambda *a: pytest.fail('new renders are not re-encoded'))
    assert run(db_path, '--book', 'my-book') == 0
    assert db.missing_deploy_audio() == []
    chapter_id = db.get_chapters(first)[0]['id']
    item = db.book_audio(first)[0]
    assert item['deploy_key'] == item['storage_key']
    assert db.media.get(item['deploy_key']) == b'm4a-' + str(chapter_id).encode()


def test_opus_only_encodes_missing_copies_without_rendering(env):
    db, db_path, first, _, rendered, checks = env
    chapter = db.get_chapters(first)[0]
    db.save_chapter_audio(chapter['id'], b'old-aac', [], 10, spoken_checksum(spoken_units(chapter)), 'v', 'say', None)
    assert db.missing_deploy_audio() == [chapter['id']]
    assert run(db_path, '--all', '--opus-only') == 0
    assert rendered == [] and checks == []
    assert db.missing_deploy_audio() == []
    assert db.media.get(db.book_audio(first)[0]['deploy_key']) == b'opus-old-aac'
