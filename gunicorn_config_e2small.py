# Gunicorn configuration for e2-small (2GB RAM, 2 vCPU)
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 128

# Worker processes
# e2-small has 2 vCPU, so 2-3 workers is optimal
workers = int(os.getenv('GUNICORN_WORKERS', '2'))
worker_class = 'gevent'  # Async workers for better concurrency
worker_connections = 200
max_requests = 2000  # Restart workers after 2000 requests to prevent memory leaks
max_requests_jitter = 100
timeout = 300  # 5 minutes for TTS generation

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

# Graceful timeout for TTS generation
graceful_timeout = 60

# SSL (if needed)
# keyfile = None
# certfile = None
