import os
import multiprocessing

# Configurações otimizadas para Render
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
workers = 1
worker_class = "gevent"
worker_connections = 1000
timeout = 120
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# Configurações de memória
worker_tmp_dir = "/dev/shm"
tmp_upload_dir = None

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Configurações de processo
daemon = False
pidfile = None
user = None
group = None
umask = 0

# Configurações SSL (não necessário para Render)
keyfile = None
certfile = None

# Configurações de rede
backlog = 2048
