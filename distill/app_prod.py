"""Production entry point: gunicorn -c deploy/gunicorn_config.py distill.app_prod:app"""
import os

if os.environ.get('DISTILL_AUTH_MODE') != 'required':
    raise RuntimeError('Distill is private: set DISTILL_AUTH_MODE=required (and DISTILL_ALLOWED_EMAILS) to run in production')

from distill.app_base import create_app  # noqa: E402

app = create_app()
