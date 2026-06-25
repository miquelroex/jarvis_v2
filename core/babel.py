"""
core/babel.py — Protocolo Babel (traducción en vivo).

Traduce texto entre idiomas usando un LLM. Reutilizable desde:
  - voz local ("traduce al inglés ...") vía fast_commands,
  - chat de Telegram (/translate ...).

La detección de idioma destino, el armado del prompt y el parseo de la respuesta
son funciones puras y testeables; la llamada al LLM se aísla (mockeable).
"""
import os
import re
import json
import logging
import unicodedata

logger = logging.getLogger(__name__)

DEFAULT_TARGET = "español"

# Alias de idioma (clave sin acentos/minúscula) -> nombre canónico mostrado.
LANG_ALIASES = {
    "ingles": "inglés", "english": "inglés", "en": "inglés",
    "frances": "francés", "french": "francés", "fr": "francés",
    "aleman": "alemán", "german": "alemán", "de": "alemán",
    "italiano": "italiano", "italian": "italiano", "it": "italiano",
    "portugues": "portugués", "portuguese": "portugués", "pt": "portugués",
    "japones": "japonés", "japanese": "japonés", "ja": "japonés",
    "chino": "chino", "chinese": "chino", "zh": "chino",
    "ruso": "ruso", "russian": "ruso", "ru": "ruso",
    "arabe": "árabe", "arabic": "árabe", "ar": "árabe",
    "espanol": "español", "spanish": "español", "es": "español", "castellano": "español",
}


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def normalize_lang(name):
    """Devuelve el nombre canónico del idioma o None si no se reconoce (puro)."""
    if not name:
        return None
    key = _strip_accents(name.strip().lower())
    return LANG_ALIASES.get(key)


def parse_translate_command(command: str):
    """De 'traduce al inglés hola qué tal' -> ('inglés', 'hola qué tal').

    Sin idioma explícito, el destino es None (el llamador usará DEFAULT_TARGET).
    Conserva mayúsculas/acentos del texto a traducir (puro)."""
    raw = (command or "").strip()
    low = raw.lower()
    for verb in ("tradúceme ", "traduceme ", "traduce ", "traducir ",
                 "cómo se dice ", "como se dice "):
        if low.startswith(verb):
            raw = raw[len(verb):].strip()
            low = low[len(verb):].strip()
            break
    target = None
    tokens = low.split()
    if len(tokens) >= 2 and tokens[0] in ("al", "a", "en"):
        canon = normalize_lang(tokens[1])
        if canon:
            target = canon
            # .lower() conserva longitud, así que el índice en `low` vale para `raw`.
            idx = low.find(tokens[1], len(tokens[0])) + len(tokens[1])
            raw = raw[idx:].strip()
    return target, raw


def build_translation_prompt(text: str, target_lang: str) -> str:
    """Prompt de traducción que pide JSON estricto (puro)."""
    return (
        f"Eres un traductor profesional. Traduce el texto al {target_lang}. "
        "Devuelve SOLO un objeto JSON válido con las claves \"source_language\" "
        "(el idioma detectado del texto original, nombrado en español) y "
        "\"translation\" (la traducción fiel y natural). Sin texto adicional.\n\n"
        f"Texto:\n{text}"
    )


def parse_translation_response(raw: str) -> dict:
    """Extrae {source_language, translation} de la respuesta del LLM (robusto, puro)."""
    if not raw or not raw.strip():
        return {"source_language": "desconocido", "translation": ""}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(0))
            return {
                "source_language": (d.get("source_language") or "desconocido"),
                "translation": (d.get("translation") or "").strip(),
            }
        except Exception:
            pass
    # Sin JSON: tratar toda la respuesta como traducción.
    return {"source_language": "desconocido", "translation": raw.strip()}


def _invoke_llm(prompt: str) -> str:
    from core.llm_factory import get_llm
    model = os.getenv("JARVIS_MODEL_TRANSLATE") or os.getenv("JARVIS_MODEL_THINK") or None
    llm = get_llm(model_name=model, temperature=0.1)
    resp = llm.invoke(prompt)
    return getattr(resp, "content", str(resp))


def translate(text: str, target_lang=None) -> dict:
    """Traduce `text` al idioma destino. Devuelve
    {source_language, translation, target_language}."""
    target = (normalize_lang(target_lang) if target_lang else None) or DEFAULT_TARGET
    if not text or not text.strip():
        return {"source_language": "desconocido", "translation": "", "target_language": target}
    try:
        raw = _invoke_llm(build_translation_prompt(text, target))
    except Exception as e:
        logger.warning(f"[Babel] Error al traducir: {e}")
        return {"source_language": "desconocido", "translation": "", "target_language": target}
    parsed = parse_translation_response(raw)
    parsed["target_language"] = target
    return parsed
