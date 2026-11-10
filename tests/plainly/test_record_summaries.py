"""Summaries are recorded as files the Listen button finds, ahead of older Gemini ones."""
import pytest

from plainly import tts_utils
from plainly.scripts.audio import record_summaries
from shared.audio.spoken import spoken_checksum


class FakeEngine:
    name, lang, repeatable = 'fake', 'en', True
    def voice_id(self): return 'fake-voice'


@pytest.fixture
def env(test_db_path, tmp_path, monkeypatch):
    from plainly import models
    db = models.Database(db_path=test_db_path)
    book_id = db.add_book(title='Novel', author='A', filename='t.txt', full_text='Full.')
    db.update_book_slug(book_id, 'novel')
    db.add_summary(book_id, 'concise', '## Heading\n\nFirst **bold** part.\n\nSecond part.')
    static = tmp_path / 'static'
    (static / 'audio').mkdir(parents=True)
    monkeypatch.setattr(record_summaries.config, 'STATIC_DIR', static)
    monkeypatch.setattr(record_summaries.config, 'TTS_OUTPUT_DIR', static / 'audio')
    seen = []
    monkeypatch.setattr(record_summaries, 'engine_for', lambda lang, settings: FakeEngine())
    monkeypatch.setattr(record_summaries, 'check_reference', lambda *a, **k: None)

    def fake_render(units, engine, work_dir):
        seen.append(units)
        return b'opus', [], 10, spoken_checksum(units)

    monkeypatch.setattr(record_summaries, 'render_chapter', fake_render)
    return test_db_path, book_id, static, seen


def run(db_path, *args):
    return record_summaries.main(['--db', str(db_path), *args])


def test_recorded_summary_is_found_ahead_of_gemini(env):
    db_path, book_id, static, seen = env
    (static / 'audio' / f'book_{book_id}_concise_gemini.opus').write_bytes(b'old')
    assert run(db_path, '--book', 'novel', '--type', 'concise') == 0
    assert [u.parts for u in seen[0]] == [['Heading'], ['First bold part.'], ['Second part.']]
    found = tts_utils.check_cached_audio(f'book_{book_id}_concise', static / 'audio', static)
    assert found['audio_url'].endswith(f'book_{book_id}_concise.m4a') and found['provider'] == 'recorded'


def test_already_recorded_is_skipped_until_forced(env):
    db_path, _, _, seen = env
    run(db_path, '--book', 'novel', '--type', 'concise')
    run(db_path, '--book', 'novel', '--type', 'concise')
    assert len(seen) == 1
    run(db_path, '--book', 'novel', '--type', 'concise', '--force')
    assert len(seen) == 2


def test_dry_run_records_nothing(env, capsys):
    db_path, _, static, seen = env
    assert run(db_path, '--book', 'novel', '--type', 'concise', '--dry-run') == 0
    assert seen == [] and not list((static / 'audio').iterdir())
    assert 'to record' in capsys.readouterr().out


def test_book_without_that_summary_is_not_an_error(env):
    db_path, _, _, seen = env
    assert run(db_path, '--book', 'novel', '--type', 'medium') == 0
    assert seen == []


def test_unknown_book_fails(env):
    assert run(env[0], '--book', 'nope', '--type', 'concise') == 1
