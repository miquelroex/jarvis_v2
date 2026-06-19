"""
Resumen nocturno de Jarvis (Daily Digest) — MVP.

Genera un resumen del día en texto natural, listo para leerse por voz (TTS)
o enviarse por Telegram. No requiere APIs externas: solo git local, la base
de datos de memoria/tareas y el estado de los servicios.

Secciones:
  1. Commits de git del día (si el directorio es un repo y hubo actividad).
  2. Recordatorios y tareas programadas activas.
  3. Recuerdos guardados hoy (notas de la memoria de Jarvis).
  4. Estado básico de los servicios de Jarvis.
  5. Próximos pasos (próximas ejecuciones programadas).
"""
import os
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _get_today_commits(repo_dir: Path = None) -> list:
    """Retorna los mensajes de commit de hoy (lista de strings). Solo lectura."""
    repo = str(repo_dir or PROJECT_ROOT)
    try:
        res = subprocess.run(
            ["git", "log", "--since=midnight", "--pretty=format:%h %s"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode != 0:
            return []
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception as e:
        logging.warning(f"[DailyDigest] No se pudo leer git log: {e}")
        return []


def _get_active_tasks() -> list:
    """Tareas programadas activas (recordatorios y monitores) desde SQLite."""
    try:
        from core.memory import db_get_active_tasks
        return db_get_active_tasks()
    except Exception as e:
        logging.warning(f"[DailyDigest] No se pudieron leer tareas: {e}")
        return []


def _get_today_memories() -> list:
    """Recuerdos guardados hoy en la memoria de Jarvis."""
    try:
        from core.memory import get_all_memories
        today = datetime.now().strftime("%Y-%m-%d")
        return [m for m in get_all_memories(limit=50)
                if str(m.get("created_at", "")).startswith(today)]
    except Exception as e:
        logging.warning(f"[DailyDigest] No se pudieron leer recuerdos: {e}")
        return []


def _get_services_summary() -> str:
    """Resumen compacto del estado de servicios: 'X activos, Y detenidos'."""
    try:
        from core.services import get_services_status
        status = get_services_status()
        running = sum(1 for v in status.values() if v == "running")
        stopped = [k for k, v in status.items() if v == "stopped"]
        summary = f"{running} servicios activos"
        if stopped:
            summary += f"; detenidos: {', '.join(stopped)}"
        return summary
    except Exception as e:
        logging.warning(f"[DailyDigest] No se pudo leer estado de servicios: {e}")
        return "estado de servicios no disponible"


def _format_next_run(task: dict) -> str:
    """Formatea la próxima ejecución de una tarea de forma legible."""
    next_run = task.get("next_run")
    if not next_run:
        return ""
    try:
        dt = datetime.fromisoformat(next_run)
        local = dt.astimezone()
        return local.strftime("%H:%M del %d/%m")
    except Exception:
        return str(next_run)


def generate_daily_digest(repo_dir: Path = None) -> str:
    """Genera el texto completo del resumen nocturno."""
    parts = []
    today_str = datetime.now().strftime("%A %d de %B").capitalize()
    parts.append(f"Resumen del día, señor ({today_str}).")

    # 1. Git
    commits = _get_today_commits(repo_dir)
    if commits:
        parts.append(f"Hoy ha realizado {len(commits)} commits:")
        for c in commits[:10]:
            parts.append(f"  - {c}")
        if len(commits) > 10:
            parts.append(f"  ... y {len(commits) - 10} más.")
    else:
        parts.append("Hoy no se han registrado commits en el repositorio.")

    # 2. Tareas y recordatorios activos
    tasks = _get_active_tasks()
    reminders = [t for t in tasks if t.get("task_type") == "reminder"]
    monitors = [t for t in tasks if t.get("task_type") == "url_monitor"]
    if reminders:
        parts.append(f"Tiene {len(reminders)} recordatorios activos:")
        for r in reminders[:5]:
            when = _format_next_run(r)
            target = r.get("target", r.get("name", ""))
            parts.append(f"  - {target}" + (f" (próximo: {when})" if when else ""))
    else:
        parts.append("No hay recordatorios pendientes.")
    if monitors:
        parts.append(f"Hay {len(monitors)} monitores de URL en marcha.")

    # 3. Notas/recuerdos de hoy
    memories = _get_today_memories()
    if memories:
        parts.append(f"Hoy ha guardado {len(memories)} notas en mi memoria:")
        for m in memories[:5]:
            parts.append(f"  - {m.get('content', '')}")

    # 4. Estado de Jarvis
    parts.append(f"Estado de los sistemas: {_get_services_summary()}.")

    # 5. Próximos pasos
    upcoming = sorted(
        [t for t in tasks if t.get("next_run")],
        key=lambda t: t.get("next_run") or ""
    )
    if upcoming:
        nxt = upcoming[0]
        when = _format_next_run(nxt)
        parts.append(f"Próximo paso programado: '{nxt.get('name', '')}' a las {when}.")
    else:
        parts.append("No hay próximos pasos programados. Puede dictarme nuevos recordatorios cuando guste.")

    return "\n".join(parts)


def send_digest_to_telegram(digest: str = None) -> bool:
    """Envía el resumen por Telegram si el bot está configurado. Best-effort."""
    if digest is None:
        digest = generate_daily_digest()
    try:
        import telebot
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_USER_ID")
        if not token or not chat_id or not token.strip() or not chat_id.strip():
            return False
        bot = telebot.TeleBot(token)
        bot.send_message(chat_id.strip(), f"🌙 {digest}")
        return True
    except Exception as e:
        logging.warning(f"[DailyDigest] No se pudo enviar por Telegram: {e}")
        return False
