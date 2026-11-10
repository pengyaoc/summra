"""What the shared recorder needs to know about Plainly."""
from plainly import config
from plainly.models import Database

DEFAULT_DB = config.DATABASE_PATH
MODES = ('original', 'plain')
deploy = None  # shipping Plainly's recordings to the VM is not built yet


def open_db(path):
    return Database(db_path=str(path))


def books(db) -> list:
    return db.get_all_books()
