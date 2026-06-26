"""
core/conversation_flow.py — Modo Conversación Continua (manos libres).

Jarvis ya mantiene la escucha tras un "Jarvis" a secas (modo conversación). Con el
Modo Continuo activado, además mantiene la conversación abierta tras CUALQUIER
comando, para que encadenes órdenes sin repetir la palabra clave, hasta que se
agota el tiempo de silencio.

Funciones puras (leen configuración); main.py las consulta en su bucle de escucha.
"""
import os


def continuous_mode_enabled() -> bool:
    """True si el Modo Conversación Continua está activado (off por defecto)."""
    return os.getenv("JARVIS_CONTINUOUS_MODE", "false").lower() in ("true", "1", "yes")


def conversation_timeout(default: int = 10) -> int:
    """Ventana de silencio (segundos) antes de volver al modo palabra de activación."""
    try:
        return int(os.getenv("JARVIS_CONVERSATION_TIMEOUT", str(default)))
    except (TypeError, ValueError):
        return default


def should_stay_conversational(processed_a_command: bool) -> bool:
    """Tras procesar un comando, ¿mantener abierto el modo conversación?"""
    return bool(processed_a_command) and continuous_mode_enabled()
