"""
core/morning_briefing.py — Briefing matutino de Jarvis.

Complemento del resumen nocturno (daily_digest): por la mañana entrega un
briefing con el saludo, la fecha, el tiempo (OpenWeatherMap), los cambios
pendientes en el repositorio y los recordatorios programados para hoy.

Módulo ligero (stdlib): los imports de voz/servicios/memoria son perezosos.
"""
import os
import json
import logging
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _get_weather() -> str:
    """Línea de clima vía OpenWeatherMap. None si no está configurado o falla.

    Requiere OPENWEATHER_API_KEY y JARVIS_WEATHER_CITY (p.ej. "Madrid,ES").
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    city = os.getenv("JARVIS_WEATHER_CITY")
    if not api_key or not city:
        return None
    units = os.getenv("JARVIS_WEATHER_UNITS", "metric")
    lang = os.getenv("JARVIS_WEATHER_LANG", "es")
    url = (
        "https://api.openweathermap.org/data/2.5/weather?"
        + urllib.parse.urlencode({"q": city, "appid": api_key, "units": units, "lang": lang})
    )
    try:
        with urllib.request.urlopen(url, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
        desc = data["weather"][0]["description"]
        temp = round(data["main"]["temp"])
        feels = round(data["main"]["feels_like"])
        sym = "°C" if units == "metric" else "°F"
        city_name = city.split(",")[0]
        return f"El tiempo en {city_name}: {desc}, {temp}{sym} (sensación de {feels}{sym})."
    except Exception as e:
        logging.warning(f"[Briefing] No se pudo obtener el clima: {e}")
        return None


def _get_pending_changes() -> int:
    """Número de archivos con cambios sin confirmar en el repositorio. Solo lectura."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
        )
        if res.returncode != 0:
            return 0
        return len([line for line in res.stdout.splitlines() if line.strip()])
    except Exception as e:
        logging.warning(f"[Briefing] No se pudo leer el estado de git: {e}")
        return 0


def _is_today(next_run: str) -> bool:
    """True si una fecha ISO (UTC) cae hoy en horario local."""
    try:
        dt = datetime.fromisoformat(next_run)
        return dt.astimezone().date() == datetime.now().astimezone().date()
    except Exception:
        return False


def _get_today_reminders() -> list:
    """Recordatorios programados cuya próxima ejecución es hoy."""
    try:
        from core.memory import db_get_active_tasks
        tasks = db_get_active_tasks()
        return [
            t for t in tasks
            if t.get("task_type") == "reminder" and _is_today(t.get("next_run", ""))
        ]
    except Exception as e:
        logging.warning(f"[Briefing] No se pudieron leer los recordatorios: {e}")
        return []


def generate_morning_briefing() -> str:
    """Genera el texto del briefing matutino, listo para voz o Telegram."""
    from core.startup import _get_greeting_by_time

    parts = [f"{_get_greeting_by_time()}, señor. Aquí tiene su briefing matutino."]

    today = datetime.now().strftime("%A %d de %B").capitalize()
    parts.append(f"Hoy es {today}.")

    weather = _get_weather()
    if weather:
        parts.append(weather)

    pending = _get_pending_changes()
    if pending > 0:
        parts.append(
            f"Tiene {pending} archivo{'s' if pending != 1 else ''} con cambios sin "
            f"confirmar en el repositorio."
        )
    else:
        parts.append("El repositorio está limpio, sin cambios pendientes.")

    reminders = _get_today_reminders()
    if reminders:
        parts.append(f"Tiene {len(reminders)} recordatorio{'s' if len(reminders) != 1 else ''} para hoy:")
        for r in reminders[:5]:
            parts.append(f"  - {r.get('target', r.get('name', ''))}")
    else:
        parts.append("No tiene recordatorios programados para hoy.")

    parts.append("Que tenga un día productivo, señor.")
    return "\n".join(parts)
