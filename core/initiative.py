"""
core/initiative.py — Iniciativa Ejecutora (Proactividad con criterio).

Sobre el Cerebro de Estado Central (world_model), Jarvis compara el estado del
mundo entre sondeos, RAZONA sobre los cambios significativos y, según una
política de confianza configurable, o bien te avisa, o bien actúa por su cuenta
en lo de bajo riesgo: "Me he tomado la libertad de liberar memoria, señor".

Niveles de autonomía (JARVIS_INITIATIVE_LEVEL):
  - off    : no hace nada (por defecto).
  - notify : sólo avisa de los cambios; nunca ejecuta nada.
  - act    : además ejecuta automáticamente las acciones de bajo riesgo (SAFE)
             y te lo comunica; lo arriesgado siempre lo consulta, nunca lo hace.

La detección de iniciativas y la política de respuesta son funciones PURAS y
testeables sobre dos snapshots del modelo de mundo; la ejecución de acciones, la
voz/HUD y el daemon de sondeo se aíslan. Barandillas: sólo se autoejecutan
acciones marcadas SAFE y registradas explícitamente; nada destructivo.
"""
import os
import time
import logging
import threading

logger = logging.getLogger(__name__)

# Niveles de riesgo de una iniciativa.
RISK_INFO = "info"    # sólo informar
RISK_SAFE = "safe"    # autoejecutable en modo 'act'
RISK_RISKY = "risky"  # siempre consultar, nunca autoejecutar

_THREAT_RANK = {"green": 0, "amber": 1, "red": 2, "violet": 3}

INITIATIVE_THREAD = None
stop_event = threading.Event()
_prev_state = None
_last_fired = {}  # id de iniciativa -> timestamp del último disparo (cooldown)


# ----------------------------------------------------------------------------
# Lectores seguros (puro)
# ----------------------------------------------------------------------------
def _ram(s):
    try:
        return float((s.get("system", {}) or {}).get("ram") or 0)
    except (TypeError, ValueError):
        return 0.0


def _threat_rank(s):
    level = ((s.get("threat", {}) or {}).get("level") or "green").lower()
    return _THREAT_RANK.get(level, 0)


def _unknown(s):
    return (s.get("network", {}) or {}).get("unknown") or 0


def _running(s):
    return (s.get("services", {}) or {}).get("running") or 0


def _dirty(s):
    return (s.get("project", {}) or {}).get("dirty_count") or 0


# ----------------------------------------------------------------------------
# Detección de iniciativas (puro)
# ----------------------------------------------------------------------------
def detect_initiatives(prev: dict, curr: dict, dirty_threshold: int = 25):
    """Iniciativas derivadas de la transición prev -> curr del mundo. Puro.

    Devuelve [{id, message, risk, action?}]. Sin prev (primer sondeo) no dispara
    nada: necesita una línea base para detectar CAMBIOS."""
    if not prev or not curr:
        return []
    out = []

    # RAM cruza a crítica: avisar y (en 'act') liberar memoria.
    if _ram(curr) >= 90 and _ram(prev) < 90:
        out.append({
            "id": "ram_critical",
            "risk": RISK_SAFE,
            "action": "free_memory",
            "message": f"Señor, la RAM acaba de alcanzar el {_ram(curr):.0f}%. Conviene actuar.",
        })

    # Escalada del nivel de amenaza.
    if _threat_rank(curr) > _threat_rank(prev) and _threat_rank(curr) >= 1:
        level = ((curr.get("threat", {}) or {}).get("level") or "").upper()
        reasons = ", ".join((curr.get("threat", {}) or {}).get("reasons", [])[:2])
        msg = f"Señor, el nivel de amenaza ha subido a {level}."
        if reasons:
            msg += f" Motivo: {reasons}."
        out.append({"id": "threat_up", "risk": RISK_INFO, "message": msg})

    # Nuevo dispositivo desconocido en la red.
    if _unknown(curr) > _unknown(prev):
        out.append({
            "id": "net_intruder",
            "risk": RISK_INFO,
            "message": "Señor, detecto un dispositivo desconocido en la red.",
        })

    # Un servicio se ha caído (hay menos activos que antes).
    if _running(curr) < _running(prev):
        out.append({
            "id": "service_down",
            "risk": RISK_INFO,
            "message": "Señor, uno de los servicios se ha detenido inesperadamente.",
        })

    # Demasiados cambios sin confirmar: sugerir commit.
    if _dirty(curr) >= dirty_threshold and _dirty(prev) < dirty_threshold:
        out.append({
            "id": "dirty_commit",
            "risk": RISK_INFO,
            "message": (f"Señor, acumula {_dirty(curr)} cambios sin confirmar. "
                        "Quizá sea buen momento para un commit."),
        })

    return out


def decide_response(initiative: dict, level: str) -> str:
    """Política de confianza: qué hacer con una iniciativa. Puro.

    Devuelve 'execute' | 'announce' | 'ask' | 'skip'."""
    lvl = (level or "off").lower()
    if lvl not in ("notify", "act"):
        return "skip"
    risk = initiative.get("risk", RISK_INFO)
    if lvl == "notify":
        return "announce"
    # lvl == "act"
    if risk == RISK_SAFE and initiative.get("action"):
        return "execute"
    if risk == RISK_RISKY:
        return "ask"
    return "announce"


def format_action_announcement(initiative: dict, result: str = "") -> str:
    """Frase tras ejecutar una acción por iniciativa propia (puro)."""
    base = f"Me he tomado la libertad de resolverlo, señor. {initiative.get('message', '')}"
    if result:
        base += f" {result}"
    return base.strip()


# ----------------------------------------------------------------------------
# Acciones seguras (aislado, registro explícito)
# ----------------------------------------------------------------------------
def _action_free_memory() -> str:
    import gc
    collected = gc.collect()
    try:
        from core.drones import launch_drone
        launch_drone("limpieza")
    except Exception:
        pass
    return f"He liberado memoria (recolectados {collected} objetos) y lanzado una limpieza."


SAFE_ACTIONS = {
    "free_memory": _action_free_memory,
}


# ----------------------------------------------------------------------------
# Entrega y ejecución (aislado)
# ----------------------------------------------------------------------------
def _announce(message: str):
    try:
        from core.narration import narrate
        narrate(message, speak=os.getenv("JARVIS_INITIATIVE_VOICE", "false").lower()
                in ("true", "1", "yes"), tone="alert")
    except Exception:
        pass


def _execute(initiative: dict):
    action = SAFE_ACTIONS.get(initiative.get("action"))
    result = ""
    if action:
        try:
            result = action() or ""
        except Exception as e:
            logger.warning(f"[Initiative] Falló la acción {initiative.get('action')}: {e}")
            result = ""
    _announce(format_action_announcement(initiative, result))


def _cooldown_ok(initiative_id: str, now: float, cooldown: float) -> bool:
    last = _last_fired.get(initiative_id, 0)
    if now - last < cooldown:
        return False
    _last_fired[initiative_id] = now
    return True


def run_once(level: str = None):
    """Un ciclo: sondea el mundo, detecta iniciativas y responde según la política."""
    global _prev_state
    level = level or os.getenv("JARVIS_INITIATIVE_LEVEL", "off")
    from core.world_model import snapshot
    curr = snapshot()
    inits = detect_initiatives(_prev_state, curr)
    _prev_state = curr
    cooldown = float(os.getenv("JARVIS_INITIATIVE_COOLDOWN", "600"))
    now = time.time()
    for init in inits:
        resp = decide_response(init, level)
        if resp == "skip":
            continue
        if not _cooldown_ok(init["id"], now, cooldown):
            continue
        if resp == "execute":
            _execute(init)
        else:  # announce / ask
            suffix = " ¿Desea que intervenga?" if resp == "ask" else ""
            _announce(init["message"] + suffix)


def _initiative_loop():
    if stop_event.wait(timeout=30):
        return
    while not stop_event.is_set():
        try:
            run_once()
        except Exception as e:
            logger.error(f"[Initiative] Error en el bucle del daemon: {e}")
        interval = int(os.getenv("JARVIS_INITIATIVE_INTERVAL", "60"))
        if stop_event.wait(timeout=interval):
            break


def start_initiative_daemon():
    """Lanza el daemon de iniciativa. Idempotente. Off por defecto
    (JARVIS_INITIATIVE_LEVEL=off): no actúa salvo que lo pongas en notify/act."""
    global INITIATIVE_THREAD
    if os.getenv("JARVIS_INITIATIVE_LEVEL", "off").lower() not in ("notify", "act"):
        logging.info("[Initiative] Desactivado (JARVIS_INITIATIVE_LEVEL=off).")
        return
    if INITIATIVE_THREAD is not None and INITIATIVE_THREAD.is_alive():
        return
    stop_event.clear()
    INITIATIVE_THREAD = threading.Thread(target=_initiative_loop, name="InitiativeDaemon", daemon=True)
    INITIATIVE_THREAD.start()
    logging.info("[Initiative] Daemon de iniciativa ejecutora iniciado.")


def stop_initiative_daemon():
    """Detiene el daemon de iniciativa."""
    stop_event.set()
