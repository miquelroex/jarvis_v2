"""
core/reactions.py — "Reacciones con Alma" (micro-emociones de Jarvis).

Da a Jarvis respuestas con carga emocional contenida ante eventos del sistema:
alivio cuando unas pruebas vuelven a pasar (más intenso si venían de una racha de
fallos), urgencia medida en una alerta crítica, orgullo seco cuando algo sale
impecable, fastidio elegante ante un error tonto.

La selección de frase es pura y testeable; la locución (con su tono de voz
adaptativo) se aísla. También aporta una directiva breve para el system prompt,
de modo que las respuestas conversacionales también lleven ese matiz emocional.
"""
import os
import random
import logging

logger = logging.getLogger(__name__)

STREAK_THRESHOLD = 3  # nº de fallos a partir del cual el alivio es "mayor"

REACTIONS = {
    "test_recovered": {
        "tone": "success",
        "phrases": [
            "Excelente, señor. Las pruebas de {name} vuelven a pasar. Confieso cierto alivio.",
            "De nuevo en verde, señor. {name} responde como debe.",
        ],
        "streak_phrases": [
            "Por fin, señor: {name} pasa tras {fails} intentos. Un alivio considerable, debo admitir.",
            "Lo hemos resuelto, señor. {name} en verde tras {fails} fallos. Persistencia recompensada.",
        ],
    },
    "test_broken": {
        "tone": "alert",
        "phrases": [
            "Señor, lamento informar que {name} ha empezado a fallar. Conviene revisarlo.",
            "Atención, señor: {name} acaba de romperse. Recomiendo una mirada.",
        ],
    },
    "task_success": {
        "tone": "success",
        "phrases": [
            "Hecho, señor. Limpio y a la primera.",
            "Completado con precisión, señor. Como debe ser.",
        ],
    },
    "critical_alert": {
        "tone": "alert",
        "phrases": [
            "Señor, esto requiere su atención inmediata.",
            "Sin ánimo de alarmar, señor, pero es urgente.",
        ],
    },
    "trivial_error": {
        "tone": "humor",
        "phrases": [
            "Un desliz menor, señor. Ya lo había previsto.",
            "Nada que no esperara, señor. Procedo a corregirlo.",
        ],
    },
}


def is_reactions_enabled() -> bool:
    return os.getenv("JARVIS_REACTIONS_ENABLED", "true").lower() in ("true", "1", "yes")


def get_reaction(event: str, context: dict = None, rng=None):
    """Devuelve {phrase, tone} para un evento, o None si no se reconoce (puro).

    Si el contexto trae 'fails' >= STREAK_THRESHOLD y el evento tiene variantes de
    racha, usa esas (alivio mayor). Las plantillas se rellenan con el contexto."""
    spec = REACTIONS.get(event)
    if not spec:
        return None
    context = context or {}
    rng = rng or random
    phrases = spec["phrases"]
    if context.get("fails", 0) >= STREAK_THRESHOLD and spec.get("streak_phrases"):
        phrases = spec["streak_phrases"]
    template = rng.choice(phrases)
    try:
        phrase = template.format(**context)
    except (KeyError, IndexError):
        phrase = template
    return {"phrase": phrase, "tone": spec["tone"]}


def react(event: str, context: dict = None, speak_out: bool = True) -> str:
    """Selecciona y (si procede) locuta una reacción emocional. Devuelve la frase."""
    if not is_reactions_enabled():
        return ""
    reaction = get_reaction(event, context)
    if not reaction:
        return ""
    if speak_out:
        try:
            from tools.voice import speak
            speak(reaction["phrase"], disable_vad=True, tone=reaction["tone"])
        except Exception as e:
            logger.warning(f"[Reactions] No se pudo locutar la reacción: {e}")
    return reaction["phrase"]


EMOTION_DIRECTIVE = (
    "\n\n=========================================\n"
    "💫 REACCIONES CON ALMA\n"
    "Colorea tus respuestas con una emoción contenida y elegante, según el momento: "
    "alivio cuando algo se resuelve tras dificultad, urgencia medida (nunca pánico) en "
    "alertas, orgullo seco cuando un resultado es impecable y un fastidio fino ante un "
    "error trivial. Una pincelada emocional, jamás teatral; la precisión técnica manda.\n"
    "=========================================\n"
)


def get_emotion_directive() -> str:
    """Directiva de emoción para inyectar en el system prompt (vacía si desactivado)."""
    return EMOTION_DIRECTIVE if is_reactions_enabled() else ""
