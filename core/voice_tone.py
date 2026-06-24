"""
core/voice_tone.py — Voz adaptativa de Jarvis (Tone Shifting).

Define perfiles de tono (velocidad, pitch y, para ElevenLabs, estabilidad/estilo)
y los aplica según el contexto de la locución: sereno al informar, firme y algo
más rápido en alertas, pausado y grave de noche, ligeramente brillante al
confirmar un éxito, y juguetón en la ironía.

Módulo puro y testeable: sólo cadenas/diccionarios. tools/voice.py consume estos
parámetros al sintetizar con Edge-TTS / ElevenLabs.
"""
import unicodedata

NEUTRAL = "neutral"

# Cada tono: rate/pitch para Edge-TTS y stability/style para ElevenLabs.
TONES = {
    "neutral": {"rate": "+0%",  "pitch": "+0Hz", "stability": 0.5,  "style": 0.0},
    "alert":   {"rate": "+13%", "pitch": "-3Hz", "stability": 0.35, "style": 0.45},
    "calm":    {"rate": "-12%", "pitch": "-8Hz", "stability": 0.7,  "style": 0.0},
    "success": {"rate": "+4%",  "pitch": "+6Hz", "stability": 0.5,  "style": 0.2},
    "humor":   {"rate": "-2%",  "pitch": "+5Hz", "stability": 0.45, "style": 0.5},
}

# Palabras clave (sin acentos, minúsculas) que delatan cada tono.
_ALERT_KW = ("alerta", "critico", "peligro", "emergencia", "fallo grave",
             "consumo critico", "ram critica", "amenaza", "urgente", "atencion")
_SUCCESS_KW = ("completado", "completada", "hecho", "listo", "resuelto",
               "exito", "finalizada con exito", "operativo", "nominal")
_CALM_KW = ("es bastante tarde", "descanso", "descansar", "buenas noches",
            "le sugiero suspender", "modo noche")
_HUMOR_KW = ("con el debido respeto", "poco ortodoxa", "modesta", "ciertamente original",
             "interesante decision", "interesante estrategia", "permitame señalar")


def _normalize(text: str) -> str:
    text = (text or "").lower()
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def detect_tone(text: str) -> str:
    """Infiere el tono más adecuado a partir del texto (puro)."""
    t = _normalize(text)
    # Las alertas mandan: si hay señal de alerta, prevalece.
    if any(kw in t for kw in _ALERT_KW):
        return "alert"
    if any(kw in t for kw in _CALM_KW):
        return "calm"
    if any(kw in t for kw in _HUMOR_KW):
        return "humor"
    if any(kw in t for kw in _SUCCESS_KW):
        return "success"
    return NEUTRAL


def resolve_tone(text: str, tone=None) -> str:
    """Devuelve un tono válido: el explícito si existe, o el detectado del texto."""
    if tone and tone in TONES:
        return tone
    return detect_tone(text)


def get_edge_params(tone: str) -> dict:
    """Parámetros rate/pitch para Edge-TTS según el tono."""
    cfg = TONES.get(tone, TONES[NEUTRAL])
    return {"rate": cfg["rate"], "pitch": cfg["pitch"]}


def get_eleven_settings(tone: str) -> dict:
    """Ajustes stability/style para ElevenLabs según el tono."""
    cfg = TONES.get(tone, TONES[NEUTRAL])
    return {"stability": cfg["stability"], "style": cfg["style"]}