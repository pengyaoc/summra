"""Give a Plainly book a recorded first chapter, in its current data. Test fixture for plainly_player.mjs.

Usage: venv/bin/python tests/e2e/plainly_seed_recording.py <book_id> <mode> [...]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from plainly.models import Database
from shared.audio.spoken import spoken_checksum

UNIT_MS = 2500


def main(book_id, modes):
    db = Database()
    chapter = db.get_chapters(book_id)[0]
    for mode in modes:
        units = db.audio_spoken_units(chapter, mode)[:12]
        ms = UNIT_MS * len(units)
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / 'tone.m4a'
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', str(ms / 1000), '-c:a', 'aac', str(path)], check=True)
            data = path.read_bytes()
        timings = [{'paragraph_id': u.paragraph_id, 'start_ms': i * UNIT_MS, 'end_ms': (i + 1) * UNIT_MS} for i, u in enumerate(units)]
        whole = db.audio_spoken_units(chapter, mode)
        db.save_chapter_audio(chapter['id'], data, timings, ms, spoken_checksum(whole), 'test', 'test', None, mode=mode)
    print(chapter['id'])


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2:])
