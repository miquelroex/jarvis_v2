"""
core/night_mode.py — Protocolo "Blackout" (modo noche inteligente).

Pasada cierta hora, Jarvis tiñe la GUI en tonos oscuros/cálidos, sugiere
descansar con voz suave (una vez por noche) y, opcionalmente, baja el volumen.
Al llegar la mañana, restaura el modo normal.

Módulo ligero (stdlib); voz/audio/GUI por imports perezosos.
"""
import os
import sys
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

BLACKOUT_THREAD = None
stop_event = threading.Event()
_blackout_active = False
_greeted_date = None  # fecha del último aviso suave (uno por noche)


def _is_night(hour: int, start: int, end: int) -> bool:
    """True si la hora cae en la franja nocturna [start, end), con salto de medianoche."""
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end  # cruza la medianoche


def is_blackout_active() -> bool:
    return _blackout_active


def _emit(event: str):
    """Emite a la GUI solo si gui.app ya está cargado (no la importa)."""
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        mod.socketio.emit(event)
    except Exception:
        pass


def _gentle_reminder():
    try:
        from tools.voice import speak
        speak(
            "Señor, es bastante tarde. Le sugiero considerar un descanso; "
            "su rendimiento se optimiza con un buen sueño.",
            disable_vad=True,
        )
    except Exception as e:
        logger.warning(f"[NightMode] No se pudo emitir el aviso de descanso: {e}")


def _maybe_lower_volume():
    if os.getenv("JARVIS_BLACKOUT_LOWER_VOLUME", "false").lower() not in ("true", "1", "yes"):
        return
    try:
        from core.system_audio import set_volume
        set_volume(int(os.getenv("JARVIS_BLACKOUT_VOLUME", "30")))
    except Exception as e:
        logger.warning(f"[NightMode] No se pudo bajar el volumen: {e}")


def set_blackout(active: bool, announce: bool = False) -> bool:
    """Activa/desactiva el modo noche: tiñe la GUI y (si announce) avisa por voz."""
    global _blackout_active
    _blackout_active = bool(active)
    _emit("blackout_on" if active else "blackout_off")
    if active and announce:
        _gentle_reminder()
        _maybe_lower_volume()
    return _blackout_active


def _blackout_loop():
    """Comprueba periódicamente la hora y entra/sale del modo noche."""
    global _blackout_active, _greeted_date
    if stop_event.wait(timeout=20):
        return
    while not stop_event.is_set():
        try:
            now = datetime.now()
            start = int(os.getenv("JARVIS_BLACKOUT_START_HOUR", "0"))
            end = int(os.getenv("JARVIS_BLACKOUT_END_HOUR", "7"))
            night = _is_night(now.hour, start, end)
            if night and not _blackout_active:
                announce = _greeted_date != now.date()
                _greeted_date = now.date()
                set_blackout(True, announce=announce)
            elif not night and _blackout_active:
                set_blackout(False)
        except Exception as e:
            logger.error(f"[NightMode] Error en el bucle del daemon: {e}")
        if stop_event.wait(timeout=int(os.getenv("JARVIS_BLACKOUT_CHECK_INTERVAL", "300"))):
            break


def start_night_mode_daemon():
    """Lanza el daemon del modo noche. Idempotente. Off por defecto
    (JARVIS_BLACKOUT_ENABLED)."""
    global BLACKOUT_THREAD
    if os.getenv("JARVIS_BLACKOUT_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[NightMode] Desactivado en .env.")
        return
    if BLACKOUT_THREAD is not None and BLACKOUT_THREAD.is_alive():
        return
    stop_event.clear()
    BLACKOUT_THREAD = threading.Thread(target=_blackout_loop, name="NightModeDaemon", daemon=True)
    BLACKOUT_THREAD.start()
    logging.info("[NightMode] Daemon del modo noche iniciado.")


def stop_night_mode_daemon():
    """Detiene el daemon del modo noche."""
    stop_event.set()