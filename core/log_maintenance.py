"""
Mantenimiento de logs y archivos temporales de Jarvis (Self-Maintenance).

Limpia de forma segura:
  - logs/audio_temp/      -> audios TTS temporales antiguos.
  - logs/backup/          -> copias .bak antiguas o cuando exceden un tamaño total.
  - logs/model_usage.log  -> rotación cuando supera un tamaño máximo.
  - Archivos transitorios -> temp_run.*, plot.png, last_exception.json antiguos.

NUNCA toca archivos operativos (locks, pending actions, estado de sentinels,
historiales o la base de datos de memoria). Ver OPERATIONAL_FILES.

Variables de entorno:
  JARVIS_LOG_MAINTENANCE_ENABLED   (default: true)
  JARVIS_LOG_MAINTENANCE_INTERVAL  segundos entre pasadas (default: 21600 = 6h)
  JARVIS_AUDIO_TEMP_MAX_AGE_HOURS  (default: 24)
  JARVIS_BACKUP_RETENTION_DAYS     (default: 30)
  JARVIS_BACKUP_MAX_MB             tamaño total máximo de logs/backup (default: 200)
  JARVIS_LOG_RETENTION_DAYS        edad máxima de archivos transitorios (default: 14)
  JARVIS_LOG_MAX_MB                tamaño máximo de model_usage.log (default: 10)
"""
import os
import time
import logging
import threading
from pathlib import Path

# Archivos operativos que el mantenimiento tiene PROHIBIDO tocar.
OPERATIONAL_FILES = {
    "jarvis.lock",
    "pending_action.json",
    "pending_model_request.json",
    "pending_terminal_command.json",
    "known_devices.json",
    "last_network_scan.json",
    "jarvis_health.json",
    "active_plan.json",
    "vulnerability_report.json",
    "job_offers.json",
    "terminal_history.json",
    "socratic_mode.txt",
    "latest_screenshot.png",
    "peer_review.html",
}

# Archivos transitorios que sí pueden eliminarse si son antiguos.
TRANSIENT_FILES = {
    "temp_run.py",
    "temp_run.php",
    "temp_run.bat",
    "plot.png",
    "last_exception.json",
}

MAINTENANCE_THREAD = None
stop_event = threading.Event()


def _get_logs_dir(base_dir=None) -> Path:
    if base_dir is not None:
        return Path(base_dir)
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "logs"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _is_older_than(path: Path, max_age_seconds: float, now: float = None) -> bool:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    now = now if now is not None else time.time()
    return (now - mtime) > max_age_seconds


def _safe_unlink(path: Path) -> bool:
    """Elimina un archivo de forma segura. Nunca elimina operativos ni directorios."""
    try:
        if path.name in OPERATIONAL_FILES or not path.is_file():
            return False
        path.unlink()
        return True
    except OSError as e:
        logging.warning(f"[LogMaintenance] No se pudo eliminar {path.name}: {e}")
        return False


def cleanup_audio_temp(logs_dir: Path, now: float = None) -> int:
    """Elimina audios temporales más antiguos que JARVIS_AUDIO_TEMP_MAX_AGE_HOURS."""
    audio_dir = logs_dir / "audio_temp"
    if not audio_dir.is_dir():
        return 0
    max_age = _env_int("JARVIS_AUDIO_TEMP_MAX_AGE_HOURS", 24) * 3600
    removed = 0
    for f in audio_dir.iterdir():
        if f.is_file() and _is_older_than(f, max_age, now):
            if _safe_unlink(f):
                removed += 1
    return removed


def cleanup_backups(logs_dir: Path, now: float = None) -> int:
    """Elimina backups antiguos y aplica un límite de tamaño total a logs/backup.

    1. Borra archivos con más de JARVIS_BACKUP_RETENTION_DAYS días.
    2. Si el tamaño total sigue superando JARVIS_BACKUP_MAX_MB, borra los más
       antiguos primero hasta volver al límite (conservando siempre el más reciente).
    """
    backup_dir = logs_dir / "backup"
    if not backup_dir.is_dir():
        return 0

    retention = _env_int("JARVIS_BACKUP_RETENTION_DAYS", 30) * 86400
    max_bytes = _env_int("JARVIS_BACKUP_MAX_MB", 200) * 1024 * 1024
    removed = 0

    files = [f for f in backup_dir.iterdir() if f.is_file()]

    # 1. Limpieza por edad
    for f in list(files):
        if _is_older_than(f, retention, now):
            if _safe_unlink(f):
                files.remove(f)
                removed += 1

    # 2. Límite por tamaño total (borrar más antiguos primero, conservar el último)
    try:
        files.sort(key=lambda f: f.stat().st_mtime)
        total = sum(f.stat().st_size for f in files)
        while total > max_bytes and len(files) > 1:
            oldest = files.pop(0)
            size = oldest.stat().st_size
            if _safe_unlink(oldest):
                total -= size
                removed += 1
            else:
                break
    except OSError as e:
        logging.warning(f"[LogMaintenance] Error aplicando límite de tamaño a backups: {e}")

    return removed


def rotate_model_usage_log(logs_dir: Path) -> bool:
    """Rota logs/model_usage.log si supera JARVIS_LOG_MAX_MB.

    El archivo actual pasa a model_usage.log.1 (sobrescribiendo la rotación
    anterior), de modo que siempre se conserva el historial reciente.
    """
    log_file = logs_dir / "model_usage.log"
    if not log_file.is_file():
        return False
    max_bytes = _env_int("JARVIS_LOG_MAX_MB", 10) * 1024 * 1024
    try:
        if log_file.stat().st_size <= max_bytes:
            return False
        rotated = logs_dir / "model_usage.log.1"
        if rotated.exists():
            rotated.unlink()
        log_file.rename(rotated)
        logging.info("[LogMaintenance] model_usage.log rotado a model_usage.log.1")
        return True
    except OSError as e:
        logging.warning(f"[LogMaintenance] Error al rotar model_usage.log: {e}")
        return False


def cleanup_transient_files(logs_dir: Path, now: float = None) -> int:
    """Elimina archivos transitorios conocidos con más de JARVIS_LOG_RETENTION_DAYS días."""
    retention = _env_int("JARVIS_LOG_RETENTION_DAYS", 14) * 86400
    removed = 0
    for name in TRANSIENT_FILES:
        f = logs_dir / name
        if f.is_file() and _is_older_than(f, retention, now):
            if _safe_unlink(f):
                removed += 1
    return removed


def run_log_maintenance(base_dir=None, now: float = None) -> dict:
    """Ejecuta una pasada completa de mantenimiento. Retorna un resumen."""
    logs_dir = _get_logs_dir(base_dir)
    summary = {
        "audio_temp_removed": 0,
        "backups_removed": 0,
        "transient_removed": 0,
        "model_log_rotated": False,
    }
    if not logs_dir.is_dir():
        return summary

    summary["audio_temp_removed"] = cleanup_audio_temp(logs_dir, now)
    summary["backups_removed"] = cleanup_backups(logs_dir, now)
    summary["transient_removed"] = cleanup_transient_files(logs_dir, now)
    summary["model_log_rotated"] = rotate_model_usage_log(logs_dir)

    total = (summary["audio_temp_removed"] + summary["backups_removed"]
             + summary["transient_removed"])
    if total or summary["model_log_rotated"]:
        logging.info(f"[LogMaintenance] Limpieza completada: {summary}")
    return summary


def _maintenance_loop():
    while not stop_event.is_set():
        try:
            run_log_maintenance()
        except Exception as e:
            logging.error(f"[LogMaintenance] Error en pasada de mantenimiento: {e}")
        interval = _env_int("JARVIS_LOG_MAINTENANCE_INTERVAL", 21600)
        if stop_event.wait(timeout=max(interval, 60)):
            break


def start_log_maintenance() -> bool:
    """Arranca el daemon de mantenimiento (idempotente)."""
    global MAINTENANCE_THREAD
    enabled = os.getenv("JARVIS_LOG_MAINTENANCE_ENABLED", "true").lower() in ("true", "1", "yes")
    if not enabled:
        logging.info("[LogMaintenance] Desactivado por configuración.")
        return False
    if MAINTENANCE_THREAD is not None and MAINTENANCE_THREAD.is_alive():
        return True
    stop_event.clear()
    MAINTENANCE_THREAD = threading.Thread(
        target=_maintenance_loop, name="LogMaintenanceThread", daemon=True
    )
    MAINTENANCE_THREAD.start()
    return True


def stop_log_maintenance() -> None:
    """Detiene el daemon de mantenimiento de forma limpia."""
    global MAINTENANCE_THREAD
    stop_event.set()
    if MAINTENANCE_THREAD is not None and MAINTENANCE_THREAD.is_alive():
        MAINTENANCE_THREAD.join(timeout=5)
    MAINTENANCE_THREAD = None
