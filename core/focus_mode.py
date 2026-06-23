"""
core/focus_mode.py — Protocolo de Enfoque "Verónica".

Al activarlo (voz o GUI), Jarvis:
  - Silencia las notificaciones toast de Windows (registro ToastEnabled,
    guardando el valor previo para restaurarlo).
  - Tiñe la GUI en ámbar cálido de alto contraste (clase body.focus-veronica).
  - Inicia un temporizador de productividad (cuenta atrás) que, al expirar,
    desactiva el protocolo y avisa.

Módulo ligero (stdlib); voz/GUI por imports perezosos. La lógica de estado y
formateo es pura y testeable; el registro de Windows se aísla en una función
mockeable.
"""
import os
import sys
import time
import logging
import threading

logger = logging.getLogger(__name__)

FOCUS_TIMER = None
stop_timer = threading.Event()
_active = False
_ends_at = None      # epoch (segundos) en que termina la sesión
_prev_toast = None   # valor previo de ToastEnabled, para restaurarlo


def is_focus_active() -> bool:
    return _active


def get_ends_at():
    return _ends_at


def _format_remaining(seconds) -> str:
    """MM:SS a partir de segundos restantes (puro)."""
    try:
        seconds = max(0, int(seconds))
    except (TypeError, ValueError):
        seconds = 0
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _set_toast_notifications(enabled: bool):
    """Activa/desactiva las notificaciones toast de Windows vía registro.
    Devuelve el valor previo (0/1) o None si no se pudo leer/escribir."""
    try:
        import winreg
    except ImportError:
        return None
    key_path = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                prev, _ = winreg.QueryValueEx(key, "ToastEnabled")
            except FileNotFoundError:
                prev = 1
            winreg.SetValueEx(key, "ToastEnabled", 0, winreg.REG_DWORD, 1 if enabled else 0)
            return prev
    except Exception as e:
        logger.warning(f"[Veronica] No se pudo ajustar las notificaciones de Windows: {e}")
        return None


def _emit(event: str, payload=None):
    """Emite a la GUI sólo si gui.app ya está cargado (no la importa)."""
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        if payload is None:
            mod.socketio.emit(event)
        else:
            mod.socketio.emit(event, payload)
    except Exception:
        pass


def _speak(text: str):
    try:
        from tools.voice import speak
        speak(text, disable_vad=True)
    except Exception as e:
        logger.warning(f"[Veronica] No se pudo emitir voz: {e}")


def _timer_loop(ends_at: float):
    """Espera hasta la hora de fin y desactiva el protocolo automáticamente."""
    while not stop_timer.is_set():
        if time.time() >= ends_at:
            stop_focus(announce=True, completed=True)
            return
        if stop_timer.wait(timeout=1):
            return


def start_focus(minutes=None, announce: bool = True) -> int:
    """Activa el Protocolo Verónica durante `minutes` (def. JARVIS_FOCUS_DEFAULT_MINUTES).
    Devuelve los minutos efectivos."""
    global _active, _ends_at, _prev_toast, FOCUS_TIMER
    if minutes is None:
        minutes = os.getenv("JARVIS_FOCUS_DEFAULT_MINUTES", "25")
    try:
        minutes = max(1, int(minutes))
    except (TypeError, ValueError):
        minutes = 25

    _active = True
    _ends_at = time.time() + minutes * 60

    if os.getenv("JARVIS_FOCUS_MUTE_NOTIFICATIONS", "true").lower() in ("true", "1", "yes"):
        _prev_toast = _set_toast_notifications(False)

    _emit("veronica_on", {"minutes": minutes, "ends_at": _ends_at})

    stop_timer.set()
    if FOCUS_TIMER is not None and FOCUS_TIMER.is_alive():
        FOCUS_TIMER.join(timeout=2)
    stop_timer.clear()
    FOCUS_TIMER = threading.Thread(target=_timer_loop, args=(_ends_at,),
                                   name="VeronicaTimer", daemon=True)
    FOCUS_TIMER.start()

    if announce:
        _speak(f"Protocolo Verónica iniciado, señor. Silenciando distractores externos "
               f"durante {minutes} minutos.")
    logging.info(f"[Veronica] Protocolo de enfoque iniciado ({minutes} min).")
    return minutes


def stop_focus(announce: bool = True, completed: bool = False) -> bool:
    """Desactiva el Protocolo Verónica y restaura las notificaciones."""
    global _active, _ends_at, _prev_toast
    stop_timer.set()
    was_active = _active

    if os.getenv("JARVIS_FOCUS_MUTE_NOTIFICATIONS", "true").lower() in ("true", "1", "yes"):
        # Restaura el valor previo; si no se conocía, deja las notificaciones activas.
        _set_toast_notifications(bool(_prev_toast) if _prev_toast is not None else True)
    _prev_toast = None

    _active = False
    _ends_at = None
    _emit("veronica_off")

    if announce and was_active:
        if completed:
            _speak("Sesión de enfoque completada, señor. Restaurando las notificaciones del sistema.")
        else:
            _speak("Protocolo Verónica finalizado, señor. Distractores restaurados.")
    logging.info("[Veronica] Protocolo de enfoque finalizado.")
    return was_active
