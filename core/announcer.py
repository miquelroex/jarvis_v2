"""
core/announcer.py — Anuncios Dramáticos de Notificaciones.

Locuta/anuncia las notificaciones entrantes con la cadencia de las películas y las
muestra como un banner en la GUI. Reutilizable: cualquier fuente (Telegram, red,
eventos internos) puede llamar a announce().

    announce("Telegram", kind="message")        -> "Señor, mensaje entrante de Telegram."
    announce("Mamá", kind="call")               -> "Señor, una llamada entrante de Mamá."
    announce("build", kind="alert", priority="high")

format_announcement es puro; voz y GUI se aíslan. Leer las notificaciones del SO
(toasts de Windows) queda fuera por requerir WinRT/permisos no disponibles aquí.
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    """Banner en la GUI. On por defecto."""
    return os.getenv("JARVIS_ANNOUNCE_ENABLED", "true").lower() in ("true", "1", "yes")


def voice_enabled() -> bool:
    """Locución por voz de las notificaciones. Off por defecto (puede ser pesado)."""
    return os.getenv("JARVIS_ANNOUNCE_VOICE", "false").lower() in ("true", "1", "yes")


def format_announcement(source: str, kind: str = "message", priority: str = "normal") -> str:
    """Frase dramática estilo Jarvis para una notificación (puro)."""
    src = (source or "").strip() or "origen desconocido"
    kind = (kind or "message").lower()
    priority = (priority or "normal").lower()
    if kind == "call":
        return f"Señor, una llamada entrante de {src}."
    if kind == "device":
        return f"Señor, dispositivo entrante en la red: {src}."
    if kind == "alert":
        prefix = "ALERTA PRIORITARIA" if priority == "high" else "Alerta"
        return f"{prefix}, señor: {src}."
    # message
    if priority == "high":
        return f"Mensaje prioritario de {src}, señor."
    return f"Señor, mensaje entrante de {src}."


def _emit(payload: dict):
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        mod.socketio.emit("notification_announce", payload)
    except Exception:
        pass


def announce(source: str, kind: str = "message", priority: str = "normal", speak: bool = True) -> str:
    """Anuncia una notificación: banner en la GUI y (opcional) voz. Devuelve el texto."""
    if not is_enabled():
        return ""
    text = format_announcement(source, kind, priority)
    _emit({"text": text, "source": source, "kind": kind, "priority": priority})
    if speak and voice_enabled():
        try:
            from tools.voice import speak as say
            say(text, disable_vad=True, tone="alert" if priority == "high" else "neutral")
        except Exception as e:
            logger.warning(f"[Announcer] No se pudo locutar la notificación: {e}")
    return text
