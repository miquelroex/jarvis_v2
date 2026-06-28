"""
core/threat_level.py — Nivel de amenaza DEFCON de Jarvis.

Agrega señales que ya producen otros subsistemas en un único "nivel de amenaza"
que la GUI usará para teñir la interfaz y la esfera:

  - green  (nominal)  — todo en orden.
  - amber  (alerta)   — RAM elevada, servicio caído, integridad en warning,
                        dependencias en advisory.
  - red    (crítico)  — RAM crítica / modo seguro, fallo de integridad,
                        vulnerabilidad de dependencias, dispositivo desconocido.
  - violet (sigilo)   — modo ultra-seguro activado manualmente.

Diseño: `_aggregate_threat_level(signals)` es una función pura y testeable; la
recopilación de señales (`_gather_signals`) hace imports perezosos y es
defensiva (cualquier fallo cae al valor seguro por defecto).
"""
import os
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

LEVELS = ("green", "amber", "red", "violet")

# Umbrales de RAM del sistema (%), configurables por entorno.
RAM_AMBER = float(os.getenv("JARVIS_THREAT_RAM_AMBER", "80"))
RAM_RED = float(os.getenv("JARVIS_THREAT_RAM_RED", "90"))

# Modo ultra-seguro (violet): flag en memoria + override por entorno.
_ultra_secure = False


def set_ultra_secure_mode(active: bool) -> None:
    """Activa/desactiva el modo ultra-seguro (nivel violet)."""
    global _ultra_secure
    _ultra_secure = bool(active)


def is_ultra_secure_mode() -> bool:
    """True si el modo ultra-seguro está activo (por flag o por entorno)."""
    if _ultra_secure:
        return True
    return os.getenv("JARVIS_ULTRA_SECURE_MODE", "false").lower() in ("true", "1", "yes")


def _default_signals() -> dict:
    return {
        "ultra_secure": False,
        "safe_mode": False,
        "system_ram_percent": 0.0,
        "integrity_status": "secure",   # secure | warning | critical
        "unknown_devices": 0,
        "stopped_services": 0,
        "dependency_status": "healthy",  # healthy | advisory | unknown
    }


def _gather_signals() -> dict:
    """Recopila las señales actuales de forma defensiva (imports perezosos)."""
    signals = _default_signals()

    signals["ultra_secure"] = is_ultra_secure_mode()

    try:
        from core.ram_guard import is_safe_mode_active
        signals["safe_mode"] = bool(is_safe_mode_active())
    except Exception:
        pass

    try:
        import psutil
        signals["system_ram_percent"] = float(psutil.virtual_memory().percent)
    except Exception:
        pass

    try:
        from core.jarvis_integrity import LATEST_HEALTH_REPORT
        signals["integrity_status"] = LATEST_HEALTH_REPORT.get("status", "secure")
    except Exception:
        pass

    try:
        from core.network_sentinel import active_devices
        signals["unknown_devices"] = sum(1 for d in active_devices if not d.get("known", False))
    except Exception:
        pass

    try:
        from core.services import get_services_status
        signals["stopped_services"] = sum(1 for v in get_services_status().values() if v == "stopped")
    except Exception:
        pass

    try:
        from core.dependency_health import LAST_STATUS
        signals["dependency_status"] = LAST_STATUS
    except Exception:
        pass

    return signals


def _aggregate_threat_level(signals: dict) -> dict:
    """Calcula el nivel de amenaza y sus motivos a partir de las señales.

    Prioridad: violet > red > amber > green.
    """
    # VIOLET — modo ultra-seguro (máxima prioridad).
    if signals.get("ultra_secure"):
        return _result("violet", ["Modo ultra-seguro activado"])

    # RED — condiciones críticas.
    red = []
    if signals.get("safe_mode"):
        red.append("Modo seguro de RAM activo")
    ram = signals.get("system_ram_percent", 0.0)
    if ram >= RAM_RED:
        red.append(f"RAM del sistema crítica ({ram:.0f}%)")
    if signals.get("integrity_status") == "critical":
        red.append("Fallo de integridad del sistema")
    unknown = signals.get("unknown_devices", 0)
    if unknown > 0:
        red.append(f"{unknown} dispositivo(s) desconocido(s) en la red")
    if red:
        return _result("red", red)

    # AMBER — condiciones de alerta.
    amber = []
    if ram >= RAM_AMBER:
        amber.append(f"RAM del sistema elevada ({ram:.0f}%)")
    if signals.get("integrity_status") == "warning":
        amber.append("Integridad del sistema en advertencia")
    stopped = signals.get("stopped_services", 0)
    if stopped > 0:
        amber.append(f"{stopped} servicio(s) detenido(s)")
    if signals.get("dependency_status") == "advisory":
        amber.append("Dependencias desactualizadas o sin mantenimiento")
    if amber:
        return _result("amber", amber)

    # GREEN — todo nominal.
    return _result("green", ["Todos los sistemas nominales"])


def _result(level: str, reasons: list) -> dict:
    return {
        "level": level,
        "reasons": reasons,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compute_threat_level() -> dict:
    """Recopila las señales actuales y devuelve el nivel de amenaza agregado."""
    return _aggregate_threat_level(_gather_signals())


def emit_threat_level() -> dict:
    """Calcula el nivel y lo emite a la GUI por Socket.IO. Devuelve el reporte."""
    report = compute_threat_level()
    try:
        from gui.app import socketio
        socketio.emit("threat_level_update", report)
    except Exception:
        pass
    return report


# --- Daemon periódico ---
THREAT_THREAD = None
stop_event = threading.Event()
_last_level = None


def _threat_loop():
    """Recalcula el nivel periódicamente y lo emite a la GUI solo cuando cambia."""
    global _last_level
    if stop_event.wait(timeout=25):
        return
    while not stop_event.is_set():
        try:
            report = compute_threat_level()
            if report["level"] != _last_level:
                _last_level = report["level"]
                try:
                    from gui.app import socketio
                    socketio.emit("threat_level_update", report)
                except Exception:
                    pass
                logger.info(f"[Threat] Nivel DEFCON: {report['level']} — {', '.join(report['reasons'])}")
        except Exception as e:
            logger.error(f"[Threat] Error en el bucle del daemon: {e}")
        interval = int(os.getenv("JARVIS_THREAT_LEVEL_INTERVAL", "30"))
        if stop_event.wait(timeout=interval):
            break


def start_threat_level_daemon():
    """Lanza el daemon del nivel de amenaza. Idempotente. Activado por defecto
    (es ligero); desactivable con JARVIS_THREAT_LEVEL_ENABLED=false."""
    global THREAT_THREAD
    if os.getenv("JARVIS_THREAT_LEVEL_ENABLED", "true").lower() not in ("true", "1", "yes"):
        logging.info("[Threat] Desactivado en .env.")
        return
    if THREAT_THREAD is not None and THREAT_THREAD.is_alive():
        return
    stop_event.clear()
    THREAT_THREAD = threading.Thread(target=_threat_loop, name="ThreatLevelDaemon", daemon=True)
    THREAT_THREAD.start()
    logging.info("[Threat] Daemon del nivel de amenaza DEFCON iniciado.")


def stop_threat_level_daemon():
    """Detiene el daemon del nivel de amenaza."""
    stop_event.set()
