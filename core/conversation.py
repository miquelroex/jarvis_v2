"""
core/conversation.py — Cerebro conversacional reutilizable de Jarvis.

Centraliza el flujo "texto de entrada -> respuesta": primero el enrutador rápido
(smart_route) y, si no resuelve, el agente LangChain (con registro de tokens).
Lo usan tanto el procesamiento por voz local (main.py) como el chat de Telegram,
evitando duplicar la lógica.

No toca la GUI ni reproduce voz: sólo devuelve (texto, modelo_usado).
"""
import os
import logging

logger = logging.getLogger(__name__)


def model_display_for_route(route_type: str) -> str:
    """Nombre legible del modelo/procesador según el tipo de ruta (puro)."""
    rt = route_type or ""
    if rt == "fast_command":
        return "Comando Local"
    if "gemini" in rt:
        return os.getenv("JARVIS_MODEL_GEMINI", "gemini-3.5-flash")
    if "pro" in rt:
        return os.getenv("JARVIS_MODEL_PRO", "moonshotai/kimi-k2.6")
    if "gpt" in rt:
        return os.getenv("JARVIS_MODEL_GPT", "openai/gpt-5.4-mini")
    if "code" in rt:
        return os.getenv("JARVIS_MODEL_CODE", "qwen/qwen3-coder")
    if "reasoning" in rt:
        return os.getenv("JARVIS_MODEL_THINK", "qwen/qwen3.7-plus")
    return "Procesador Interno"


def get_response(text: str):
    """Procesa un mensaje de texto y devuelve (respuesta, modelo_usado).

    Usa el enrutador rápido y, si no resuelve, delega en el agente LangChain.
    Lanza excepción si el agente falla (el llamador decide cómo informar)."""
    from core.router import smart_route

    route_result = smart_route(text)
    if route_result:
        return route_result["content"], model_display_for_route(route_result.get("type", ""))

    # Delegar al agente de LangChain.
    from core.agent_manager import get_executor
    from core.model_logging import log_model_usage
    from langchain_community.callbacks import get_openai_callback

    default_model = os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v4-pro")
    prompt_tokens = 0
    completion_tokens = 0
    try:
        with get_openai_callback() as cb:
            response = get_executor().invoke({"input": text})
            prompt_tokens = cb.prompt_tokens
            completion_tokens = cb.completion_tokens
        content = response["output"]
    except Exception:
        log_model_usage(
            tool_name="main_model", model_name=default_model, prompt=text,
            prompt_tokens=0, completion_tokens=0, provider="openrouter",
        )
        raise

    log_model_usage(
        tool_name="main_model", model_name=default_model, prompt=text,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, provider="openrouter",
    )
    return content, default_model
