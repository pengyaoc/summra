import os
from pathlib import Path

# Repo root
BASE_DIR = Path(__file__).parent.parent

DATABASE_PATH = Path(os.environ.get('DISTILL_DB') or BASE_DIR / 'data' / 'distill.db')
USER_DATABASE_PATH = Path(os.environ.get('DISTILL_USER_DB') or BASE_DIR / 'data' / 'distill_user.db')

# Loopback by default: the dev server runs with auth off.
HOST = os.environ.get('DISTILL_HOST', '127.0.0.1')
PORT = int(os.environ.get('PORT', 5003))
