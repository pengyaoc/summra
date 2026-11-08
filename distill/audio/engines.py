"""macOS voices for chapter audio: `say` (English) and Siri Voice 4 (Chinese).

Neither engine may fall back to another voice silently: Siri must list the voice,
and every run first matches a reference clip recorded when the owner approved it.
"""
import hashlib
import json
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import NamedTuple, Protocol

REFERENCE_TEXT = {
    'en': 'Reading is to the mind what exercise is to the body.',
    'zh': '读书之于心灵，犹如运动之于身体。',
}
SIRI_ATTEMPTS = 3
DURATION_TOLERANCE = 0.02


class Rendered(NamedTuple):
    wav: Path
    duration_ms: int
    sample_rate: int


class VoiceUnavailable(RuntimeError):
    pass


class VoiceMismatch(RuntimeError):
    pass


class RenderFailed(RuntimeError):
    pass


class Engine(Protocol):
    name: str
    lang: str
    repeatable: bool  # byte-identical output for identical input

    def voice_id(self) -> str: ...

    def render(self, text: str, out_wav: Path) -> Rendered: ...


def _wav_info(path: Path) -> Rendered:
    with wave.open(str(path), 'rb') as audio:
        rate = audio.getframerate()
        return Rendered(path, round(audio.getnframes() * 1000 / rate), rate)


def _run(cmd, what):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderFailed(f'{what} failed: {(result.stderr or result.stdout).strip()[:300]}')
    return result


class SayEngine:
    """The Mac's system voice (Siri Voice 2), which `say -v` cannot name."""
    name, lang, repeatable = 'say', 'en', True

    def voice_id(self) -> str:
        return 'say:system'

    def render(self, text: str, out_wav: Path) -> Rendered:
        with tempfile.TemporaryDirectory(prefix='distill-say-') as tmp:
            source, aiff = Path(tmp) / 'text.txt', Path(tmp) / 'speech.aiff'
            source.write_text(text, encoding='utf-8')
            _run(['say', '-o', str(aiff), '-f', str(source)], 'say')
            _run(['afconvert', '-f', 'WAVE', '-d', 'LEI16', str(aiff), str(out_wav)], 'afconvert to WAV')
        return _wav_info(out_wav)


class SiriEngine:
    """Siri Voice 4 through InkChinese's private SiriTTSService exporter, run in
    InkChinese's venv (it needs PyObjC, which this repo's venv does not have)."""
    name, lang = 'siri', 'zh'
    repeatable = False  # 2026-11-07: two renders differed (3500 vs 3520 ms); match by duration

    def __init__(self, tts_path: Path, python: Path, voice: str = 'zh-CN-D', rate: float = 1.0):
        self.tts_path, self.python, self.voice, self.rate = Path(tts_path), Path(python), voice, rate
        self._voice_checked = False

    def voice_id(self) -> str:
        return f'siri:{self.voice}@{self.rate}'

    def _script(self, body: str) -> list:
        prelude = f'import sys, json; sys.path.insert(0, {str(self.tts_path)!r}); import siri_tts; '
        return [str(self.python), '-c', prelude + body]

    def _check_voice(self):
        if self._voice_checked:
            return
        listed = json.loads(_run(self._script('print(json.dumps(siri_tts.voices()))'), 'Siri voice list').stdout)
        if self.voice not in {v.get('name') for v in listed}:
            raise VoiceUnavailable(f'Siri voice {self.voice} is not downloaded on this Mac')
        self._voice_checked = True

    def render(self, text: str, out_wav: Path) -> Rendered:
        self._check_voice()
        body = (f'siri_tts.VOICE_NAME = {self.voice!r}; '
                f'siri_tts.synthesize(sys.stdin.read(), "zh-CN", {str(out_wav)!r}, rate={self.rate!r})')
        error = None
        for _ in range(SIRI_ATTEMPTS):
            result = subprocess.run(self._script(body), input=text, capture_output=True, text=True)
            if result.returncode == 0:
                return _wav_info(out_wav)
            error = (result.stderr or result.stdout).strip()[-300:]
        raise RenderFailed(f'Siri failed {SIRI_ATTEMPTS} times: {error}')


def engine_for(lang: str, settings: dict) -> Engine:
    if lang == 'en':
        return SayEngine()
    if lang == 'zh':
        return SiriEngine(Path(settings['DISTILL_SIRI_TTS_PATH']), Path(settings['DISTILL_SIRI_PYTHON']))
    raise ValueError(f'No audio voice for language {lang!r}')


def _fingerprint(rendered: Rendered) -> dict:
    with wave.open(str(rendered.wav), 'rb') as audio:
        frames = audio.readframes(audio.getnframes())
    return {'sha256': hashlib.sha256(frames).hexdigest(), 'duration_ms': rendered.duration_ms}


def check_reference(engine: Engine, ref_dir: Path, approve: bool = False) -> None:
    """Render the reference sentence and compare it with the approved one."""
    ref_dir = Path(ref_dir)
    ref_file = ref_dir / f'{engine.name}.json'
    with tempfile.TemporaryDirectory(prefix='distill-ref-') as tmp:
        current = _fingerprint(engine.render(REFERENCE_TEXT[engine.lang], Path(tmp) / 'ref.wav'))
    if approve:
        ref_dir.mkdir(parents=True, exist_ok=True)
        ref_file.write_text(json.dumps({**current, 'voice': engine.voice_id()}, indent=2) + '\n')
        return
    if not ref_file.is_file():
        raise VoiceMismatch(f'No approved {engine.name} voice yet: listen to a chapter, then rerun with --approve-voice')
    approved = json.loads(ref_file.read_text())
    if engine.repeatable:
        same = current['sha256'] == approved['sha256']
    else:
        same = abs(current['duration_ms'] - approved['duration_ms']) <= approved['duration_ms'] * DURATION_TOLERANCE
    if not same:
        raise VoiceMismatch(f'The {engine.name} voice no longer matches the approved reference; '
                            'check System Settings > Spoken Content, then re-approve if intended')
