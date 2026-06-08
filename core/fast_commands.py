import os
import webbrowser
import unicodedata
import re
from datetime import datetime

from tools.browser import open_website
from tools.launcher import open_windows_app
from tools.time import get_time
from tools.date import get_date

def normalize_text(text: str) -> str:
    """Normaliza el texto quitando acentos, convirtiendo a minúsculas y limpiando espacios."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text

def handle_fast_command(command: str):
    """
    Comprueba si el comando introducido coincide con una orden local rápida
    (abrir navegador, aplicaciones de Windows, preguntar la hora/fecha).
    Retorna la respuesta de Jarvis si se maneja localmente, o None si debe ir al agente.
    """
    text = normalize_text(command)

    # --- Comandos rápidos de Memoria Persistente ---
    from core.memory import save_memory, search_memories, delete_memory_by_content, get_all_memories

    # 1. Guardar recuerdos
    match_save_pref = None
    for pref in ["recuerda que ", "recuerda ", "guardar en memoria "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            match_save_pref = pref
            break
    if match_save_pref is not None:
        content_to_save = command[len(match_save_pref):].strip()
        if content_to_save:
            saved = save_memory(content_to_save, category="preference", source="fast_command")
            if saved:
                return f"Entendido, señor. He guardado en mi memoria: {content_to_save}."
            else:
                return f"Señor, ese recuerdo ya estaba registrado en mi memoria."
        return "Señor, ¿qué es lo que desea que recuerde?"

    # 2. Olvidar recuerdos
    match_delete_pref = None
    for pref in ["olvida que ", "olvida ", "borra de tu memoria "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            match_delete_pref = pref
            break
    if match_delete_pref is not None:
        content_to_delete = command[len(match_delete_pref):].strip()
        if content_to_delete:
            deleted = delete_memory_by_content(content_to_delete)
            if deleted:
                return f"Entendido, señor. He olvidado lo relacionado con: {content_to_delete}."
            else:
                return f"No he encontrado ningún recuerdo relacionado con '{content_to_delete}', señor."
        return "Señor, ¿qué recuerdo desea que olvide?"

    # 3. Consultar recuerdos
    # Consulta general
    if text == "que recuerdas" or text == "dime mis recuerdos":
        mems = get_all_memories(limit=20)
        if mems:
            formatted = "\n".join(f"- {m['content']}" for m in mems)
            return f"Esto es lo que recuerdo, señor:\n{formatted}"
        return "No tengo recuerdos guardados por ahora, señor."

    # Consulta específica
    match_query_pref = None
    for pref in ["que recuerdas de ", "que recuerdas sobre "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            match_query_pref = pref
            break
    if match_query_pref is not None:
        query_text = command[len(match_query_pref):].strip()
        if query_text:
            matches = search_memories(query_text)
            if matches:
                formatted = "\n".join(f"- {m['content']}" for m in matches)
                return f"Recuerdo lo siguiente sobre '{query_text}', señor:\n{formatted}"
            return f"No tengo recuerdos relacionados con '{query_text}', señor."
        return "Señor, ¿de qué desea que haga memoria?"

    # --- Comandos locales estándar ---
    websites = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
        "chatgpt": "https://chatgpt.com",
        "whatsapp": "https://web.whatsapp.com",
    }

    apps = {
        "calculadora": "calc",
        "bloc de notas": "notepad",
        "notepad": "notepad",
        "explorador": "explorer",
        "archivos": "explorer",
        "chrome": "chrome",
        "spotify": "spotify",
    }

    for name, url in websites.items():
        if f"abre {name}" in text or f"abrir {name}" in text:
            open_website.invoke({"url": url})
            return f"Abriendo {name}, señor."

    for name, executable in apps.items():
        if f"abre {name}" in text or f"abrir {name}" in text:
            open_windows_app.invoke({"app_executable": executable})
            return f"Abriendo {name}, señor."

    if "que hora es" in text or "dime la hora" in text:
        res = get_time.invoke({})
        # Extraer la hora en formato HH:MM
        match = re.search(r"(\d{2}:\d{2})", res)
        if match:
            return f"Son las {match.group(1)}, señor."
        now = datetime.now()
        return f"Son las {now.hour:02d}:{now.minute:02d}, señor."

    if "que dia es" in text or "fecha de hoy" in text or "que fecha es" in text:
        res = get_date.invoke({})
        return f"Hoy es {res}."

    return None
