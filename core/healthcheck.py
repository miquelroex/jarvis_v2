"""
core/healthcheck.py — Healthcheck de arranque de Jarvis.

Genera un resumen de estado agregando comprobaciones ligeras y seguras:
  - tools cargadas correctamente / tools que fallaron (sin reimportar)
  - servicios activos / detenidos / desactivados
  - claves API presentes o ausentes (sin exponer sus valores)
  - estado de SQLite / memoria
  - estado general: healthy | degraded | error

Garantías de diseño (Fase 1):
  * NO reimporta ni recarga las tools (lee el reporte ya calculado por agent_manager).
  * NO ejecuta la suite de tests.
  * NO vuelca valores de claves API (solo un booleano de presencia).
  * Este módulo no está conectado todavía al arranque ni a la GUI.
"""
import os
import json
import sqlite3
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Tablas que deben existir en la base de datos de memoria para considerarla sana.
_EXPECTED_TABLES = {"memories", "scheduled_tasks"}

# Ruta por defecto donde se persiste el último reporte de arranque.
DEFAULT_REPORT_PATH = os.path.join("logs", "startup_health.json")


def _check_tools() -> dict:
    """Estado de carga de las tools, sin reimportar: lee el reporte de agent_manager."""
    try:
        from core.agent_manager import get_tools_load_report
        report = get_tools_load_report()
        return {
            "loaded": report.get("loaded", 0),
            "failed": report.get("failed", []),
        }
    except Exception as e:
        logger.warning(f"[Healthcheck] No se pudo obtener el reporte de tools: {e}")
        return {"loaded": 0, "failed": [], "error": str(e)}


def _check_services() -> dict:
    """Estado de cada servicio de segundo plano: running | stopped | disabled."""
    try:
        from core.services import get_services_status
        return get_services_status()
    except Exception as e:
        logger.warning(f"[Healthcheck] No se pudo obtener el estado de servicios: {e}")
        return {}


def _check_api_keys() -> list:
    """Presencia de claves API, SIN exponer valores.

    Reutiliza check_env_variables(), que devuelve únicamente
    [{"name", "configured": bool}] — nunca el valor de la clave.
    """
    try:
        from core.jarvis_integrity import check_env_variables
        return check_env_variables()
    except Exception as e:
        logger.warning(f"[Healthcheck] No se pudieron verificar las claves API: {e}")
        return []


def _check_database() -> dict:
    """Comprueba que SQLite es accesible y que existen las tablas esperadas.

    No lee contenido de las tablas, solo consulta el esquema (sqlite_master).
    """
    result = {"ok": False, "path": None, "tables": [], "error": None}
    try:
        from core.memory import get_db_path, init_db

        init_db()  # idempotente: CREATE TABLE IF NOT EXISTS
        db_path = get_db_path()
        result["path"] = db_path

        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = sorted(row[0] for row in cursor.fetchall())
        finally:
            conn.close()

        result["tables"] = tables
        if _EXPECTED_TABLES.issubset(set(tables)):
            result["ok"] = True
        else:
            missing = _EXPECTED_TABLES - set(tables)
            result["error"] = f"Faltan tablas esperadas: {', '.join(sorted(missing))}"
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)
        logger.error(f"[Healthcheck] Error al comprobar la base de datos: {e}")
    return result


def _aggregate_status(tools_report: dict, services: dict, database: dict) -> str:
    """Calcula el estado global a partir de las secciones.

    Reglas:
      - 'error'    si SQLite no es accesible (dependencia crítica del núcleo).
      - 'degraded' si hay alguna tool fallida o algún servicio 'stopped'.
                   Los servicios 'disabled' (por configuración) NO degradan.
      - 'healthy'  en cualquier otro caso.
    """
    if not database.get("ok", False):
        return "error"

    if tools_report.get("failed"):
        return "degraded"

    if any(state == "stopped" for state in services.values()):
        return "degraded"

    return "healthy"


def run_healthcheck() -> dict:
    """Ejecuta el healthcheck de arranque y devuelve un resumen agregado.

    No reimporta tools, no ejecuta la suite de tests y no expone valores de claves.

    Returns:
        dict con claves: status, timestamp, tools, services, api_keys, database.
    """
    tools_report = _check_tools()
    services = _check_services()
    api_keys = _check_api_keys()
    database = _check_database()

    status = _aggregate_status(tools_report, services, database)

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tools": tools_report,
        "services": services,
        "api_keys": api_keys,
        "database": database,
    }


def summarize_healthcheck(report: dict) -> str:
    """Resumen de una sola línea del reporte, pensado para logging.

    No expone valores de claves: solo cuenta cuántas están presentes.
    """
    status = report.get("status", "unknown")

    tools = report.get("tools", {})
    loaded = tools.get("loaded", 0)
    failed = len(tools.get("failed", []))

    services = report.get("services", {})
    running = sum(1 for s in services.values() if s == "running")
    stopped = sum(1 for s in services.values() if s == "stopped")
    disabled = sum(1 for s in services.values() if s == "disabled")

    keys = report.get("api_keys", [])
    keys_ok = sum(1 for k in keys if k.get("configured"))

    db_ok = report.get("database", {}).get("ok", False)

    return (
        f"status={status} | tools={loaded} ok/{failed} fallidas | "
        f"servicios={running} activos/{stopped} detenidos/{disabled} desactivados | "
        f"api_keys={keys_ok}/{len(keys)} presentes | sqlite={'ok' if db_ok else 'ERROR'}"
    )


def persist_healthcheck(report: dict, path: str = DEFAULT_REPORT_PATH) -> bool:
    """Persiste el reporte a un fichero JSON (crea el directorio si hace falta).

    Returns:
        bool: True si se escribió correctamente, False en caso de error.
    """
    try:
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"[Healthcheck] No se pudo persistir el reporte en {path}: {e}")
        return False
