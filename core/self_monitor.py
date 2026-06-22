"""
core/self_monitor.py — Dashboard de salud de Jarvis (Self-Monitoring).

Agrega métricas en vivo para un HUD en la GUI:
  - uso de IA hoy: nº de llamadas, tokens y coste estimado (USD).
  - servicios: cuántos activos / detenidos / desactivados.
  - sistema: RAM del sistema (%), CPU (%), RAM del proceso (MB), uptime.
  - nivel de amenaza DEFCON actual.

Reutiliza model_logging (uso), services (estado) y threat_level (DEFCON). Un
daemon ligero emite el dashboard por Socket.IO periódicamente.

Nota: la latencia media de la IA aún no se registra (requeriría cronometrar las
llamadas); se deja como ampliación futura.
"""
import os
import time
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _get_usage() -> dict:
    """Uso de IA de hoy: {calls, tokens, cost}."""
    try:
        from core.model_logging import get_daily_usage
        return get_daily_usage()
    except Exception as e:
        logger.warning(f"[SelfMonitor] No se pudo leer el uso diario: {e}")
        return {"calls": 0, "tokens": 0, "cost": 0.0}


def _get_services_summary() -> dict:
    """Conteo de servicios por estado."""
    summary = {"running": 0, "stopped": 0, "disabled": 0}
    try:
        from core.services import get_services_status
        for state in get_services_status().values():
            if state in summary:
                summary[state] += 1
    except Exception as e:
        logger.warning(f"[SelfMonitor] No se pudo leer el estado de servicios: {e}")
    return summary


def _get_system_metrics() -> dict:
    """Métricas de sistema en vivo (RAM, CPU, uptime del proceso)."""
    metrics = {
        "system_ram_percent": 0.0,
        "cpu_percent": 0.0,
        "process_ram_mb": 0.0,
        "uptime_seconds": 0,
    }
    try:
        import psutil
        metrics["system_ram_percent"] = round(psutil.virtual_memory().percent, 1)
        metrics["cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
        proc = psutil.Process(os.getpid())
        metrics["process_ram_mb"] = round(proc.memory_info().rss / (1024 * 1024), 1)
        metrics["uptime_seconds"] = int(time.time() - proc.create_time())
    except Exception as e:
        logger.warning(f"[SelfMonitor] No se pudieron leer métricas de sistema: {e}")
    return metrics


def _get_threat_level() -> str:
    try:
        from core.threat_level import compute_threat_level
        return compute_threat_level().get("level", "green")
    except Exception:
        return "green"


def get_health_dashboard() -> dict:
    """Devuelve el dashboard de salud agregado."""
    return {
        "usage": _get_usage(),
        "services": _get_services_summary(),
        "system": _get_system_metrics(),
        "threat_level": _get_threat_level(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# --- Daemon periódico ---
MONITOR_THREAD = None
stop_event = threading.Event()


def emit_health_dashboard() -> dict:
    """Calcula el dashboard y lo emite por Socket.IO. Devuelve el reporte."""
    report = get_health_dashboard()
    try:
        from gui.app import socketio
        socketio.emit("health_dashboard_update", report)
    except Exception:
        pass
    return report


def _monitor_loop():
    """Emite el dashboard periódicamente para alimentar el HUD en vivo."""
    if stop_event.wait(timeout=5):
        return
    while not stop_event.is_set():
        try:
            emit_health_dashboard()
        except Exception as e:
            logger.error(f"[SelfMonitor] Error en el bucle del daemon: {e}")
        interval = int(os.getenv("JARVIS_SELF_MONITOR_INTERVAL", "5"))
        if stop_event.wait(timeout=interval):
            break


def start_self_monitor_daemon():
    """Lanza el daemon del dashboard. Idempotente. Activado por defecto (ligero);
    desactivable con JARVIS_SELF_MONITOR_ENABLED=false."""
    global MONITOR_THREAD
    if os.getenv("JARVIS_SELF_MONITOR_ENABLED", "true").lower() not in ("true", "1", "yes"):
        logging.info("[SelfMonitor] Desactivado en .env.")
        return
    if MONITOR_THREAD is not None and MONITOR_THREAD.is_alive():
        return
    stop_event.clear()
    MONITOR_THREAD = threading.Thread(target=_monitor_loop, name="SelfMonitorDaemon", daemon=True)
    MONITOR_THREAD.start()
    logging.info("[SelfMonitor] Daemon del dashboard de salud iniciado.")


def stop_self_monitor_daemon():
    """Detiene el daemon del dashboard."""
    stop_event.set()