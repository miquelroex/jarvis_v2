"""
core/insights.py — "Señor, detecto un patrón".

Insight proactivo. Jarvis cruza tus hábitos registrados (las acciones del motor
de anticipación, con su contexto temporal) y la base de errores recurrentes, y
cuando encuentra algo estadísticamente significativo lo comenta con un toque
Stark, sin que se lo pidas. Ejemplo: "Señor, observo que suele compilar sobre
todo los lunes. ¿Casualidad?".

Los detectores son funciones PURAS y testeables que operan sobre una lista de
eventos {action, hour, weekday, ts} (y, para errores, sobre el store de
error_kb). El daemon entrega como mucho un insight nuevo al día (voz opcional,
off por defecto; HUD siempre).
"""
import os
import sys
import json
import logging
import threading
from datetime import datetime
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

INSIGHT_THREAD = None
stop_event = threading.Event()
_delivered = {}  # texto del insight -> fecha de entrega (1 por día y patrón)


# ----------------------------------------------------------------------------
# Utilidades de fraseo (puras)
# ----------------------------------------------------------------------------
def _phrase(action: str) -> str:
    """Frase natural a partir de una acción registrada (p.ej. 'app:code' -> 'abrir code')."""
    if not action:
        return ""
    if ":" in action:
        kind, name = action.split(":", 1)
        if kind in ("app", "window", "web"):
            return f"abrir {name}"
    return action


def _part_of_day(hour: int) -> str:
    """Franja del día para una hora (puro)."""
    if 5 <= hour < 12:
        return "por las mañanas"
    if 12 <= hour < 14:
        return "al mediodía"
    if 14 <= hour < 20:
        return "por las tardes"
    if 20 <= hour < 24:
        return "por las noches"
    return "de madrugada"


# ----------------------------------------------------------------------------
# Detectores (puros)
# ----------------------------------------------------------------------------
def detect_weekday_patterns(events, min_count: int = 4, dominance: float = 0.5):
    """Acciones que se concentran en un día de la semana concreto.

    Para cada acción con al menos `min_count` registros, si un único día acumula
    una fracción >= `dominance` de ellos, emite un insight. Puro."""
    by_action = defaultdict(Counter)
    for e in events or []:
        action = e.get("action")
        wd = e.get("weekday")
        if not action or wd is None or not (0 <= wd <= 6):
            continue
        by_action[action][wd] += 1
    insights = []
    for action, hist in by_action.items():
        total = sum(hist.values())
        if total < min_count:
            continue
        top_wd, top_n = hist.most_common(1)[0]
        if top_n / total >= dominance:
            phrase = _phrase(action)
            insights.append({
                "kind": "weekday",
                "score": top_n,
                "text": (f"Señor, observo que suele {phrase} sobre todo los "
                         f"{WEEKDAY_NAMES[top_wd]} ({top_n} de {total} veces). ¿Casualidad?"),
            })
    return insights


def detect_hour_patterns(events, min_total: int = 12, dominance: float = 0.3):
    """Franja horaria dominante de tu actividad global. Puro."""
    hist = Counter()
    for e in events or []:
        h = e.get("hour")
        if h is None or not (0 <= h <= 23):
            continue
        hist[h] += 1
    total = sum(hist.values())
    if total < min_total:
        return []
    top_hour, top_n = hist.most_common(1)[0]
    if top_n / total < dominance:
        return []
    return [{
        "kind": "hour",
        "score": top_n,
        "text": (f"Señor, su pico de actividad es alrededor de las {top_hour:02d}:00 "
                 f"{_part_of_day(top_hour)}. Tendré sus herramientas a punto."),
    }]


def detect_sequence_patterns(events, min_count: int = 3, top_k: int = 2):
    """Pares de acciones consecutivas A->B recurrentes (candidatos a rutina). Puro."""
    actions = [e.get("action") for e in (events or []) if e.get("action")]
    pairs = Counter()
    for a, b in zip(actions, actions[1:]):
        if a == b:
            continue
        pairs[(a, b)] += 1
    insights = []
    for (a, b), count in pairs.most_common():
        if count < min_count:
            break
        insights.append({
            "kind": "sequence",
            "score": count * 2,  # accionable: merece prioridad
            "text": (f"Señor, detecto un patrón: tras {_phrase(a)} casi siempre "
                     f"{_phrase(b)} ({count} veces). ¿Le preparo una rutina?"),
        })
        if len(insights) >= top_k:
            break
    return insights


def detect_error_patterns(error_store, min_count: int = 3, top_k: int = 2):
    """Errores que reaparecen con insistencia, a partir del store de error_kb. Puro."""
    if not error_store:
        return []
    items = sorted(error_store.values(), key=lambda e: e.get("count", 0), reverse=True)
    insights = []
    for e in items:
        count = e.get("count", 0)
        if count < min_count:
            break
        label = (e.get("error") or "").strip()[:60] or "un error recurrente"
        solved = " y ya sabemos cómo resolverlo" if e.get("solution") else ", aún sin solución fija"
        insights.append({
            "kind": "error",
            "score": count,
            "text": (f"Señor, este error ya ha reaparecido {count} veces{solved}: "
                     f"\"{label}\". Quizá merezca una mirada de raíz."),
        })
        if len(insights) >= top_k:
            break
    return insights


def build_insights(events, error_store=None, now=None, top_k: int = 3):
    """Combina todos los detectores y devuelve los insights más significativos. Puro."""
    insights = []
    insights += detect_sequence_patterns(events)
    insights += detect_weekday_patterns(events)
    insights += detect_hour_patterns(events)
    insights += detect_error_patterns(error_store)
    # Dedupe por texto preservando el de mayor score.
    best = {}
    for ins in insights:
        cur = best.get(ins["text"])
        if cur is None or ins["score"] > cur["score"]:
            best[ins["text"]] = ins
    ranked = sorted(best.values(), key=lambda i: i["score"], reverse=True)
    return ranked[:top_k]


def format_for_voice(insights) -> str:
    """Texto hablado a partir de una lista de insights ("" si no hay)."""
    if not insights:
        return ""
    return " ".join(i["text"] for i in insights)


# ----------------------------------------------------------------------------
# Carga de datos (aislada)
# ----------------------------------------------------------------------------
def _load_events():
    try:
        from core.anticipation import _load_events as _ant_load
        return _ant_load()
    except Exception as e:
        logger.warning(f"[Insights] No se pudieron cargar los hábitos: {e}")
        return []


def _load_error_store():
    try:
        from core.error_kb import _load
        return _load()
    except Exception as e:
        logger.warning(f"[Insights] No se pudo cargar la base de errores: {e}")
        return {}


def get_insights(now=None, top_k: int = 3):
    """Insights significativos para el momento actual (datos reales del disco)."""
    now = now or datetime.now()
    return build_insights(_load_events(), _load_error_store(), now=now, top_k=top_k)


def get_insights_report() -> str:
    """Texto listo para voz/HUD con los insights actuales (o aviso si no hay)."""
    insights = get_insights()
    if not insights:
        return ("Señor, aún no dispongo de suficientes hábitos registrados para "
                "detectar patrones. Déjeme observarle un poco más.")
    return format_for_voice(insights)


# ----------------------------------------------------------------------------
# Entrega proactiva (daemon)
# ----------------------------------------------------------------------------
def _emit_gui(insight: dict):
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        mod.socketio.emit("insight_detected",
                          {"kind": insight["kind"], "text": insight["text"]})
    except Exception:
        pass


def _deliver(insight: dict):
    _emit_gui(insight)
    if os.getenv("JARVIS_INSIGHTS_VOICE", "false").lower() in ("true", "1", "yes"):
        try:
            from tools.voice import speak
            speak(insight["text"], disable_vad=True)
        except Exception:
            pass


def _insight_loop():
    if stop_event.wait(timeout=90):
        return
    while not stop_event.is_set():
        try:
            now = datetime.now()
            insights = get_insights(now, top_k=1)
            if insights:
                top = insights[0]
                if _delivered.get(top["text"]) != now.date():
                    _delivered[top["text"]] = now.date()
                    _deliver(top)
        except Exception as e:
            logger.error(f"[Insights] Error en el bucle del daemon: {e}")
        interval = int(os.getenv("JARVIS_INSIGHTS_INTERVAL", "3600"))
        if stop_event.wait(timeout=interval):
            break


def start_insights_daemon():
    """Lanza el daemon de insights. Idempotente. Off por defecto
    (JARVIS_INSIGHTS_ENABLED) porque interrumpe proactivamente."""
    global INSIGHT_THREAD
    if os.getenv("JARVIS_INSIGHTS_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Insights] Desactivado en .env.")
        return
    if INSIGHT_THREAD is not None and INSIGHT_THREAD.is_alive():
        return
    stop_event.clear()
    INSIGHT_THREAD = threading.Thread(target=_insight_loop, name="InsightsDaemon", daemon=True)
    INSIGHT_THREAD.start()
    logging.info("[Insights] Daemon de insights iniciado.")


def stop_insights_daemon():
    """Detiene el daemon de insights."""
    stop_event.set()
