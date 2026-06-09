import os
from core.fast_commands import normalize_text, handle_fast_command

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

    # 3. Enrutamiento directo a modelos especializados por palabras clave
    
    # Gemini
    if "gemini" in text or "google ai" in text or "googleai" in text:
        from tools.gemini_ai import ask_gemini
        try:
            resp = ask_gemini.invoke(command)
            return {"type": "delegation_gemini", "content": resp}
        except Exception as e:
            return {"type": "delegation_gemini_error", "content": f"Fallo al invocar Gemini: {str(e)}"}

    # Ultra (Requiere confirmación)
    if "modo ultra" in text or "gpt pro" in text or "gpt-pro" in text or "ultra" in text:
        from tools.model_delegate import ask_ultra_model
        try:
            resp = ask_ultra_model.invoke(command)
            return {"type": "delegation_ultra", "content": resp}
        except Exception as e:
            return {"type": "delegation_ultra_error", "content": f"Fallo al invocar el modelo Ultra: {str(e)}"}

    # Pro / Kimi (Requiere confirmación)
    if "modo pro" in text or "kimi" in text:
        from tools.model_delegate import ask_pro_model
        try:
            resp = ask_pro_model.invoke(command)
            return {"type": "delegation_pro", "content": resp}
        except Exception as e:
            return {"type": "delegation_pro_error", "content": f"Fallo al invocar el modelo Pro: {str(e)}"}

    # GPT (Requiere confirmación)
    if "gpt" in text or "chatgpt" in text:
        from tools.model_delegate import ask_gpt_model
        try:
            resp = ask_gpt_model.invoke(command)
            return {"type": "delegation_gpt", "content": resp}
        except Exception as e:
            return {"type": "delegation_gpt_error", "content": f"Fallo al invocar GPT: {str(e)}"}

    # Programación / Código
    code_keywords = [
        "escribe un script", "escribe una funcion", "crea una clase",
        "codigo", "bug", "error de python", "refactorizar", "refactoriza",
        "explicame este codigo", "git", "github", "crea un archivo",
        "scripts", "tools", "arquitectura"
    ]
    if any(kw in text for kw in code_keywords):
        from tools.model_delegate import ask_code_model
        try:
            resp = ask_code_model.invoke(command)
            return {"type": "delegation_code", "content": resp}
        except Exception as e:
            return {"type": "delegation_code_error", "content": f"Fallo al invocar el modelo de código: {str(e)}"}

    # Razonamiento / Pensamiento profundo
    reason_keywords = [
        "razona", "piensa despacio", "deduce", "analiza logicamente",
        "pensamiento profundo", "resuelve el acertijo", "piensa paso a paso",
        "analisis largo", "análisis largo", "razonamiento general"
    ]
    if any(kw in text for kw in reason_keywords):
        from tools.model_delegate import ask_reasoning_model
        try:
            resp = ask_reasoning_model.invoke(command)
            return {"type": "delegation_reasoning", "content": resp}
        except Exception as e:
            return {"type": "delegation_reasoning_error", "content": f"Fallo al invocar el modelo de razonamiento: {str(e)}"}

    # Si no cumple ninguna regla, delegar al agente LangChain
    return None
