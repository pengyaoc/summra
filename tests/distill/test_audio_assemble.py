import subprocess
import wave
from pathlib import Path

import pytest

from distill.audio import assemble
from distill.audio.assemble import compute_timings, render_chapter
from distill.audio.engines import Rendered
from distill.audio.spoken import spoken_checksum, spoken_units

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
def fake_afconvert(monkeypatch):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b'M4A' + Path(cmd[-2]).read_bytes()[:10])
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(assemble.subprocess, 'run', run)
    return calls


def test_render_chapter_uses_fake_engine(tmp_path, fake_afconvert):
    m4a, timings, duration_ms, checksum = render_chapter(CHAPTER, ToneEngine(), tmp_path)
    assert m4a.startswith(b'M4A')
    assert '-b' in fake_afconvert[0] and '32000' in fake_afconvert[0]
    assert timings == compute_timings([('5.0', [50, 160]), ('5.1', [70]), ('5.3', [30, 30])])
    assert duration_ms == timings[-1]['end_ms']
    assert checksum == spoken_checksum(spoken_units(CHAPTER))


def test_render_chapter_rejects_mixed_rates(tmp_path, fake_afconvert):
    class Mixed(ToneEngine):
        calls = 0

        def render(self, text, out_wav):
            Mixed.calls += 1
            self.rate = 8000 if Mixed.calls == 1 else 16000
            return super().render(text, out_wav)

    with pytest.raises(ValueError):
        render_chapter(CHAPTER, Mixed(), tmp_path)
