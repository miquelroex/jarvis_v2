"""
core/dependency_health.py — Auditoría proactiva de salud de dependencias.

A diferencia del vulnerability_patcher (que busca vulnerabilidades de SEGURIDAD
vía OSV), este módulo evalúa la SALUD/MANTENIMIENTO de las dependencias:
  - "outdated": la versión instalada está por detrás de la última publicada.
  - "stale" / posiblemente abandonada: el paquete no publica un release desde
    hace más de N días (umbral configurable).

Consulta los metadatos públicos de PyPI. Módulo ligero (stdlib + packaging):
no importa langchain ni tools, por lo que es testeable de forma aislada.

Fase 1: solo lógica y persistencia. Aún no conectado a daemon/servicios/GUI.
"""
import os
import json
import logging
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
REPORT_FILE = Path("logs/dependency_health.json")

# Días sin un nuevo release para considerar un paquete "stale" / posiblemente
# abandonado. Por defecto ~18 meses. Configurable por entorno.
STALE_DAYS = int(os.getenv("JARVIS_DEP_STALE_DAYS", "540"))


def parse_requirements(req_path: Path = None) -> list:
    """Lee requirements.txt y devuelve [{"name", "version"}] de los pines exactos (==)."""
    req_path = Path(req_path) if req_path else REQUIREMENTS_FILE
    deps = []
    if not req_path.exists():
        return deps
    try:
        for line in req_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            if "==" in line:
                name, _, rest = line.partition("==")
                version = rest.split(";")[0].split("#")[0].strip()
                deps.append({"name": name.strip(), "version": version})
    except Exception as e:
        logger.error(f"[DepHealth] Error al leer requirements.txt: {e}")
    return deps


def _is_outdated(current: str, latest: str) -> bool:
    """True si la versión instalada está por detrás de la última publicada."""
    if not latest or not current:
        return False
    try:
        from packaging.version import parse as parse_version
        return parse_version(current) < parse_version(latest)
    except Exception:
        # Fallback conservador si packaging no puede parsear las versiones.
        return current != latest


def _fetch_pypi_metadata(name: str) -> dict:
    """Descarga los metadatos JSON de un paquete desde PyPI. None si falla."""
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        with urllib.request.urlopen(url, timeout=6) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"[DepHealth] No se pudo consultar PyPI para {name}: {e}")
        return None


def _latest_release_date(meta: dict):
    """Fecha (datetime UTC) del release más reciente publicado en PyPI, o None."""
    latest = None
    releases = meta.get("releases", {}) or {}
    for files in releases.values():
        for f in (files or []):
            ts = f.get("upload_time_iso_8601") or f.get("upload_time")
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if latest is None or dt > latest:
                latest = dt
    return latest


def analyze_dependency(dep: dict, now: datetime = None) -> dict:
    """Analiza una dependencia: outdated y stale. Consulta PyPI."""
    now = now or datetime.now(timezone.utc)
    name = dep["name"]
    current = dep["version"]
    result = {
        "name": name, "current": current, "latest": None,
        "outdated": False, "stale": False,
        "last_release": None, "days_since_release": None, "error": None,
    }

    meta = _fetch_pypi_metadata(name)
    if meta is None:
        result["error"] = "no se pudo consultar PyPI"
        return result

    latest = meta.get("info", {}).get("version") or ""
    result["latest"] = latest
    result["outdated"] = _is_outdated(current, latest)

    last_dt = _latest_release_date(meta)
    if last_dt is not None:
        result["last_release"] = last_dt.date().isoformat()
        days = (now - last_dt).days
        result["days_since_release"] = days
        result["stale"] = days > STALE_DAYS

    return result


def run_dependency_health_check() -> dict:
    """Audita todas las dependencias de requirements.txt y devuelve un reporte agregado.

    Estado: 'advisory' si hay paquetes outdated o stale; 'healthy' en caso contrario.
    """
    deps = parse_requirements()
    now = datetime.now(timezone.utc)
    results = [analyze_dependency(d, now) for d in deps]

    outdated = [
        {"name": r["name"], "current": r["current"], "latest": r["latest"]}
        for r in results if r["outdated"]
    ]
    stale = [
        {"name": r["name"], "last_release": r["last_release"],
         "days_since_release": r["days_since_release"]}
        for r in results if r["stale"]
    ]
    errors = [r["name"] for r in results if r["error"]]

    status = "advisory" if (outdated or stale) else "healthy"
    return {
        "status": status,
        "last_scan": now.isoformat(),
        "total": len(deps),
        "checked": len([r for r in results if r["error"] is None]),
        "outdated": outdated,
        "stale": stale,
        "errors": errors,
    }


def persist_report(report: dict, path: Path = None) -> bool:
    """Persiste el reporte a un fichero JSON. Devuelve True si tuvo éxito."""
    path = Path(path) if path else REPORT_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.error(f"[DepHealth] Error al persistir el reporte en {path}: {e}")
        return False


# --- Daemon periódico ---
HEALTH_THREAD = None
stop_event = threading.Event()
LAST_STATUS = "unknown"


def run_and_report() -> dict:
    """Ejecuta la auditoría, persiste el reporte, lo emite a la GUI y avisa por voz
    de forma proactiva SOLO en la transición a 'advisory' (para no resultar pesado)."""
    global LAST_STATUS
    report = run_dependency_health_check()
    persist_report(report)

    # Emitir a la GUI (best-effort)
    try:
        from gui.app import socketio
        socketio.emit("dependency_health_update", report)
    except Exception:
        pass

    # Aviso proactivo por voz solo al pasar de no-advisory a advisory
    try:
        if report["status"] == "advisory" and LAST_STATUS != "advisory":
            n_out = len(report["outdated"])
            n_stale = len(report["stale"])
            from tools.voice import speak
            speak(
                f"Señor, informe de dependencias: {n_out} desactualizadas y "
                f"{n_stale} sin mantenimiento reciente. Le sugiero revisarlas.",
                disable_vad=True,
            )
    except Exception:
        pass

    LAST_STATUS = report["status"]
    return report


def _health_loop():
    """Bucle periódico del daemon de salud de dependencias."""
    # Espera inicial para no interferir con el arranque.
    if stop_event.wait(timeout=30):
        return
    while not stop_event.is_set():
        try:
            run_and_report()
        except Exception as e:
            logger.error(f"[DepHealth] Error en el bucle periódico: {e}")
        interval = int(os.getenv("JARVIS_DEP_HEALTH_INTERVAL", "86400"))  # diario por defecto
        if stop_event.wait(timeout=interval):
            break


def start_dependency_health_daemon():
    """Lanza el daemon de auditoría de dependencias. Idempotente. Controlado por
    JARVIS_DEP_HEALTH_ENABLED (desactivado por defecto, es una tarea de red)."""
    global HEALTH_THREAD
    if os.getenv("JARVIS_DEP_HEALTH_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logger.info("[DepHealth] Desactivado en .env.")
        return
    if HEALTH_THREAD is not None and HEALTH_THREAD.is_alive():
        logger.info("[DepHealth] Ya está en ejecución.")
        return
    stop_event.clear()
    HEALTH_THREAD = threading.Thread(target=_health_loop, name="DependencyHealthDaemon", daemon=True)
    HEALTH_THREAD.start()
    logger.info("[DepHealth] Daemon de salud de dependencias iniciado en segundo plano.")


def stop_dependency_health_daemon():
    """Detiene el daemon de salud de dependencias de forma limpia."""
    logger.info("[DepHealth] Deteniendo daemon de salud de dependencias...")
    stop_event.set()
