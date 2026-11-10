"""Plainly records with the same command as Distill, without the Gemini API."""
from pathlib import Path

import pytest

from shared.audio import make_audio
from shared.audio.spoken import spoken_checksum


class FakeEngine:
    name, lang, repeatable = 'fake', 'en', True
    def voice_id(self): return 'fake-voice'


@pytest.fixture
def env(test_db_path, tmp_path, monkeypatch):
    from plainly import models
    db = models.Database(db_path=test_db_path)
    book_id = db.add_book(title='The Test Novel', author='Jane Doe', filename='t.txt', full_text='Full.')
    db.update_book_slug(book_id, 'the-test-novel')
    db.add_chapter(book_id, 1, 'One', 'A summary.', chapter_text='First.\n\nSecond.')
    db.add_chapter(book_id, 2, 'Empty', 'A summary.', chapter_text='')
    seen, langs = [], []
    monkeypatch.setattr(make_audio, 'engine_for', lambda lang, settings: langs.append(lang) or FakeEngine())
    monkeypatch.setattr(make_audio, 'check_reference', lambda *a, **k: None)

    def fake_render(units, engine, work_dir):
        seen.append([u.parts for u in units])
        return b'opus', [], 10, spoken_checksum(units)

    monkeypatch.setattr(make_audio, 'render_chapter', fake_render)
    monkeypatch.setattr('plainly.config.AUDIO_MEDIA_DIR', tmp_path / 'media')
    return db, book_id, Path(test_db_path), seen, langs


def run(db_path, *args):
    return make_audio.main(['--app', 'plainly', '--db', str(db_path), '--jobs', '1', '--config', '/nonexistent', *args])


def test_records_a_book_chapter_with_no_gemini(env):
    db, book_id, db_path, seen, langs = env
    assert run(db_path, '--book', 'the-test-novel', '--mode', 'original') == 0
    assert seen == [[['First.'], ['Second.']]] and langs[0] == 'en'
    assert [c['title'] for c in db.book_audio(book_id, 'original')] == ['One']


def test_a_chapter_with_nothing_to_say_is_skipped_and_stays_done(env):
    _, _, db_path, seen, _ = env
    assert run(db_path, '--book', 'the-test-novel', '--mode', 'original') == 0
    assert run(db_path, '--book', 'the-test-novel', '--mode', 'original') == 0
    assert len(seen) == 1


def test_a_book_in_chinese_uses_the_chinese_voice(env, monkeypatch):
    from plainly import audio_app
    _, _, db_path, _, langs = env
    original = audio_app.books
    monkeypatch.setattr(audio_app, 'books', lambda db: [{**b, 'lang': 'zh'} for b in original(db)])
    assert run(db_path, '--all', '--mode', 'original') == 0
    assert 'zh' in langs


def test_plainly_has_no_deploy_yet(env, capsys):
    _, _, db_path, seen, _ = env
    assert run(db_path, '--book', 'the-test-novel', '--mode', 'original', '--deploy') == 2
    assert seen == [] and 'deploy' in capsys.readouterr().err.lower()


def test_gemini_speech_is_gone():
    with pytest.raises(ModuleNotFoundError):
        __import__('plainly.gemini_tts_handler')
