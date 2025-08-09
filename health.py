"""
Health check endpoint para monitoramento do Render
"""
from flask import jsonify
import psutil
import os
import time

def get_health_status():
    """Retorna o status de saúde da aplicação"""
    try:
        # Verificar uso de memória
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Verificar uso de CPU com amostragem rápida (não bloqueante)
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Uptime do processo
        process = psutil.Process(os.getpid())
        start_time = process.create_time()
        uptime_seconds = max(0, time.time() - start_time)
        
        status = {
            "status": "healthy",
            "memory_usage": f"{memory_percent:.1f}%",
            "cpu_usage": f"{cpu_percent:.1f}%",
            "uptime_seconds": int(uptime_seconds),
            "started_at": start_time,
            "pid": os.getpid()
        }
        
        # Marcar como unhealthy se uso de memória > 90%
        if memory_percent > 90:
            status["status"] = "unhealthy"
            status["reason"] = "High memory usage"
        
        return status
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def register_health_routes(app):
    """Registra as rotas de health check"""
    
    @app.route('/health')
    def health_check():
        """Endpoint básico de health check"""
        return jsonify({"status": "ok", "service": "jogo-5-palavras"})
    
    @app.route('/health/detailed')
    def detailed_health():
        """Endpoint detalhado de health check"""
        return jsonify(get_health_status())
    
    @app.route('/ping')
    def ping():
        """Endpoint simples para keep-alive"""
        return "pong"
