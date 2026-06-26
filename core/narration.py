"""
core/narration.py — "Stream de Pensamiento" ("Trabajando, señor").

Permite que las tareas largas narren lo que van haciendo paso a paso, tanto en el
HUD de la GUI (evento 'thought_stream') como por voz (opcional). Da la sensación
de que Jarvis trabaja contigo en tiempo real.

    narrate("Generando la mejora con el modelo de código…")
    narrate("Ejecutando la suite de pruebas…")

Funciones ligeras; voz y GUI aisladas. Off-voice por defecto (para no ser pesado).
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    """Narración en general (HUD). On por defecto."""
    return os.getenv("JARVIS_NARRATION_ENABLED", "true").lower() in ("true", "1", "yes")


def voice_enabled() -> bool:
    """Narración por voz. Off por defecto (puede ser locuaz en tareas largas)."""
    return os.getenv("JARVIS_NARRATION_VOICE", "false").lower() in ("true", "1", "yes")


def _emit(text: str):
    """Envía el paso al HUD si la GUI ya está cargada (no la importa)."""
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        mod.socketio.emit("thought_stream", {"text": text})
    except Exception:
        pass


def narrate(text: str, speak: bool = True, tone: str = "neutral") -> str:
    """Narra un paso de progreso (HUD siempre; voz si está activada). Devuelve el texto."""
    if not is_enabled() or not text or not text.strip():
        return ""
    _emit(text)
    if speak and voice_enabled():
        try:
            from tools.voice import speak as say
            say(text, disable_vad=True, tone=tone)
        except Exception as e:
            logger.warning(f"[Narration] No se pudo locutar el paso: {e}")
    return text
