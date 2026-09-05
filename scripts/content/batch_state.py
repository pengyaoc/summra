"""Batch job state persistence for generate_summaries.py's Gemini Batch API
mode, extracted from generate_summaries.py. Pure disk I/O over JSON state
files under BATCH_JOBS_DIR — no dependency on SummaryGenerator.

Note: scripts/images/generate_illustrations.py has its own independent copy
of this same pattern (save/load/update/list pending batch jobs) — not
consolidated here, since illustration batch jobs track different fields
than text-summary batch jobs and merging them is a separate task.
"""
import json
import time
from pathlib import Path
from typing import Dict, List

from scripts.content.constants import BATCH_JOBS_DIR


def save_batch_job_state(book_id: int, job_name: str, book_title: str,
                        request_metadata: List[Dict]) -> Path:
    """Save batch job state to disk for later resumption

    Args:
        book_id: Book ID being processed
        job_name: Gemini batch job name/ID
        book_title: Title of the book
        request_metadata: List of metadata for each request (type, chapter_num, etc.)

    Returns:
        Path to the saved state file
    """
    BATCH_JOBS_DIR.mkdir(parents=True, exist_ok=True)

    state = {
        'book_id': book_id,
        'book_title': book_title,
        'job_name': job_name,
        'request_metadata': request_metadata,
        'status': 'pending',
        'created_at': time.time(),
        'updated_at': time.time()
    }

    state_file = BATCH_JOBS_DIR / f"book_{book_id}_{int(time.time())}.json"
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"  💾 Saved batch job state: {state_file}")
    return state_file


def load_batch_job_state(state_file: Path) -> Dict:
    """Load batch job state from disk

    Args:
        state_file: Path to the state file

    Returns:
        Dictionary with job state
    """
    with open(state_file, 'r') as f:
        return json.load(f)


def update_batch_job_state(state_file: Path, status: str, **kwargs):
    """Update batch job state file

    Args:
        state_file: Path to the state file
        status: New status value
        **kwargs: Additional fields to update
    """
    state = load_batch_job_state(state_file)
    state['status'] = status
    state['updated_at'] = time.time()
    state.update(kwargs)

    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def list_pending_batch_jobs() -> List[Dict]:
    """List all pending batch jobs

    Returns:
        List of job state dictionaries
    """
    if not BATCH_JOBS_DIR.exists():
        return []

    pending_jobs = []
    for state_file in BATCH_JOBS_DIR.glob("book_*.json"):
        try:
            state = load_batch_job_state(state_file)
            if state.get('status') in ['pending', 'running']:
                state['state_file'] = str(state_file)
                pending_jobs.append(state)
        except Exception as e:
            print(f"  ⚠️  Error loading {state_file}: {e}")

    return sorted(pending_jobs, key=lambda x: x.get('created_at', 0))
