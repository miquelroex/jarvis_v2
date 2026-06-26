"""
core/prodigal.py — Protocolo "Hijo Pródigo".

Cuando vuelves tras una ausencia, Jarvis te pone al día como un mayordomo:
commits nuevos en el repositorio, cambios sin confirmar, dispositivos en la red,
notas pendientes y nivel de amenaza — todo desde tu último "check-in".

El montaje del texto es puro y testeable; los lectores reales (git, red, inbox,
amenaza) se aíslan y son best-effort.
"""
import os
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAST_CHECKIN_FILE = Path("logs/prodigal_last_checkin.txt")
DEFAULT_LOOKBACK_HOURS = 8


def _now() -> datetime:
    return datetime.now()


def _read_last_checkin(default_hours: int = DEFAULT_LOOKBACK_HOURS) -> datetime:
    """Última vez que se pidió el parte (o hace `default_hours` si no hay)."""
    if LAST_CHECKIN_FILE.exists():
        try:
            return datetime.fromisoformat(LAST_CHECKIN_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            pass
    return _now() - timedelta(hours=default_hours)


def _write_checkin(ts: datetime):
    try:
        LAST_CHECKIN_FILE.parent.mkdir(exist_ok=True)
        LAST_CHECKIN_FILE.write_text(ts.isoformat(), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[Prodigal] No se pudo guardar el check-in: {e}")


def _count_new_commits(since: datetime) -> int:
    """Commits desde una fecha (solo lectura)."""
    try:
        res = subprocess.run(
            ["git", "log", f"--since={since.isoformat()}", "--oneline"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
        )
        if res.returncode != 0:
            return 0
        return len([line for line in res.stdout.splitlines() if line.strip()])
    except Exception as e:
        logger.warning(f"[Prodigal] No se pudo contar commits: {e}")
        return 0


def _get_git_state() -> dict:
    try:
        from core.project_awareness import get_active_project
        return get_active_project()
    except Exception:
        return {"is_repo": False, "branch": "", "dirty_count": 0, "last_commit": ""}


def _get_devices_count() -> int:
    try:
        path = PROJECT_ROOT / "logs" / "last_network_scan.json"
        if not path.exists():
            return 0
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("devices", data.get("hosts", []))
        return len(data) if isinstance(data, list) else 0
    except Exception:
        return 0


def _get_pending_count() -> int:
    try:
        from core.inbox import get_inbox_items
        items = get_inbox_items()
        return len([i for i in items if not i.get("done")])
    except Exception:
        return 0


def _get_threat_level() -> str:
    try:
        from core.threat_level import compute_threat_level
        return compute_threat_level().get("level", "green")
    except Exception:
        return "green"


def _fmt_absence(minutes: int) -> str:
    minutes = max(0, int(minutes))
    if minutes < 60:
        return f"{minutes} minuto{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    rem = minutes % 60
    if hours < 24:
        base = f"{hours} hora{'s' if hours != 1 else ''}"
        return base + (f" y {rem} minutos" if rem else "")
    days = hours // 24
    return f"{days} día{'s' if days != 1 else ''}"


_THREAT_ES = {"green": "verde", "amber": "ámbar", "red": "rojo", "violet": "violeta"}


def build_welcome_back(ctx: dict) -> str:
    """Monta el parte de bienvenida a partir del contexto (puro)."""
    parts = [f"Bienvenido de nuevo, señor. En su ausencia de {_fmt_absence(ctx.get('absence_minutes', 0))}:"]

    commits = ctx.get("new_commits", 0)
    if commits:
        branch = ctx.get("branch") or "el repositorio"
        parts.append(f"se han registrado {commits} commit{'s' if commits != 1 else ''} nuevo{'s' if commits != 1 else ''} en {branch}.")

    dirty = ctx.get("dirty_count", 0)
    if dirty:
        parts.append(f"El repositorio tiene {dirty} archivo{'s' if dirty != 1 else ''} con cambios sin confirmar.")

    devices = ctx.get("devices_count", 0)
    if devices:
        parts.append(f"Detecto {devices} dispositivo{'s' if devices != 1 else ''} en la red.")

    pending = ctx.get("pending_count", 0)
    if pending:
        parts.append(f"Tiene {pending} nota{'s' if pending != 1 else ''} pendiente{'s' if pending != 1 else ''} en la bandeja.")

    threat = ctx.get("threat_level", "green")
    if threat and threat != "green":
        parts.append(f"Atención: el nivel de amenaza está en {_THREAT_ES.get(threat, threat)}.")

    if len(parts) == 1:
        parts.append("sin novedades reseñables. Todo en orden.")

    parts.append("A su servicio.")
    return " ".join(parts)


def get_catchup(update: bool = True) -> str:
    """Ensambla el parte del Hijo Pródigo desde el último check-in."""
    now = _now()
    since = _read_last_checkin()
    git = _get_git_state()
    ctx = {
        "absence_minutes": int((now - since).total_seconds() // 60),
        "new_commits": _count_new_commits(since),
        "dirty_count": git.get("dirty_count", 0) if git.get("is_repo") else 0,
        "branch": git.get("branch", ""),
        "devices_count": _get_devices_count(),
        "pending_count": _get_pending_count(),
        "threat_level": _get_threat_level(),
    }
    if update:
        _write_checkin(now)
    return build_welcome_back(ctx)


def deliver_catchup() -> str:
    """Genera el parte y lo locuta (best-effort). Devuelve el texto."""
    text = get_catchup()
    try:
        from tools.voice import speak
        speak(text, disable_vad=True)
    except Exception as e:
        logger.warning(f"[Prodigal] No se pudo locutar el parte: {e}")
    return text