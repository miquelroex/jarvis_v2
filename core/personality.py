"""
core/personality.py — "Medidor de Sarcasmo" configurable de Jarvis.

Un dial 0-10 que regula cuánta ironía británica gasta Jarvis. El nivel se
persiste en disco y se inyecta dinámicamente en el system prompt, de modo que
puede cambiar en caliente sin reiniciar (la próxima respuesta ya lo refleja).

La directiva de tono según el nivel es pura y testeable.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SARCASM_FILE = Path("logs/sarcasm_level.txt")
DEFAULT_LEVEL = 3
MIN_LEVEL = 0
MAX_LEVEL = 10


def clamp_level(value) -> int:
    """Acota el nivel al rango [0, 10] (puro)."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_LEVEL
    return max(MIN_LEVEL, min(MAX_LEVEL, n))


def get_sarcasm_level() -> int:
    """Lee el nivel de sarcasmo persistido (DEFAULT_LEVEL si no existe)."""
    if not SARCASM_FILE.exists():
        return DEFAULT_LEVEL
    try:
        return clamp_level(SARCASM_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return DEFAULT_LEVEL


def _emit_level(level: int):
    """Notifica el nivel a la GUI si ya está cargada (no la importa)."""
    import sys
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        mod.socketio.emit("sarcasm_level_update", {"level": level})
    except Exception:
        pass


def set_sarcasm_level(value) -> int:
    """Fija (y acota) el nivel de sarcasmo. Devuelve el nivel efectivo."""
    level = clamp_level(value)
    try:
        SARCASM_FILE.parent.mkdir(exist_ok=True)
        SARCASM_FILE.write_text(str(level), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[Personality] No se pudo guardar el nivel de sarcasmo: {e}")
    _emit_level(level)
    return level


def adjust_sarcasm(delta: int) -> int:
    """Sube/baja el nivel de sarcasmo en `delta` y lo persiste."""
    return set_sarcasm_level(get_sarcasm_level() + delta)


def get_sarcasm_directive(level: int) -> str:
    """Devuelve la directiva de tono para inyectar en el prompt según el nivel (puro)."""
    level = clamp_level(level)
    if level <= 1:
        tone = ("Tono impecablemente formal y profesional, de mayordomo británico de "
                "protocolo estricto. Sin ironía ni bromas; cortesía absoluta.")
    elif level <= 4:
        tone = ("Tono formal y elegante con alguna pincelada muy sutil y ocasional de "
                "ironía británica. El humor seco aparece solo de vez en cuando.")
    elif level <= 7:
        tone = ("Ironía británica fina y recurrente, con humor seco evidente pero siempre "
                "respetuoso. Permítete comentarios mordaces ocasionales sin perder la elegancia.")
    else:
        tone = ("Modo compañero socarrón: ironía marcada y descarada, bromas secas frecuentes "
                "y réplicas ingeniosas. Nunca seas faltón, grosero ni condescendiente, y que "
                "la eficacia técnica jamás se resienta por el humor.")
    return (
        "\n\n=========================================\n"
        f"🎭 MEDIDOR DE SARCASMO: nivel {level}/10\n"
        f"{tone}\n"
        "=========================================\n"
    )
