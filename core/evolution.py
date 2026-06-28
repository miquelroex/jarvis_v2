"""
core/evolution.py — Motor de Evolución (aprendizaje continuo de Jarvis).

Jarvis aprende de su PROPIA operación: cruza la telemetría de sus herramientas
(core/tool_armor), los errores que reinciden (core/error_kb) y su uso, y saca
LECCIONES que acumula en un diario, evolucionando con el tiempo. *"He aprendido
que la herramienta X es poco fiable, señor; y que el error Y merece una
auto-mejora."* Es la meta-capa que decide QUÉ mejorar; la ejecución de la mejora
es el Protocolo Mark II (core/mark_ii).

La evaluación de lecciones, la deduplicación contra el diario y el formato son
funciones PURAS y testeables; la recolección de señales y el diario en disco se
aíslan.
"""
import os
import json
import time
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

JOURNAL_FILE = Path("logs/evolution_journal.jsonl")
_lock = threading.Lock()

EVOLUTION_THREAD = None
stop_event = threading.Event()


# ----------------------------------------------------------------------------
# Evaluación de lecciones (pura)
# ----------------------------------------------------------------------------
def assess_evolution(tool_rows, error_items, error_threshold: int = 4):
    """Lecciones aprendidas de la operación de Jarvis. Puro.

    tool_rows: filas de tool_armor.summarize_stats ({name, calls, fail_rate, state}).
    error_items: valores de error_kb ({error, count, solution})."""
    lessons = []
    for r in tool_rows or []:
        name = r.get("name", "?")
        if r.get("state") == "open":
            lessons.append({
                "kind": "tool", "priority": 3,
                "text": (f"La herramienta {name} falla sistemáticamente "
                         "(circuito abierto); conviene un fallback o revisarla."),
            })
        elif r.get("fail_rate", 0) >= 0.3 and r.get("calls", 0) >= 3:
            pct = int(r["fail_rate"] * 100)
            lessons.append({
                "kind": "tool", "priority": 2,
                "text": f"La herramienta {name} es poco fiable: falla el {pct}% de las veces.",
            })
        elif r.get("calls", 0) >= 5 and r.get("fail_rate", 0) == 0:
            lessons.append({
                "kind": "strength", "priority": 1,
                "text": f"Domino bien {name}: {r['calls']} usos sin un solo fallo.",
            })

    for e in error_items or []:
        count = e.get("count", 0)
        if count < error_threshold:
            continue
        label = (e.get("error") or "").strip()[:60] or "un error recurrente"
        if e.get("solution"):
            lessons.append({
                "kind": "error", "priority": 1,
                "text": f"El error «{label}» reincide ({count}×), pero ya sé resolverlo.",
            })
        else:
            lessons.append({
                "kind": "error", "priority": 3,
                "text": (f"El error «{label}» reincide ({count}×) sin solución fija; "
                         "candidato a auto-mejora (Mark II)."),
            })

    lessons.sort(key=lambda l: l["priority"], reverse=True)
    return lessons


def new_lessons(journal_texts, lessons):
    """Lecciones que aún no están en el diario (puro)."""
    seen = set(journal_texts or [])
    return [l for l in (lessons or []) if l["text"] not in seen]


def format_evolution_report(lessons) -> str:
    """Informe hablado de las lecciones (puro)."""
    if not lessons:
        return "No he extraído lecciones nuevas, señor. Sigo aprendiendo."
    partes = [l["text"] for l in lessons[:6]]
    return "Esto es lo que he aprendido, señor: " + " ".join(partes)


def format_learnings(journal, top_k: int = 8) -> str:
    """Resumen del diario de aprendizaje acumulado (puro)."""
    if not journal:
        return "Aún no he acumulado aprendizajes, señor. Deme algo de rodaje."
    recientes = sorted(journal, key=lambda e: e.get("ts", 0), reverse=True)[:top_k]
    return (f"He acumulado {len(journal)} lecciones, señor. Las más recientes: "
            + " ".join(e["text"] for e in recientes))


# ----------------------------------------------------------------------------
# Recolección y diario (aislado)
# ----------------------------------------------------------------------------
def _tool_rows():
    try:
        from core.tool_armor import summarize_stats, get_stats
        return summarize_stats(get_stats())
    except Exception as e:
        logger.debug(f"[Evolution] Sin telemetría de herramientas: {e}")
        return []


def _error_items():
    try:
        from core.error_kb import _load
        return list(_load().values())
    except Exception as e:
        logger.debug(f"[Evolution] Sin base de errores: {e}")
        return []


def _load_journal():
    if not JOURNAL_FILE.exists():
        return []
    out = []
    try:
        with _lock:
            lines = JOURNAL_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"[Evolution] No se pudo leer el diario: {e}")
    return out


def _append_journal(lessons, ts: float = None):
    ts = ts if ts is not None else time.time()
    try:
        with _lock:
            JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
                for l in lessons:
                    f.write(json.dumps({"text": l["text"], "kind": l["kind"], "ts": ts},
                                       ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[Evolution] No se pudo guardar el diario: {e}")


def learn_now() -> str:
    """Evalúa la operación, registra las lecciones nuevas y las devuelve."""
    lessons = assess_evolution(_tool_rows(), _error_items())
    journal = _load_journal()
    fresh = new_lessons({e.get("text") for e in journal}, lessons)
    if fresh:
        _append_journal(fresh)
    return format_evolution_report(fresh)


def get_learnings() -> str:
    """Recuento del aprendizaje acumulado ("¿qué has aprendido?")."""
    return format_learnings(_load_journal())


# ----------------------------------------------------------------------------
# Daemon (aprendizaje continuo, silencioso)
# ----------------------------------------------------------------------------
def _evolution_loop():
    if stop_event.wait(timeout=120):
        return
    while not stop_event.is_set():
        try:
            learn_now()  # registra en el diario sin interrumpir
        except Exception as e:
            logger.error(f"[Evolution] Error en el bucle: {e}")
        interval = int(os.getenv("JARVIS_EVOLUTION_INTERVAL", "3600"))
        if stop_event.wait(timeout=interval):
            break


def start_evolution_daemon():
    """Lanza el aprendizaje continuo en segundo plano. Off por defecto
    (JARVIS_EVOLUTION_ENABLED). La consulta "¿qué has aprendido?" funciona siempre."""
    global EVOLUTION_THREAD
    if os.getenv("JARVIS_EVOLUTION_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Evolution] Aprendizaje continuo desactivado en .env.")
        return
    if EVOLUTION_THREAD is not None and EVOLUTION_THREAD.is_alive():
        return
    stop_event.clear()
    EVOLUTION_THREAD = threading.Thread(target=_evolution_loop, name="EvolutionDaemon", daemon=True)
    EVOLUTION_THREAD.start()
    logging.info("[Evolution] Aprendizaje continuo iniciado.")


def stop_evolution_daemon():
    """Detiene el aprendizaje continuo."""
    stop_event.set()
