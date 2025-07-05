import os
import multiprocessing

# Configurações otimizadas para Render com melhor estabilidade
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
workers = 1  # Manter 1 worker para o plano gratuito
worker_class = "eventlet"  # Mudança para eventlet para melhor suporte a SocketIO
worker_connections = 1000
timeout = 180  # Aumentado para conexões lentas
keepalive = 5  # Aumentado para melhor estabilidade
max_requests = 2000  # Aumentado
max_requests_jitter = 200
preload_app = True

# Configurações de memória otimizadas
worker_tmp_dir = "/dev/shm"
tmp_upload_dir = None

# Logging detalhado para debug
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
accesslog = "-"
errorlog = "-"

# Configurações para produção
graceful_timeout = 30
worker_tmp_dir = "/dev/shm"
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
