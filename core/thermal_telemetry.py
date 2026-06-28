"""
core/thermal_telemetry.py — Telemetría térmica de hardware (Stark Thermal HUD).

Alimenta un mapa de calor 3D en la GUI con la carga real por núcleo de la CPU
(azul = frío/ocioso, rojo = caliente/saturado), además de CPU/RAM globales e,
de forma oportunista, temperatura de CPU y batería si el sistema las expone.

En muchos Windows la temperatura real y las RPM de ventiladores no son accesibles
sin admin ni un proveedor WMI específico (LibreHardwareMonitor). Por eso la señal
principal del heatmap es la carga por núcleo (siempre disponible vía psutil); la
temperatura/batería se incluyen sólo si se pueden leer (None en caso contrario).

Módulo ligero; psutil/WMI se aíslan de forma perezosa. La lógica de construcción
del snapshot es pura y testeable. Un daemon emite 'thermal_update' por Socket.IO.
"""
import os
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

THERMAL_THREAD = None
stop_event = threading.Event()


def _build_core_list(loads) -> list:
    """Convierte una lista de cargas por núcleo en [{id, load}] (puro)."""
    cores = []
    for i, load in enumerate(loads or []):
        try:
            val = round(float(load), 1)
        except (TypeError, ValueError):
            val = 0.0
        cores.append({"id": i, "load": val})
    return cores


def _celsius_from_decikelvin(dk) -> float:
    """Convierte décimas de Kelvin (MSAcpi_ThermalZoneTemperature) a °C (puro)."""
    return round(float(dk) / 10.0 - 273.15, 1)


def _read_per_core_load() -> list:
    try:
        import psutil
        return psutil.cpu_percent(percpu=True, interval=None)
    except Exception as e:
        logger.warning(f"[Thermal] No se pudo leer la carga por núcleo: {e}")
        return []


def _read_cpu_temperature():
    """Temperatura de CPU en °C (best-effort). None si no es accesible."""
    # 1) psutil (Linux y algunos portátiles).
    try:
        import psutil
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures() or {}
            for entries in temps.values():
                for e in entries:
                    if e.current:
                        return round(float(e.current), 1)
    except Exception:
        pass
    # 2) WMI MSAcpi_ThermalZoneTemperature (Windows, suele requerir admin).
    try:
        import win32com.client
        w = win32com.client.GetObject(r"winmgmts:\\.\root\WMI")
        for row in w.ExecQuery("SELECT * FROM MSAcpi_ThermalZoneTemperature"):
            return _celsius_from_decikelvin(row.CurrentTemperature)
    except Exception:
        pass
    return None


def _read_battery():
    """{'percent', 'plugged'} o None."""
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return None
        return {"percent": round(b.percent, 1), "plugged": bool(b.power_plugged)}
    except Exception:
        return None


def _read_ram_percent() -> float:
    try:
        import psutil
        return round(psutil.virtual_memory().percent, 1)
    except Exception:
        return 0.0


def get_thermal_snapshot() -> dict:
    """Snapshot de telemetría térmica para el heatmap 3D."""
    cores = _build_core_list(_read_per_core_load())
    loads = [c["load"] for c in cores]
    cpu_overall = round(sum(loads) / len(loads), 1) if loads else 0.0
    return {
        "cores": cores,
        "cpu_overall": cpu_overall,
        "ram_percent": _read_ram_percent(),
        "cpu_temp": _read_cpu_temperature(),
        "battery": _read_battery(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _emit(report: dict):
    """Emite a la GUI sólo si gui.app ya está cargado."""
    import sys
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        mod.socketio.emit("thermal_update", report)
    except Exception:
        pass


def emit_thermal_snapshot() -> dict:
    report = get_thermal_snapshot()
    _emit(report)
    return report


def _emit_event(event: str):
    import sys
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        mod.socketio.emit(event)
    except Exception:
        pass


def open_thermal():
    """Abre el mapa de calor 3D en la GUI y envía un snapshot inmediato."""
    _emit_event("thermal_open")
    emit_thermal_snapshot()


def close_thermal():
    """Cierra el mapa de calor 3D en la GUI."""
    _emit_event("thermal_close")


def _thermal_loop():
    # Primera lectura de cpu_percent devuelve 0; se descarta calentando el contador.
    _read_per_core_load()
    if stop_event.wait(timeout=2):
        return
    while not stop_event.is_set():
        try:
            emit_thermal_snapshot()
        except Exception as e:
            logger.error(f"[Thermal] Error en el bucle del daemon: {e}")
        interval = int(os.getenv("JARVIS_THERMAL_INTERVAL", "15"))
        if stop_event.wait(timeout=interval):
            break


def start_thermal_telemetry_daemon():
    """Lanza el daemon de telemetría térmica. Idempotente. Activado por defecto
    (ligero); desactivable con JARVIS_THERMAL_TELEMETRY_ENABLED=false."""
    global THERMAL_THREAD
    if os.getenv("JARVIS_THERMAL_TELEMETRY_ENABLED", "true").lower() not in ("true", "1", "yes"):
        logging.info("[Thermal] Desactivado en .env.")
        return
    if THERMAL_THREAD is not None and THERMAL_THREAD.is_alive():
        return
    stop_event.clear()
    THERMAL_THREAD = threading.Thread(target=_thermal_loop, name="ThermalTelemetryDaemon", daemon=True)
    THERMAL_THREAD.start()
    logging.info("[Thermal] Daemon de telemetría térmica iniciado.")


def stop_thermal_telemetry_daemon():
    """Detiene el daemon de telemetría térmica."""
    stop_event.set()
