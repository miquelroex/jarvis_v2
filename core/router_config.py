"""
core/router_config.py — Carga de las palabras clave del enrutador.

Externaliza a config/router_keywords.json las listas de keywords que usa
core/router.py para decidir a qué modelo especializado delegar. La lógica de
enrutamiento (prioridad, tool a invocar, tipos de retorno) permanece en código;
aquí solo viven los datos.

Robustez: si el archivo falta, no es válido, o le falta algún grupo, se usan los
valores por defecto embebidos. El enrutamiento nunca debe romperse por un
problema de configuración.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

_ROUTER_KEYWORDS_PATH = os.path.join("config", "router_keywords.json")

# Defaults embebidos: deben coincidir con config/router_keywords.json para que el
# comportamiento sea idéntico con o sin el archivo presente.
_DEFAULT_ROUTER_KEYWORDS = {
    "gemini": ["gemini", "google ai", "googleai"],
    "ultra": ["modo ultra", "gpt pro", "gpt-pro", "ultra"],
    "pro": ["modo pro", "kimi"],
    "gpt": ["gpt", "chatgpt"],
    "code": [
        "escribe un script", "escribe una funcion", "crea una clase",
        "codigo", "bug", "error de python", "refactorizar", "refactoriza",
        "explicame este codigo", "git", "github", "crea un archivo",
        "scripts", "tools", "arquitectura",
    ],
    "reasoning": [
        "razona", "piensa despacio", "deduce", "analiza logicamente",
        "pensamiento profundo", "resuelve el acertijo", "piensa paso a paso",
        "analisis largo", "razonamiento general",
    ],
}

_router_keywords_cache = None


def get_router_keywords(force_reload: bool = False) -> dict:
    """Devuelve las keywords del enrutador, cacheadas tras la primera carga.

    Lee config/router_keywords.json y completa con los defaults embebidos
    cualquier grupo ausente, vacío o inválido. Ante cualquier error, devuelve
    los defaults (el routing nunca se rompe por config).

    Args:
        force_reload: si True, ignora la caché y vuelve a leer el archivo.
    """
    global _router_keywords_cache
    if _router_keywords_cache is not None and not force_reload:
        return _router_keywords_cache

    keywords = {key: list(val) for key, val in _DEFAULT_ROUTER_KEYWORDS.items()}
    try:
        if os.path.exists(_ROUTER_KEYWORDS_PATH):
            with open(_ROUTER_KEYWORDS_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for key in _DEFAULT_ROUTER_KEYWORDS:
                    val = loaded.get(key)
                    if isinstance(val, list) and val:
                        # Normalizamos a minúsculas; el matching se hace sobre texto ya normalizado.
                        keywords[key] = [str(k).lower() for k in val]
            else:
                logger.warning("[Router] router_keywords.json no es un objeto JSON; usando defaults.")
    except Exception as e:
        logger.warning(f"[Router] Error al cargar router_keywords.json, usando defaults: {e}")

    _router_keywords_cache = keywords
    return keywords
