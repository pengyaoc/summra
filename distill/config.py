import os
from pathlib import Path

# Repo root
BASE_DIR = Path(__file__).parent.parent

DATABASE_PATH = Path(os.environ.get('DISTILL_DB') or BASE_DIR / 'data' / 'distill.db')
USER_DATABASE_PATH = Path(os.environ.get('DISTILL_USER_DB') or BASE_DIR / 'data' / 'distill_user.db')

PORT = int(os.environ.get('PORT', 5003))
