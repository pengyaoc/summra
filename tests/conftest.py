"""
Centralized pytest fixtures for all tests.

All test artifacts (databases, images, audio, batch jobs) are created in tests/fixtures/
and automatically cleaned up after test completion.
"""

import pytest
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

# `backend` and `scripts` are installed as real packages (see pyproject.toml,
# `pip install -e .`), so no sys.path manipulation is needed here — tests
# import them as `from backend import config`, `from scripts.content.
# generate_summaries import SummaryGenerator`, etc.

# Test fixtures root directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_DIR.mkdir(exist_ok=True)

# Subdirectories for different artifact types
DATABASES_DIR = FIXTURES_DIR / "databases"
ILLUSTRATIONS_DIR = FIXTURES_DIR / "illustrations"
AUDIO_DIR = FIXTURES_DIR / "audio"
BATCH_JOBS_DIR = FIXTURES_DIR / "batch_jobs"

# Ensure all subdirectories exist
DATABASES_DIR.mkdir(exist_ok=True)
ILLUSTRATIONS_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
BATCH_JOBS_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_artifacts():
    """
    Automatically clean up test artifacts after each test.

    This fixture runs for every test function and ensures that
    test-generated files are removed after the test completes.
    """
    # Setup: nothing needed (artifacts created during test)
    yield

    # Teardown: clean up all test artifacts
    for subdir in [DATABASES_DIR, ILLUSTRATIONS_DIR, AUDIO_DIR, BATCH_JOBS_DIR]:
        if subdir.exists():
            # Remove all files in the directory
            for item in subdir.glob("*"):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)


@pytest.fixture
def test_db_path():
    """
    Provides a unique database path in the test fixtures directory.

    Returns:
        Path: Path to a temporary test database file
    """
    db_path = DATABASES_DIR / f"test_{uuid.uuid4().hex}.db"
    yield db_path

    # Cleanup handled by cleanup_test_artifacts


@pytest.fixture
def test_illustrations_dir():
    """
    Provides a temporary illustrations directory for tests.

    Returns:
        Path: Path to temporary illustrations directory
    """
    illustrations_dir = ILLUSTRATIONS_DIR / f"test_{uuid.uuid4().hex}"
    illustrations_dir.mkdir(parents=True, exist_ok=True)
    yield illustrations_dir

    # Cleanup handled by cleanup_test_artifacts


@pytest.fixture
def test_audio_dir():
    """
    Provides a temporary audio directory for tests.

    Returns:
        Path: Path to temporary audio directory
    """
    audio_dir = AUDIO_DIR / f"test_{uuid.uuid4().hex}"
    audio_dir.mkdir(parents=True, exist_ok=True)
    yield audio_dir

    # Cleanup handled by cleanup_test_artifacts


@pytest.fixture
def test_batch_jobs_dir():
    """
    Provides a temporary batch jobs directory for tests.

    Returns:
        Path: Path to temporary batch jobs directory
    """
    batch_jobs_dir = BATCH_JOBS_DIR / f"test_{uuid.uuid4().hex}"
    batch_jobs_dir.mkdir(parents=True, exist_ok=True)
    yield batch_jobs_dir

    # Cleanup handled by cleanup_test_artifacts


@pytest.fixture
def mock_config_paths(test_illustrations_dir, test_audio_dir, test_batch_jobs_dir):
    """
    Mock configuration paths to use test fixtures directories.

    This prevents tests from writing to production directories.
    """
    with patch('backend.config.ILLUSTRATIONS_DIR', test_illustrations_dir), \
         patch('backend.config.TTS_OUTPUT_DIR', test_audio_dir), \
         patch('scripts.images.generate_illustrations.BATCH_JOBS_DIR', test_batch_jobs_dir):
        yield {
            'illustrations': test_illustrations_dir,
            'audio': test_audio_dir,
            'batch_jobs': test_batch_jobs_dir
        }
