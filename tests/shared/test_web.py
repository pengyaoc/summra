import gzip
from flask import Flask
from shared.web import install_web_basics

def _app():
    app = Flask(__name__)
    install_web_basics(app, "X_STATIC_OVERRIDE")
    app.add_url_rule('/', 'i', lambda: 'x' * 2000)
    app.add_url_rule('/where', 'w', lambda: __import__('flask').request.script_root)
    return app

def test_gzips_large_html():
    r = _app().test_client().get('/', headers={'Accept-Encoding': 'gzip'})
    assert r.headers['Content-Encoding'] == 'gzip' and gzip.decompress(r.data) == b'x' * 2000

def test_honours_forwarded_prefix():
    r = _app().test_client().get('/distill/where', headers={'X-Forwarded-Prefix': '/distill'})
    assert r.data == b'/distill'
