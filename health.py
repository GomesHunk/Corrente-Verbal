"""
Health check endpoint para monitoramento do Render
"""
from flask import jsonify
import psutil
import os

def get_health_status():
    """Retorna o status de saúde da aplicação"""
    try:
        # Verificar uso de memória
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Verificar uso de CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Verificar se o processo está rodando há muito tempo
        process = psutil.Process(os.getpid())
        uptime = process.create_time()
        
        status = {
            "status": "healthy",
            "memory_usage": f"{memory_percent:.1f}%",
            "cpu_usage": f"{cpu_percent:.1f}%",
            "uptime": uptime,
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
