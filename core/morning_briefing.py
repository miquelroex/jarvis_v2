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
import threading
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


def _send_to_telegram(text: str) -> bool:
    """Envía el briefing por Telegram si el bot está configurado. Best-effort."""
    try:
        import telebot
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_USER_ID")
        if not token or not chat_id or not token.strip() or not chat_id.strip():
            return False
        telebot.TeleBot(token).send_message(chat_id.strip(), f"☀️ {text}")
        return True
    except Exception as e:
        logging.warning(f"[Briefing] No se pudo enviar por Telegram: {e}")
        return False


def deliver_briefing(channel: str = None, briefing: str = None) -> dict:
    """Genera (si hace falta) y entrega el briefing por los canales configurados.

    channel: 'voice' | 'telegram' | 'both' (def. JARVIS_MORNING_CHANNEL o 'both').
    """
    if briefing is None:
        briefing = generate_morning_briefing()
    channel = (channel or os.getenv("JARVIS_MORNING_CHANNEL", "both")).lower()
    results = {"voice": False, "telegram": False}

    if channel in ("voice", "both"):
        try:
            from tools.voice import speak
            speak(briefing, disable_vad=True)
            results["voice"] = True
        except Exception as e:
            logging.warning(f"[Briefing] No se pudo entregar por voz: {e}")

    if channel in ("telegram", "both"):
        results["telegram"] = _send_to_telegram(briefing)

    logging.info(f"[Briefing] Briefing entregado: {results}")
    return results


# --- Daemon programado ---
BRIEFING_THREAD = None
stop_event = threading.Event()
_last_briefing_date = None


def _briefing_loop():
    """Bucle del daemon: entrega el briefing una vez al día a la hora objetivo."""
    global _last_briefing_date
    # Reutiliza la comprobación de "toca entregar" del resumen diario.
    from core.daily_digest import _should_deliver_now
    if stop_event.wait(timeout=20):
        return
    while not stop_event.is_set():
        try:
            now = datetime.now()
            target_hour = int(os.getenv("JARVIS_MORNING_BRIEFING_HOUR", "8"))
            if _should_deliver_now(now, target_hour, _last_briefing_date):
                deliver_briefing()
                _last_briefing_date = now.date()
        except Exception as e:
            logging.error(f"[Briefing] Error en el bucle del daemon: {e}")
        check_interval = int(os.getenv("JARVIS_MORNING_CHECK_INTERVAL", "300"))
        if stop_event.wait(timeout=check_interval):
            break


def start_morning_briefing_daemon():
    """Lanza el daemon del briefing matutino. Idempotente. Controlado por
    JARVIS_MORNING_BRIEFING_ENABLED (desactivado por defecto)."""
    global BRIEFING_THREAD
    if os.getenv("JARVIS_MORNING_BRIEFING_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Briefing] Desactivado en .env.")
        return
    if BRIEFING_THREAD is not None and BRIEFING_THREAD.is_alive():
        logging.info("[Briefing] Ya está en ejecución.")
        return
    stop_event.clear()
    BRIEFING_THREAD = threading.Thread(target=_briefing_loop, name="MorningBriefingDaemon", daemon=True)
    BRIEFING_THREAD.start()
    logging.info("[Briefing] Daemon del briefing matutino iniciado en segundo plano.")


def stop_morning_briefing_daemon():
    """Detiene el daemon del briefing matutino de forma limpia."""
    logging.info("[Briefing] Deteniendo daemon del briefing matutino...")
    stop_event.set()
