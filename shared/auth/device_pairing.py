"""Browser-bound Kindle pairing. Google identity still comes only from Apache.

The code shown on a Kindle is an approval identifier, never a login credential.
Only the originating browser's 256-bit secret can redeem an approved request.
"""
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import time
from contextlib import contextmanager
from io import BytesIO

from flask import Blueprint, abort, g, jsonify, redirect, render_template, request, send_file, url_for

from shared.auth.pchauth.core import Identity, is_allowed
from shared.auth.pchauth.trusted_header import identity_from_headers
from shared.kindle import is_kindle_user_agent

PAIR_TTL = 600
SESSION_TTL = 30 * 86400


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class PairingStore:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS pairing_requests (
                    secret_hash TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL,
                    created REAL NOT NULL, expires REAL NOT NULL, email TEXT,
                    consumed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS device_sessions (
                    token_hash TEXT PRIMARY KEY, id TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS pairing_csrf (
                    token_hash TEXT PRIMARY KEY, email TEXT NOT NULL,
                    scope TEXT NOT NULL, expires REAL NOT NULL);
            ''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def pending(self, secret):
        with self.connection() as db:
            return db.execute('SELECT * FROM pairing_requests WHERE secret_hash=? AND expires>? AND consumed=0',
                              (digest(secret), self.clock())).fetchone()

    def create(self):
        now = self.clock()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM pairing_requests WHERE expires<=?', (now,))
            db.execute('DELETE FROM device_sessions WHERE expires<=?', (now,))
            db.execute('DELETE FROM pairing_csrf WHERE expires<=?', (now,))
            # This is a private, single-owner service. Bound unauthenticated writes
            # globally, including deployments behind a loopback reverse proxy.
            if db.execute('SELECT count(*) FROM pairing_requests WHERE created>?', (now - PAIR_TTL,)).fetchone()[0] >= 40:
                return None
            secret = secrets.token_urlsafe(32)
            alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
            code = ''.join(secrets.choice(alphabet) for _ in range(8))
            db.execute('INSERT INTO pairing_requests(secret_hash,code,created,expires) VALUES(?,?,?,?)',
                       (digest(secret), code, now, now + PAIR_TTL))
            return secret

    def by_code(self, code):
        with self.connection() as db:
            return db.execute('SELECT * FROM pairing_requests WHERE code=? AND expires>? AND consumed=0',
                              (code, self.clock())).fetchone()

    def csrf(self, email, scope):
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute('INSERT INTO pairing_csrf VALUES(?,?,?,?)',
                       (digest(token), email, scope, self.clock() + PAIR_TTL))
        return token

    def mutate(self, token, email, scope, code=None, session_id=None):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            result = db.execute('DELETE FROM pairing_csrf WHERE token_hash=? AND email=? AND scope=? AND expires>?',
                                (digest(token), email, scope, self.clock()))
            if result.rowcount != 1:
                return False
            if code:
                return db.execute('UPDATE pairing_requests SET email=? WHERE code=? AND expires>? AND consumed=0 AND email IS NULL',
                                  (email, code, self.clock())).rowcount == 1
            return db.execute('DELETE FROM device_sessions WHERE id=? AND email=?', (session_id, email)).rowcount == 1

    def redeem(self, secret, config):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM pairing_requests WHERE secret_hash=? AND expires>? AND consumed=0',
                             (digest(secret), self.clock())).fetchone()
            if not row or not row['email'] or not is_allowed(row['email'], config):
                return None
            db.execute('UPDATE pairing_requests SET consumed=1 WHERE secret_hash=?', (digest(secret),))
            token = secrets.token_urlsafe(32)
            db.execute('INSERT INTO device_sessions VALUES(?,?,?,?,?)',
                       (digest(token), secrets.token_hex(16), row['email'], self.clock(), self.clock() + SESSION_TTL))
            return token

    def identity(self, token):
        with self.connection() as db:
            row = db.execute('SELECT email FROM device_sessions WHERE token_hash=? AND expires>?',
                             (digest(token), self.clock())).fetchone()
            return Identity(email=row['email']) if row else None

    def devices(self, email):
        with self.connection() as db:
            return db.execute('SELECT id,created,expires FROM device_sessions WHERE email=? AND expires>? ORDER BY created DESC',
                              (email, self.clock())).fetchall()


def install_pairing(app, config, user_db, *, app_id, app_name, env_prefix,
                    library_endpoint, login_endpoint, public_endpoints=frozenset(),
                    launch_endpoint=None):
    """Install one auth boundary for required/private or optional/public readers.

    Stores and cookies are app-specific; Distill's existing names/schema stay
    unchanged so deployed Kindle sessions survive this shared-code extraction.
    """
    pair_cookie = app_id + '_pair'
    device_cookie = app_id + '_device'
    csrf_cookie = app_id + '_pair_csrf'
    origin = os.environ.get(env_prefix + '_PAIRING_ORIGIN', 'https://pengyaochen.com').rstrip('/')
    store = PairingStore(os.environ.get(env_prefix + '_PAIRING_DB') or
                         Path(user_db.db_path).with_name(app_id + '_pairing.db'))
    app.extensions[app_id + '_pairing'] = store
    bp = Blueprint('pairing', __name__)

    def kindle():
        return is_kindle_user_agent(request.user_agent.string)

    def cookie_path():
        return (request.script_root or '') + '/'

    def set_cookie(response, name, value, age):
        response.set_cookie(name, value, max_age=age, secure=True, httponly=True,
                            samesite='Lax', path=cookie_path())

    @app.before_request
    def resolve_identity():
        g.user_id = None
        g.oidc_identity = identity_from_headers(request.headers, config)
        if g.oidc_identity and not is_allowed(g.oidc_identity.email, config):
            return jsonify(error='not on the allowlist', email=g.oidc_identity.email), 403
        identity = g.oidc_identity
        if identity is None and kindle():
            identity = store.identity(request.cookies.get(device_cookie, ''))
            if identity and not is_allowed(identity.email, config):
                identity = None
        if config.mode == 'off':
            identity = Identity(email='')
        if identity is not None:
            g.user_id = user_db.upsert_user_by_email(identity.email)
        # Kindle-only automatic entry, including the otherwise-public PWA launch.
        if launch_endpoint and request.endpoint == launch_endpoint and kindle():
            return redirect(url_for(library_endpoint if g.user_id is not None else 'pairing.start'))
        if request.endpoint in public_endpoints or request.blueprint == 'pairing':
            return None
        if g.user_id is None and request.endpoint == login_endpoint and kindle():
            return redirect(url_for('pairing.start'))
        if g.user_id is None and config.mode == 'required':
            if kindle() and request.method == 'GET' and request.accept_mimetypes.accept_html:
                return redirect(url_for('pairing.start'))
            return jsonify(error='not authenticated'), 401

    def page(**context):
        return render_template('shared/kindle/pairing.html', pairing_app_name=app_name, **context)

    def phone_identity():
        # A device session can never approve another device or manage sessions.
        if not g.oidc_identity:
            abort(401)
        return g.oidc_identity.email

    def check_csrf():
        token = request.form.get('csrf', '')
        cookie = request.cookies.get(csrf_cookie, '')
        if not token or not secrets.compare_digest(token, cookie):
            abort(403)
        request_origin = request.headers.get('Origin')
        if request_origin and request_origin != origin:
            abort(403)
        return token

    @bp.route('/pair')
    def start():
        if not kindle():
            return redirect(url_for(login_endpoint))
        if g.user_id is not None:
            return redirect(url_for(library_endpoint))
        secret = request.cookies.get(pair_cookie, '')
        row = store.pending(secret)
        if row and row['email']:
            token = store.redeem(secret, config)
            if token:
                response = redirect(url_for(library_endpoint))
                set_cookie(response, device_cookie, token, SESSION_TTL)
                response.delete_cookie(pair_cookie, path=cookie_path())
                return response
        if not row:
            secret = store.create()
            if not secret:
                return page(error='Too many pairing attempts. Try again in ten minutes.'), 429
            row = store.pending(secret)
        code = row['code']
        phone_url = origin + url_for('pairing.approve', code=code)
        response = app.make_response(page(mode='kindle', code=code[:4] + '-' + code[4:], phone_url=phone_url))
        set_cookie(response, pair_cookie, secret, PAIR_TTL)
        return response

    @bp.route('/pair/qr.png')
    def qr():
        if not kindle():
            abort(404)
        row = store.pending(request.cookies.get(pair_cookie, ''))
        if not row:
            abort(404)
        import qrcode
        target = origin + url_for('pairing.approve', code=row['code'])
        data = BytesIO()
        qrcode.make(target, box_size=6, border=4).save(data, format='PNG')
        data.seek(0)
        return send_file(data, mimetype='image/png')

    @bp.route('/pair/approve', methods=['GET', 'POST'])
    def approve():
        email = phone_identity()
        code = (request.values.get('code') or '').upper().replace('-', '').replace(' ', '')
        if not code:
            return page(mode='enter')
        row = store.by_code(code)
        if not row:
            return page(error='This code has expired or has already been used. Refresh the pairing page on your Kindle.'), 410
        scope = 'approve:' + code
        if request.method == 'POST':
            if not store.mutate(check_csrf(), email, scope, code=code):
                abort(403)
            return page(mode='approved')
        csrf = store.csrf(email, scope)
        response = app.make_response(page(mode='approve', code=code, display_code=code[:4] + '-' + code[4:], csrf=csrf, email=email))
        set_cookie(response, csrf_cookie, csrf, PAIR_TTL)
        return response

    @bp.route('/pair/devices', methods=['GET', 'POST'])
    def devices():
        email = phone_identity()
        if request.method == 'POST':
            session_id = request.form.get('device', '')
            if not store.mutate(check_csrf(), email, 'revoke', session_id=session_id):
                abort(403)
            return redirect(url_for('pairing.devices'))
        csrf = store.csrf(email, 'revoke')
        response = app.make_response(page(mode='devices', devices=store.devices(email), csrf=csrf))
        set_cookie(response, csrf_cookie, csrf, PAIR_TTL)
        return response

    @bp.after_request
    def secure_response(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    app.register_blueprint(bp)
