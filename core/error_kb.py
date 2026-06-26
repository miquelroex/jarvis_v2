"""
core/error_kb.py — Base de conocimiento de errores recurrentes.

Jarvis recuerda los errores/tracebacks que te encuentras y la solución que se
aplicó. Cuando un error reaparece, te dice cuántas veces lo has visto y cómo se
resolvió la última vez. Memoria de depuración, todo local.

La "firma" del error (normalización a un identificador estable, ignorando rutas,
números y direcciones) es pura y testeable; el almacenamiento se aísla.
"""
import re
import json
import logging
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

KB_FILE = Path("logs/error_kb.json")
_lock = threading.Lock()


def error_signature(text: str) -> str:
    """Normaliza un error/traceback a una firma estable (puro)."""
    if not text or not text.strip():
        return ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Buscar la línea de excepción (TypeError/ValueError/...); si no, la última.
    exc_line = ""
    for l in reversed(lines):
        if re.match(r"^[A-Za-z_][\w.]*(Error|Exception|Warning|Fault)\b", l):
            exc_line = l
            break
    if not exc_line:
        exc_line = lines[-1] if lines else text.strip()

    sig = exc_line
    sig = re.sub(r"0x[0-9a-fA-F]+", "0x", sig)                  # direcciones hex
    sig = re.sub(r"[A-Za-z]:\\[^\s'\"]+|/[^\s'\"]+", "PATH", sig)  # rutas
    sig = re.sub(r"'[^']*'", "'X'", sig)                          # literales
    sig = re.sub(r'"[^"]*"', '"X"', sig)
    sig = re.sub(r"\b\d+\b", "N", sig)                            # números
    sig = re.sub(r"\s+", " ", sig).strip().lower()
    return sig


def _load() -> dict:
    if not KB_FILE.exists():
        return {}
    try:
        return json.loads(KB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(store: dict):
    try:
        KB_FILE.parent.mkdir(parents=True, exist_ok=True)
        KB_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[ErrorKB] No se pudo guardar la base de errores: {e}")


def _representative(text: str) -> str:
    """Línea representativa del error para mostrar (la de la excepción)."""
    for l in reversed([x.strip() for x in (text or "").splitlines() if x.strip()]):
        if re.match(r"^[A-Za-z_][\w.]*(Error|Exception|Warning|Fault)\b", l):
            return l[:200]
    stripped = (text or "").strip()
    return stripped.splitlines()[-1][:200] if stripped else ""


def record_error(error_text: str, solution: str = None) -> str:
    """Registra (o incrementa) un error. Devuelve su firma."""
    sig = error_signature(error_text)
    if not sig:
        return ""
    now = datetime.now().isoformat()
    with _lock:
        store = _load()
        entry = store.get(sig)
        if entry is None:
            entry = {"error": _representative(error_text), "solution": solution,
                     "count": 0, "first_seen": now, "last_seen": now}
            store[sig] = entry
        entry["count"] += 1
        entry["last_seen"] = now
        if solution:
            entry["solution"] = solution.strip()
        _save(store)
    return sig


def record_solution(error_text: str, solution: str) -> bool:
    """Asocia una solución a la firma de un error (si existe o creándola)."""
    if not solution or not solution.strip():
        return False
    sig = error_signature(error_text)
    if not sig:
        return False
    now = datetime.now().isoformat()
    with _lock:
        store = _load()
        entry = store.setdefault(sig, {"error": _representative(error_text), "count": 0,
                                        "first_seen": now, "last_seen": now})
        entry["solution"] = solution.strip()
        _save(store)
    return True


def lookup(error_text: str):
    """Devuelve la entrada de un error o None."""
    sig = error_signature(error_text)
    if not sig:
        return None
    with _lock:
        return _load().get(sig)


def recall(error_text: str) -> str:
    """Texto para Jarvis si el error ya se vio antes y tiene solución ("" si no)."""
    entry = lookup(error_text)
    if not entry or not entry.get("solution"):
        return ""
    count = entry.get("count", 0)
    veces = "una vez" if count == 1 else f"{count} veces"
    return (f"Señor, ya se ha encontrado este error {veces}. "
            f"La última vez se resolvió así: {entry['solution']}")


def get_summary(top_n: int = 5) -> str:
    """Resumen de los errores más recurrentes (puro respecto al store cargado)."""
    with _lock:
        store = _load()
    if not store:
        return "No tengo errores registrados aún, señor."
    items = sorted(store.values(), key=lambda e: e.get("count", 0), reverse=True)[:top_n]
    parts = [
        f"{e.get('count', 0)}× {e.get('error', '')[:50]}" + (" (con solución)" if e.get("solution") else "")
        for e in items
    ]
    return "Errores más recurrentes, señor: " + "; ".join(parts) + "."
