"""Render a chapter's spoken units and join them into one Opus file with unit timings.

Units are rendered part by part and joined with fixed silences, so each unit's
start and end are known exactly; no forced alignment is needed.
"""
import subprocess
import wave
from pathlib import Path
from typing import List, Sequence, Tuple

from shared.audio.engines import Engine
from shared.audio.spoken import SpokenUnit, spoken_checksum

UNIT_GAP_MS = 350
PART_GAP_MS = 250
OPUS_BITRATE = '24k'  # approved by ear 2026-11-08; AAC 32 kbps sounded dull


def compute_timings(units: Sequence[Tuple[str, Sequence[float]]],
                    unit_gap_ms: float = UNIT_GAP_MS, part_gap_ms: float = PART_GAP_MS) -> List[dict]:
    """[(paragraph_id, part durations)] -> [{paragraph_id, start_ms, end_ms}].

    The first unit's first part is the chapter title, followed by a unit gap.
    """
    timings, cursor = [], 0.0
    for index, (paragraph_id, durations) in enumerate(units):
        if index:
            cursor += unit_gap_ms
        start = cursor
        for part, duration in enumerate(durations):
            if part:
                cursor += unit_gap_ms if (index == 0 and part == 1) else part_gap_ms
            cursor += duration
        timings.append({'paragraph_id': paragraph_id, 'start_ms': round(start), 'end_ms': round(cursor)})
    return timings


def render_chapter(units: Sequence[SpokenUnit], engine: Engine, work_dir: Path) -> Tuple[bytes, List[dict], int, str]:
    """Return (Opus bytes, timings, duration_ms, spoken checksum) for what a chapter says."""
    work_dir = Path(work_dir)
    rendered = []  # per unit: list of PCM frame strings
    rate = None
    for u, unit in enumerate(units):
        frames = []
        for p, text in enumerate(unit.parts):
            result = engine.render(text, work_dir / f'u{u}_p{p}.wav')
            with wave.open(str(result.wav), 'rb') as audio:
                if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
                    raise ValueError('Expected mono 16-bit speech')
                if rate is None:
                    rate = audio.getframerate()
                elif audio.getframerate() != rate:
                    raise ValueError('Parts of one chapter came back at different sample rates')
                frames.append(audio.readframes(audio.getnframes()))
        rendered.append(frames)

    unit_gap = b'\x00\x00' * int(rate * UNIT_GAP_MS / 1000)
    part_gap = b'\x00\x00' * int(rate * PART_GAP_MS / 1000)
    pcm = bytearray()
    for u, frames in enumerate(rendered):
        if u:
            pcm += unit_gap
        for p, part in enumerate(frames):
            if p:
                pcm += unit_gap if (u == 0 and p == 1) else part_gap
            pcm += part

    def ms(data: bytes) -> float:
        return len(data) / 2 * 1000 / rate

    timings = compute_timings([(unit.paragraph_id, [ms(f) for f in frames]) for unit, frames in zip(units, rendered)],
                              unit_gap_ms=ms(unit_gap), part_gap_ms=ms(part_gap))
    joined = work_dir / 'chapter.wav'
    with wave.open(str(joined), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(bytes(pcm))
    return _to_opus(joined, work_dir / 'chapter.mp4'), timings, round(ms(bytes(pcm))), spoken_checksum(units)


def _to_opus(source: Path, encoded: Path) -> bytes:
    """Opus 24 kbps in an MP4 container: the only file a new chapter keeps."""
    result = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-c:a', 'libopus',
                             '-b:a', OPUS_BITRATE, '-application', 'audio', '-f', 'mp4', str(encoded)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffmpeg Opus encode failed: {result.stderr.strip()[:300]}')
    return encoded.read_bytes()


def encode_opus(aac: bytes, work_dir: Path) -> bytes:
    """Convert an older chapter's AAC file to Opus without re-rendering it."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    source = work_dir / 'master.m4a'
    source.write_bytes(aac)
    return _to_opus(source, work_dir / 'deploy.mp4')
