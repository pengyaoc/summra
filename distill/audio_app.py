"""What the shared recorder needs to know about Distill."""
from distill import config
from distill.models import DistillDatabase
from distill.scripts.deploy_db import deploy_db, load_settings

DEFAULT_DB = config.DATABASE_PATH
MODES = ('summary',)
open_db = DistillDatabase


def books(db) -> list:
    return db.list_books()


def deploy(db_path, config_path) -> None:
    deploy_db(db_path, load_settings(config_path))
