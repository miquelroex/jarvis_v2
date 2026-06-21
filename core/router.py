import os
from core.fast_commands import normalize_text, handle_fast_command
from core.router_config import get_router_keywords

def smart_route(command: str):
    """
    Analiza la petición del usuario en Python y determina el mejor camino
    de ejecución antes de involucrar al agente completo de LangChain.
    
    Retorna un diccionario si intercepta y maneja el comando:
        {"type": "fast_command" | "delegation_...", "content": respuesta_texto}
    O retorna None si debe delegar el flujo al agente principal de LangChain.
    """
    # 1. Si hay una acción pendiente de confirmación (modelo, terminal, filesystem, etc.),
    # desactivamos el enrutador para que el agente maneje "confirmo" / "cancela".
    if os.path.exists("logs/pending_action.json") or os.path.exists("logs/pending_model_request.json") or os.path.exists("logs/pending_terminal_command.json"):
        return None

    # 2. Comprobación de comandos rápidos locales (síncronos)
    fast_resp = handle_fast_command(command)
    if fast_resp is not None:
        return {"type": "fast_command", "content": fast_resp}

    text = normalize_text(command)

    # 3. Enrutamiento directo a modelos especializados por palabras clave.
    #    Las listas de keywords viven en config/router_keywords.json (con fallback
    #    a defaults embebidos). El orden de prioridad y la lógica por ruta se
    #    mantienen aquí en código.
    keywords = get_router_keywords()

    # Gemini
    if any(kw in text for kw in keywords["gemini"]):
        from tools.gemini_ai import ask_gemini
        try:
            resp = ask_gemini.invoke(command)
            return {"type": "delegation_gemini", "content": resp}
        except Exception as e:
            return {"type": "delegation_gemini_error", "content": f"Fallo al invocar Gemini: {str(e)}"}

    # Ultra (Requiere confirmación)
    if any(kw in text for kw in keywords["ultra"]):
        from tools.model_delegate import ask_ultra_model
        try:
            resp = ask_ultra_model.invoke(command)
            return {"type": "delegation_ultra", "content": resp}
        except Exception as e:
            return {"type": "delegation_ultra_error", "content": f"Fallo al invocar el modelo Ultra: {str(e)}"}

    # Pro / Kimi (Requiere confirmación)
    if any(kw in text for kw in keywords["pro"]):
        from tools.model_delegate import ask_pro_model
        try:
            resp = ask_pro_model.invoke(command)
            return {"type": "delegation_pro", "content": resp}
        except Exception as e:
            return {"type": "delegation_pro_error", "content": f"Fallo al invocar el modelo Pro: {str(e)}"}

    # GPT (Requiere confirmación)
    if any(kw in text for kw in keywords["gpt"]):
        from tools.model_delegate import ask_gpt_model
        try:
            resp = ask_gpt_model.invoke(command)
            return {"type": "delegation_gpt", "content": resp}
        except Exception as e:
            return {"type": "delegation_gpt_error", "content": f"Fallo al invocar GPT: {str(e)}"}

    # Programación / Código
    if any(kw in text for kw in keywords["code"]):
        from tools.model_delegate import ask_code_model
        try:
            resp = ask_code_model.invoke(command)
            return {"type": "delegation_code", "content": resp}
        except Exception as e:
            return {"type": "delegation_code_error", "content": f"Fallo al invocar el modelo de código: {str(e)}"}

    # Razonamiento / Pensamiento profundo
    if any(kw in text for kw in keywords["reasoning"]):
        from tools.model_delegate import ask_reasoning_model
        try:
            resp = ask_reasoning_model.invoke(command)
            return {"type": "delegation_reasoning", "content": resp}
        except Exception as e:
            return {"type": "delegation_reasoning_error", "content": f"Fallo al invocar el modelo de razonamiento: {str(e)}"}

    # Si no cumple ninguna regla, delegar al agente LangChain
    return None
