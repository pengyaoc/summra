import json
import subprocess
import wave
from pathlib import Path

import pytest

from distill.audio import engines
from distill.audio.engines import (
    RenderFailed, Rendered, SayEngine, SiriEngine, VoiceMismatch, VoiceUnavailable,
    check_reference, engine_for,
)

SETTINGS = {'DISTILL_SIRI_TTS_PATH': '/x/pipeline', 'DISTILL_SIRI_PYTHON': '/x/python'}


def write_wav(path: Path, frames: bytes, rate=22050):
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(frames)


class FakeEngine:
    name, lang, repeatable = 'fake', 'en', True

    def __init__(self, frames=b'\x01\x00' * 100):
        self.frames = frames

    def voice_id(self):
        return 'fake'

    def render(self, text, out_wav):
        write_wav(out_wav, self.frames * 100)
        return engines._wav_info(out_wav)


def test_engine_for_lang():
    assert isinstance(engine_for('en', SETTINGS), SayEngine)
    assert isinstance(engine_for('zh', SETTINGS), SiriEngine)
    with pytest.raises(ValueError):
        engine_for('fr', SETTINGS)


def test_siri_retries_then_fails(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if 'voices()' in cmd[-1]:
            return subprocess.CompletedProcess(cmd, 0, json.dumps([{'name': 'zh-CN-D'}]), '')
        return subprocess.CompletedProcess(cmd, 1, '', 'sirittsd connection error')

    monkeypatch.setattr(engines.subprocess, 'run', fake_run)
    with pytest.raises(RenderFailed):
        SiriEngine(Path('/x/pipeline'), Path('/x/python')).render('你好', tmp_path / 'a.wav')
    assert sum('synthesize' in c[-1] for c in calls) == 3


def test_siri_missing_voice_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(engines.subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 0, json.dumps([{'name': 'zh-CN-C'}]), ''))
    with pytest.raises(VoiceUnavailable):
        SiriEngine(Path('/x/pipeline'), Path('/x/python')).render('你好', tmp_path / 'a.wav')


def test_reference_missing_without_approve_raises(tmp_path):
    with pytest.raises(VoiceMismatch):
        check_reference(FakeEngine(), tmp_path)


def test_reference_approve_writes_then_passes(tmp_path):
    check_reference(FakeEngine(), tmp_path, approve=True)
    assert (tmp_path / 'fake.json').is_file()
    check_reference(FakeEngine(), tmp_path)


def test_reference_mismatch_raises(tmp_path):
    check_reference(FakeEngine(), tmp_path, approve=True)
    with pytest.raises(VoiceMismatch):
        check_reference(FakeEngine(frames=b'\x02\x00' * 100), tmp_path)


def test_reference_non_repeatable_uses_duration_tolerance(tmp_path):
    engine = FakeEngine()
    engine.repeatable = False
    check_reference(engine, tmp_path, approve=True)
    other = FakeEngine(frames=b'\x02\x00' * 101)  # same length within 2%, different bytes
    other.repeatable = False
    check_reference(other, tmp_path)
    far = FakeEngine(frames=b'\x02\x00' * 150)
    far.repeatable = False
    with pytest.raises(VoiceMismatch):
        check_reference(far, tmp_path)


def test_say_retries_after_a_hang_then_succeeds(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[0])
        assert kwargs.get('timeout'), 'every voice call needs a timeout'
        if cmd[0] == 'say' and calls.count('say') == 1:
            raise subprocess.TimeoutExpired(cmd, kwargs['timeout'])
        if cmd[0] == 'afconvert':
            write_wav(Path(cmd[-1]), b'\x01\x00' * 2205)
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(engines.subprocess, 'run', fake_run)
    rendered = SayEngine().render('Hello.', tmp_path / 'a.wav')
    assert calls.count('say') == 2 and rendered.duration_ms == 100


def test_say_hangs_three_times_fails(monkeypatch, tmp_path):
    def hang(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get('timeout'))

    monkeypatch.setattr(engines.subprocess, 'run', hang)
    with pytest.raises(RenderFailed):
        SayEngine().render('Hello.', tmp_path / 'a.wav')


def test_siri_hang_counts_as_a_failed_attempt(monkeypatch, tmp_path):
    attempts = []

    def fake_run(cmd, **kwargs):
        if 'voices()' in cmd[-1]:
            return subprocess.CompletedProcess(cmd, 0, json.dumps([{'name': 'zh-CN-D'}]), '')
        attempts.append(kwargs.get('timeout'))
        raise subprocess.TimeoutExpired(cmd, kwargs.get('timeout'))

    monkeypatch.setattr(engines.subprocess, 'run', fake_run)
    with pytest.raises(RenderFailed):
        SiriEngine(Path('/x/pipeline'), Path('/x/python')).render('你好', tmp_path / 'a.wav')
    assert len(attempts) == 3 and all(attempts)


def test_say_records_at_48khz(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == 'afconvert':
            write_wav(Path(cmd[-1]), b'\x01\x00' * 2205)
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(engines.subprocess, 'run', fake_run)
    SayEngine().render('Hello.', tmp_path / 'a.wav')
    assert '--data-format=BEI16@48000' in calls[0]


# Siri stops at about 26 s of speech per sentence (roughly 130 Chinese characters)
# and reports success, so a long sentence silently loses its end.
LONG_SENTENCE = '，'.join(f'第{n}段很长的内容需要完整读出来' for n in range(30)) + '。'


def test_split_for_siri_keeps_every_character_under_the_limit():
    chunks = engines.split_for_siri(LONG_SENTENCE)
    assert ''.join(chunks) == LONG_SENTENCE
    assert len(chunks) > 1 and all(len(c) <= engines.SIRI_CHUNK_CHARS for c in chunks)
    assert all(c[-1] in '，。' for c in chunks)  # cut at punctuation, not mid-phrase


def test_split_for_siri_leaves_short_text_whole():
    assert engines.split_for_siri('你好。') == ['你好。']


def test_split_for_siri_prefers_sentence_ends():
    first, second = '一' * 60 + '。', '二' * 60 + '，后面还有。'
    assert engines.split_for_siri(first + second) == [first, second]


def test_split_for_siri_cuts_text_with_no_punctuation():
    text = '字' * 200
    chunks = engines.split_for_siri(text)
    assert ''.join(chunks) == text and all(len(c) <= engines.SIRI_CHUNK_CHARS for c in chunks)


def test_split_for_siri_never_leaves_punctuation_alone():
    text = '字' * engines.SIRI_CHUNK_CHARS + '”。'
    assert all(any(ch == '字' for ch in c) for c in engines.split_for_siri(text))


def _fake_siri(monkeypatch, seconds_for):
    spoken = []

    def fake_run(cmd, **kwargs):
        if 'voices()' in cmd[-1]:
            return subprocess.CompletedProcess(cmd, 0, json.dumps([{'name': 'zh-CN-D'}]), '')
        spoken.append(kwargs['input'])
        out = cmd[-1].split('synthesize(sys.stdin.read(), "zh-CN", ')[1].split(',')[0].strip("'\"")
        write_wav(Path(out), b'\x01\x00' * int(1000 * seconds_for(kwargs['input'])), rate=1000)
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(engines.subprocess, 'run', fake_run)
    return spoken


def test_siri_records_long_text_in_pieces_and_joins_them(monkeypatch, tmp_path):
    spoken = _fake_siri(monkeypatch, lambda text: 1)
    rendered = SiriEngine(Path('/x/pipeline'), Path('/x/python')).render(LONG_SENTENCE, tmp_path / 'a.wav')
    assert ''.join(spoken) == LONG_SENTENCE and len(spoken) > 1
    gaps = (len(spoken) - 1) * engines.SIRI_CHUNK_GAP_MS
    assert rendered.duration_ms == len(spoken) * 1000 + gaps
    assert engines._wav_info(tmp_path / 'a.wav').duration_ms == rendered.duration_ms


def test_siri_refuses_a_piece_that_reached_the_cutoff(monkeypatch, tmp_path):
    _fake_siri(monkeypatch, lambda text: 26)
    with pytest.raises(RenderFailed, match='cut'):
        SiriEngine(Path('/x/pipeline'), Path('/x/python')).render('你好。', tmp_path / 'a.wav')
