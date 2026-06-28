"""
core/wellbeing.py — Lectura de estado/ánimo del usuario ("¿cómo le veo, señor?").

Jarvis estima tu nivel de tensión/fatiga cruzando señales que ya recopila —la
hora, los errores recientes, cuánto llevas trabajando sin pausa y si los tests
están en rojo— y ajusta su trato: te felicita cuando vas fino y, cuando detecta
agotamiento, te sugiere parar con tacto. *"Señor, lleva tres horas con el mismo
bug y son las 2 de la mañana. Sugiero una pausa."*

El cálculo del nivel y las frases son funciones PURAS y testeables; la
recolección de señales (error_kb, idle, test watcher) y el daemon se aíslan.
Complementa el Protocolo Blackout (que sólo mira la hora) con una lectura
multi-señal. Off por defecto la parte proactiva; la consulta "¿cómo estoy?"
funciona siempre.
"""
import os
import time
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

WELLBEING_THREAD = None
stop_event = threading.Event()
_last_advice = 0.0
_work_start = None  # marca de inicio de actividad continua (se reinicia tras un descanso)


# ----------------------------------------------------------------------------
# Núcleo puro
# ----------------------------------------------------------------------------
def compute_stress(signals: dict) -> int:
    """Puntuación de tensión 0-100 a partir de las señales (puro)."""
    score = 0
    hour = signals.get("hour")
    if hour is not None and (hour >= 23 or hour <= 5):
        score += 25
    errors = signals.get("recent_errors", 0) or 0
    score += min(40, errors * 12)
    work = signals.get("work_minutes", 0) or 0
    if work >= 150:
        score += 30
    elif work >= 90:
        score += 15
    if signals.get("tests_failing"):
        score += 15
    return max(0, min(100, score))


def stress_level(score: int) -> str:
    """Etiqueta de estado a partir de la puntuación (puro)."""
    if score < 25:
        return "sereno"
    if score < 50:
        return "concentrado"
    if score < 75:
        return "tenso"
    return "agotado"


def advice_for(level: str) -> str:
    """Frase de Jarvis según el nivel (puro)."""
    return {
        "sereno": "Todo en orden, señor. Le veo sereno.",
        "concentrado": "Le veo concentrado, señor. Buen ritmo.",
        "tenso": "Le noto algo tenso, señor. ¿Le vendría bien una pausa breve?",
        "agotado": ("Señor, da señales de agotamiento. Le recomiendo "
                    "encarecidamente parar y descansar un poco."),
    }.get(level, "")


def should_intervene(level: str) -> bool:
    """¿El nivel amerita una intervención proactiva? (puro)."""
    return level in ("tenso", "agotado")


def build_status_report(signals: dict) -> str:
    """Informe hablado del estado, con los factores que pesan (puro)."""
    level = stress_level(compute_stress(signals))
    factores = []
    hour = signals.get("hour")
    if hour is not None and (hour >= 23 or hour <= 5):
        factores.append("la hora")
    if (signals.get("recent_errors", 0) or 0) >= 2:
        factores.append("los errores recientes")
    if (signals.get("work_minutes", 0) or 0) >= 90:
        factores.append("el rato sin pausa")
    if signals.get("tests_failing"):
        factores.append("los tests en rojo")
    base = advice_for(level)
    if factores and level in ("tenso", "agotado"):
        base += " Pesa " + ", ".join(factores) + "."
    return base


# ----------------------------------------------------------------------------
# Recolección de señales (aislada)
# ----------------------------------------------------------------------------
def _recent_error_count(window_min: int = 15) -> int:
    """Errores cuyo last_seen cae en los últimos `window_min` minutos."""
    try:
        from core.error_kb import _load
        store = _load()
        now = datetime.now()
        n = 0
        for e in store.values():
            ls = e.get("last_seen")
            if not ls:
                continue
            try:
                dt = datetime.fromisoformat(ls)
            except Exception:
                continue
            if 0 <= (now - dt).total_seconds() <= window_min * 60:
                n += 1
        return n
    except Exception:
        return 0


def _tests_failing() -> bool:
    try:
        from core.test_watcher import get_watcher_status
        last = get_watcher_status().get("last_run", {})
        return last.get("last_run_time") is not None and last.get("last_success") is False
    except Exception:
        return False


def _work_minutes(idle_break: int = 300) -> int:
    """Minutos de actividad continua; se reinicia tras un periodo de inactividad."""
    global _work_start
    now = time.time()
    try:
        from core.productivity import _idle_seconds
        idle = _idle_seconds()
    except Exception:
        idle = 0
    if idle >= idle_break or _work_start is None:
        _work_start = now
    return int((now - _work_start) / 60)


def _gather_signals() -> dict:
    now = datetime.now()
    return {
        "hour": now.hour,
        "recent_errors": _recent_error_count(),
        "work_minutes": _work_minutes(),
        "tests_failing": _tests_failing(),
    }


def get_status_report() -> str:
    """Lectura de estado bajo demanda ("¿cómo estoy?")."""
    return build_status_report(_gather_signals())


# ----------------------------------------------------------------------------
# Entrega y daemon (aislado)
# ----------------------------------------------------------------------------
def _deliver(message: str):
    try:
        from core.narration import narrate
        narrate(message, speak=os.getenv("JARVIS_WELLBEING_VOICE", "true").lower()
                in ("true", "1", "yes"), tone="calm")
    except Exception:
        pass


def run_once():
    """Evalúa el estado y, si procede, interviene (con enfriamiento)."""
    global _last_advice
    signals = _gather_signals()
    level = stress_level(compute_stress(signals))
    if not should_intervene(level):
        return
    cooldown = float(os.getenv("JARVIS_WELLBEING_COOLDOWN", "3600"))
    if time.time() - _last_advice < cooldown:
        return
    _last_advice = time.time()
    _deliver(build_status_report(signals))


def _wellbeing_loop():
    if stop_event.wait(timeout=60):
        return
    while not stop_event.is_set():
        try:
            run_once()
        except Exception as e:
            logger.error(f"[Wellbeing] Error en el bucle: {e}")
        interval = int(os.getenv("JARVIS_WELLBEING_INTERVAL", "600"))
        if stop_event.wait(timeout=interval):
            break


def start_wellbeing_daemon():
    """Lanza la lectura proactiva de estado. Off por defecto
    (JARVIS_WELLBEING_ENABLED) porque interrumpe con sugerencias."""
    global WELLBEING_THREAD
    if os.getenv("JARVIS_WELLBEING_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Wellbeing] Desactivado en .env.")
        return
    if WELLBEING_THREAD is not None and WELLBEING_THREAD.is_alive():
        return
    stop_event.clear()
    WELLBEING_THREAD = threading.Thread(target=_wellbeing_loop, name="WellbeingDaemon", daemon=True)
    WELLBEING_THREAD.start()
    logging.info("[Wellbeing] Lectura de estado iniciada.")


def stop_wellbeing_daemon():
    """Detiene la lectura de estado."""
    stop_event.set()
