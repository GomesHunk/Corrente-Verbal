import os
import multiprocessing

# Configurações otimizadas para Render - evitar loops de reconexão
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
workers = 1  # Manter 1 worker para o plano gratuito
worker_class = "gevent"  # Voltar para gevent por estabilidade
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
