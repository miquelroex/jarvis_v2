"""
core/model_config.py — Resolución de alias de modelos para el cambio en caliente.

Mapea nombres hablados (config/model_aliases.json) a la variable de entorno que
contiene el ID real del modelo, y resuelve esa variable con un default sensato.
Así el usuario puede decir "cambia al modelo de código" y Jarvis sabe a qué ID
de OpenRouter corresponde, respetando lo que haya configurado en el .env.

Módulo ligero (solo os/json/logging): no importa langchain ni tools, para que
sea testeable de forma aislada.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

_MODEL_ALIASES_PATH = os.path.join("config", "model_aliases.json")

# alias hablado (normalizado, minúsculas, sin tildes) -> variable de entorno con el ID
_DEFAULT_ALIASES = {
    "predeterminado": "JARVIS_MODEL_DEFAULT",
    "por defecto": "JARVIS_MODEL_DEFAULT",
    "deepseek": "JARVIS_MODEL_DEFAULT",
    "gemini": "JARVIS_MODEL_GEMINI",
    "google": "JARVIS_MODEL_GEMINI",
    "codigo": "JARVIS_MODEL_CODE",
    "code": "JARVIS_MODEL_CODE",
    "razonamiento": "JARVIS_MODEL_THINK",
    "pensamiento": "JARVIS_MODEL_THINK",
    "pro": "JARVIS_MODEL_PRO",
    "kimi": "JARVIS_MODEL_PRO",
    "gpt": "JARVIS_MODEL_GPT",
    "chatgpt": "JARVIS_MODEL_GPT",
    "ultra": "JARVIS_MODEL_ULTRA",
    "agente": "JARVIS_MODEL_AGENT",
}

# Valores por defecto de cada variable (coherentes con main.py / llm_factory),
# para resolver el ID aunque la variable no esté definida en el entorno.
_ENV_DEFAULTS = {
    "JARVIS_MODEL_DEFAULT": "deepseek/deepseek-v4-pro",
    "JARVIS_MODEL_GEMINI": "gemini-3.5-flash",
    "JARVIS_MODEL_CODE": "qwen/qwen3-coder",
    "JARVIS_MODEL_THINK": "qwen/qwen3.7-plus",
    "JARVIS_MODEL_PRO": "moonshotai/kimi-k2.6",
    "JARVIS_MODEL_GPT": "openai/gpt-5.4-mini",
    "JARVIS_MODEL_ULTRA": "",
    "JARVIS_MODEL_AGENT": "",
}

_aliases_cache = None


def _load_aliases(force_reload: bool = False) -> dict:
    """Carga el mapa alias->env desde config/model_aliases.json (con fallback a
    defaults embebidos). Cualquier error mantiene los defaults."""
    global _aliases_cache
    if _aliases_cache is not None and not force_reload:
        return _aliases_cache

    aliases = dict(_DEFAULT_ALIASES)
    try:
        if os.path.exists(_MODEL_ALIASES_PATH):
            with open(_MODEL_ALIASES_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for k, v in loaded.items():
                    if isinstance(k, str) and isinstance(v, str):
                        aliases[k.lower()] = v
            else:
                logger.warning("[Models] model_aliases.json no es un objeto JSON; usando defaults.")
    except Exception as e:
        logger.warning(f"[Models] Error al cargar model_aliases.json, usando defaults: {e}")

    _aliases_cache = aliases
    return aliases


def resolve_model_alias(alias: str, force_reload: bool = False):
    """Devuelve el ID de modelo para un alias hablado, o None si no se reconoce
    el alias o el modelo no está configurado."""
    if not alias:
        return None
    key = alias.strip().lower()
    aliases = _load_aliases(force_reload=force_reload)
    env_var = aliases.get(key)
    if env_var is None:
        return None
    model_id = os.getenv(env_var, _ENV_DEFAULTS.get(env_var, ""))
    return model_id or None


def available_aliases() -> list:
    """Lista de alias hablados reconocidos (para mensajes de ayuda)."""
    return sorted(_load_aliases().keys())
