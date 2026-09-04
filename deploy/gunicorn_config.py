# Gunicorn configuration for production (memory-optimized)
import multiprocessing
import os

# Server socket
# GUNICORN_BIND lets one committed config serve both a standalone deploy
# (127.0.0.1:5000, the default) and a cohosted one (e.g. 127.0.0.1:5001 for
# Summra on wordpress-2-vm) without a --bind override baked into the
# systemd unit's ExecStart.
bind = os.getenv('GUNICORN_BIND', '127.0.0.1:5000')
backlog = 64

# Worker processes
# For e2-micro: use 1-2 workers max to conserve memory
workers = int(os.getenv('GUNICORN_WORKERS', '1'))
# gthread (stdlib threading, no C extension) replaces gevent: the app is
# sync WSGI with zero async I/O, so gevent's cooperative sockets bought
# nothing, while its pinned version (gevent==24.2.1 in requirements-prod.txt)
# has no wheel for newer Python and fails to build from source.
worker_class = 'gthread'
threads = int(os.getenv('GUNICORN_THREADS', '4'))
max_requests = 1000  # Restart workers after 1000 requests to prevent memory leaks
max_requests_jitter = 50
timeout = 120  # 2 minutes for slow requests

# Memory optimization
preload_app = True  # Load app before forking workers (saves memory).
                     # Safe with gthread (unlike gevent): no monkey-patching
                     # to race against import-time socket/ssl usage.

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'summra'

# Server mechanics
daemon = False
pidfile = '/tmp/gunicorn.pid'
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = None
# certfile = None
