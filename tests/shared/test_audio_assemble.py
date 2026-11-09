import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from shared.audio import assemble
from shared.audio.assemble import compute_timings, encode_opus, render_chapter
from shared.audio.engines import Rendered
from shared.audio.spoken import spoken_checksum, spoken_units

CHAPTER = {'id': 5, 'title': 'Title', 'blocks': [
    {'type': 'p', 'text': 'First paragraph.'},
    {'type': 'p', 'text': 'Second.'},
    {'type': 'table', 'header': ['a'], 'rows': []},
    {'type': 'ul', 'items': ['one', 'two']},
]}


def test_compute_timings_gaps():
    assert compute_timings([('5.0', [1000, 2000]), ('5.1', [500]), ('5.3', [300, 300])]) == [
        {'paragraph_id': '5.0', 'start_ms': 0, 'end_ms': 3350},
        {'paragraph_id': '5.1', 'start_ms': 3700, 'end_ms': 4200},
        {'paragraph_id': '5.3', 'start_ms': 4550, 'end_ms': 5400},
    ]


class ToneEngine:
    """Writes 10 ms of audio per character of text."""
    name, lang, repeatable = 'tone', 'en', True

    def __init__(self, rate=8000):
        self.rate = rate

    def voice_id(self):
        return 'tone'

    def render(self, text, out_wav):
        frames = len(text) * self.rate // 100
        with wave.open(str(out_wav), 'wb') as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(self.rate)
            out.writeframes(b'\x01\x00' * frames)
        return Rendered(Path(out_wav), len(text) * 10, self.rate)


@pytest.fixture
def fake_ffmpeg(monkeypatch):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        source = Path(cmd[cmd.index('-i') + 1])
        Path(cmd[-1]).write_bytes(b'OPUS' + source.read_bytes()[:10])
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(assemble.subprocess, 'run', run)
    return calls


def test_render_chapter_uses_fake_engine(tmp_path, fake_ffmpeg):
    audio, timings, duration_ms, checksum = render_chapter(CHAPTER, ToneEngine(), tmp_path)
    assert audio.startswith(b'OPUS' + b'RIFF')  # encoded straight from the raw WAV, no AAC step
    assert len(fake_ffmpeg) == 1
    cmd = fake_ffmpeg[0]
    assert cmd[cmd.index('-c:a') + 1] == 'libopus' and cmd[cmd.index('-b:a') + 1] == '24k'
    assert cmd[cmd.index('-application') + 1] == 'audio'
    assert timings == compute_timings([('5.0', [50, 160]), ('5.1', [70]), ('5.3', [30, 30])])
    assert duration_ms == timings[-1]['end_ms']
    assert checksum == spoken_checksum(spoken_units(CHAPTER))


def test_render_chapter_rejects_mixed_rates(tmp_path, fake_ffmpeg):
    class Mixed(ToneEngine):
        calls = 0

        def render(self, text, out_wav):
            Mixed.calls += 1
            self.rate = 8000 if Mixed.calls == 1 else 16000
            return super().render(text, out_wav)

    with pytest.raises(ValueError):
        render_chapter(CHAPTER, Mixed(), tmp_path)


def test_encode_opus_uses_libopus_24k_mp4(tmp_path, monkeypatch):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b'OPUS')
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(assemble.subprocess, 'run', run)
    assert encode_opus(b'M4A-master', tmp_path) == b'OPUS'
    cmd = calls[0]
    assert cmd[0] == 'ffmpeg'
    assert cmd[cmd.index('-c:a') + 1] == 'libopus' and cmd[cmd.index('-b:a') + 1] == '24k'
    assert cmd[cmd.index('-application') + 1] == 'audio'
    assert cmd[cmd.index('-f') + 1] == 'mp4'


def test_encode_opus_failure_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(assemble.subprocess, 'run',
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, '', 'bad input'))
    with pytest.raises(RuntimeError, match='bad input'):
        encode_opus(b'not audio', tmp_path)


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg not installed')
def test_encode_opus_real_ffmpeg_makes_smaller_mp4(tmp_path):
    source = tmp_path / 'tone.wav'
    with wave.open(str(source), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(22050)
        out.writeframes(bytes(range(256)) * (22050 * 4 * 2 // 256))
    m4a = tmp_path / 'tone.m4a'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-c:a', 'aac', '-b:a', '32k', str(m4a)], check=True)
    opus = encode_opus(m4a.read_bytes(), tmp_path / 'work')
    assert opus[4:8] == b'ftyp' and b'Opus' in opus
