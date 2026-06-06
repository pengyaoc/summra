# Gunicorn configuration for production (memory-optimized)
import multiprocessing
import os

# Server socket
bind = "127.0.0.1:5000"
backlog = 64

# Worker processes
# For e2-micro: use 1-2 workers max to conserve memory
workers = int(os.getenv('GUNICORN_WORKERS', '1'))
worker_class = 'gevent'  # Async workers for better concurrency with low memory
worker_connections = 100
max_requests = 1000  # Restart workers after 1000 requests to prevent memory leaks
max_requests_jitter = 50
timeout = 120  # 2 minutes for slow requests

# Memory optimization
preload_app = True  # Load app before forking workers (saves memory)

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
