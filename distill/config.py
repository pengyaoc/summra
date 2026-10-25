from pathlib import Path

# Repo root
BASE_DIR = Path(__file__).parent.parent

DATABASE_PATH = BASE_DIR / 'data' / 'distill.db'
USER_DATABASE_PATH = BASE_DIR / 'data' / 'distill_user.db'
