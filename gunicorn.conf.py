import os
import multiprocessing

# Configurações otimizadas para Render - evitar loops de reconexão
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
workers = 1  # Manter 1 worker para o plano gratuito
# Habilita WebSocket nativo com gevent-websocket
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
worker_connections = 1000
timeout = 120  # Timeout conservador
keepalive = 2   # Keepalive mais baixo
max_requests = 1500  # Reduzido para evitar problemas
max_requests_jitter = 150
preload_app = True

# Configurações de memória otimizadas
worker_tmp_dir = "/dev/shm"
tmp_upload_dir = None

# Logging otimizado para produção
loglevel = "warning"  # Reduzir logs para evitar spam
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)s'
accesslog = "-"
errorlog = "-"

# Configurações para produção - reduzir timeouts
graceful_timeout = 20  # Reduzido
backlog = 2048

# Configurações de processo
daemon = False
pidfile = None
user = None
group = None
umask = 0

# SSL (não usado no Render)
keyfile = None
certfile = None
