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
