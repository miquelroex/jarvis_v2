"""
core/anticipation.py — Anticipación ("Me he tomado la libertad…").

Jarvis aprende tus patrones de uso registrando acciones (apps/ventanas/comandos)
con su contexto temporal (hora y día de la semana). Cuando el contexto actual se
parece a momentos pasados, predice qué sueles hacer y se adelanta sugiriéndolo.

El registro se guarda en logs/anticipation_log.jsonl. El motor de predicción es
una función pura y testeable que opera sobre una lista de eventos.
"""
import os
import json
import logging
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_FILE = Path("logs/anticipation_log.jsonl")
_lock = threading.Lock()

ANTICIPATE_THREAD = None
stop_event = threading.Event()
_delivered = {}  # acción -> fecha del último aviso (1 por día y acción)


def _context(ts: datetime):
    """(hora, día_semana) de un timestamp (puro)."""
    return ts.hour, ts.weekday()


def record_action(action: str, ts=None):
    """Registra una acción con su contexto temporal (best-effort)."""
    if not action or not action.strip():
        return
    ts = ts or datetime.now()
    hour, weekday = _context(ts)
    rec = {"action": action.strip(), "hour": hour, "weekday": weekday, "ts": ts.isoformat()}
    try:
        with _lock:
            LOG_FILE.parent.mkdir(exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[Anticipation] No se pudo registrar la acción: {e}")


def _hour_distance(a: int, b: int) -> int:
    """Distancia circular entre dos horas (0-12)."""
    d = abs(a - b) % 24
    return min(d, 24 - d)


def predict(events, now: datetime, top_k: int = 3, min_score: int = 3,
            hour_window: int = 1, recent_exclude=None):
    """Predice las acciones más probables para el contexto de `now` (puro).

    events: lista de {action, hour, weekday}. Pondera coincidencia de día de la
    semana (x2) y cercanía horaria (±hour_window). Excluye acciones recientes."""
    hour, weekday = _context(now)
    recent = set(recent_exclude or [])
    scores = Counter()
    for e in events or []:
        eh = e.get("hour")
        if eh is None:
            continue
        if _hour_distance(eh, hour) > hour_window:
            continue
        action = e.get("action")
        if not action or action in recent:
            continue
        weight = 2 if e.get("weekday") == weekday else 1
        scores[action] += weight
    ranked = [
        {"action": a, "score": s}
        for a, s in scores.most_common()
        if s >= min_score
    ]
    return ranked[:top_k]


def _load_events(limit: int = 5000):
    if not LOG_FILE.exists():
        return []
    events = []
    try:
        with _lock:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"[Anticipation] No se pudo leer el registro: {e}")
    return events


def _recent_actions(events, now: datetime, within_hours: int = 1):
    """Acciones realizadas en las últimas `within_hours` horas (para no repetir)."""
    recent = set()
    for e in events:
        ts = e.get("ts")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            continue
        if 0 <= (now - dt).total_seconds() <= within_hours * 3600:
            recent.add(e.get("action"))
    return recent


def get_suggestions(now=None, top_k: int = 3):
    """Sugerencias de anticipación para el momento actual."""
    now = now or datetime.now()
    events = _load_events()
    recent = _recent_actions(events, now)
    return predict(events, now, top_k=top_k, recent_exclude=recent)


def _phrase(action: str) -> str:
    """Frase natural a partir de una acción registrada (p.ej. 'app:code' -> 'abrir code')."""
    if ":" in action:
        kind, name = action.split(":", 1)
        if kind in ("app", "window"):
            return f"abrir {name}"
        if kind == "web":
            return f"abrir {name}"
    return action


def _anticipate_loop():
    if stop_event.wait(timeout=60):
        return
    while not stop_event.is_set():
        try:
            now = datetime.now()
            sugg = get_suggestions(now, top_k=1)
            if sugg:
                top = sugg[0]
                if _delivered.get(top["action"]) != now.date():
                    _delivered[top["action"]] = now.date()
                    _deliver(top)
        except Exception as e:
            logger.error(f"[Anticipation] Error en el bucle del daemon: {e}")
        interval = int(os.getenv("JARVIS_ANTICIPATION_INTERVAL", "1800"))
        if stop_event.wait(timeout=interval):
            break


def _deliver(suggestion: dict):
    phrase = _phrase(suggestion["action"])
    msg = f"Señor, a esta hora suele {phrase}. Me he tomado la libertad de tenerlo a mano."
    try:
        from tools.voice import speak
        speak(msg, disable_vad=True)
    except Exception:
        pass
    import sys
    mod = sys.modules.get("gui.app")
    if mod is not None:
        try:
            mod.socketio.emit("anticipation_suggestion",
                              {"action": suggestion["action"], "phrase": phrase, "message": msg})
        except Exception:
            pass


def start_anticipation_daemon():
    """Lanza el daemon de anticipación. Idempotente. Off por defecto
    (JARVIS_ANTICIPATION_ENABLED) porque interrumpe con voz."""
    global ANTICIPATE_THREAD
    if os.getenv("JARVIS_ANTICIPATION_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Anticipation] Desactivado en .env.")
        return
    if ANTICIPATE_THREAD is not None and ANTICIPATE_THREAD.is_alive():
        return
    stop_event.clear()
    ANTICIPATE_THREAD = threading.Thread(target=_anticipate_loop, name="AnticipationDaemon", daemon=True)
    ANTICIPATE_THREAD.start()
    logging.info("[Anticipation] Daemon de anticipación iniciado.")


def stop_anticipation_daemon():
    """Detiene el daemon de anticipación."""
    stop_event.set()
