"""
core/world_model.py — Cerebro de Estado Central (Modelo de Mundo).

Unifica el estado vivo de todos los dominios de Jarvis (sistema, servicios,
amenaza, proyecto activo, productividad, red, vigilancias, uso de IA) en un
único objeto sobre el que Jarvis puede razonar de forma GLOBAL, en vez de
consultar cada servicio por separado.

Es la columna vertebral del asistente: el snapshot se inyecta en el contexto
del agente (conciencia situacional en cada turno) y alimenta el informe de
situación por voz. Base para la proactividad que razona sobre cambios de estado.

La construcción de hechos, el bloque de contexto y el informe son funciones
PURAS y testeables sobre un dict de estado; la recolección de cada dominio se
aísla y se cachea unos segundos para no recalcular en cada turno.
"""
import os
import time
import logging
import threading

logger = logging.getLogger(__name__)

_snapshot_cache = {"ts": 0.0, "state": None}
_cache_lock = threading.Lock()

_LEVEL_WORD = {"green": "VERDE", "amber": "ÁMBAR", "red": "ROJA", "violet": "VIOLETA"}


# ----------------------------------------------------------------------------
# Formato / clasificación (puro)
# ----------------------------------------------------------------------------
def _fmt_uptime(seconds) -> str:
    try:
        seconds = max(0, int(seconds))
    except (TypeError, ValueError):
        return "0m"
    h, m = seconds // 3600, (seconds % 3600) // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


def overall_status(state: dict) -> str:
    """Estado global agregado: 'critical' | 'advisory' | 'nominal' (puro)."""
    threat = (state.get("threat", {}).get("level") or "green").lower()
    ram = state.get("system", {}).get("ram") or 0
    try:
        ram = float(ram)
    except (TypeError, ValueError):
        ram = 0
    stopped = state.get("services", {}).get("stopped") or 0
    if threat in ("red", "violet") or ram >= 90:
        return "critical"
    if threat == "amber" or ram >= 80 or stopped > 0:
        return "advisory"
    return "nominal"


def build_facts(state: dict):
    """Lista de hechos legibles del estado, omitiendo lo irrelevante (puro)."""
    facts = []
    sysm = state.get("system", {})
    ram = sysm.get("ram")
    if ram is not None:
        facts.append(f"RAM del sistema al {ram}%")
    cpu = sysm.get("cpu")
    if cpu:
        facts.append(f"CPU al {cpu}%")
    up = sysm.get("uptime_seconds")
    if up:
        facts.append(f"uptime {_fmt_uptime(up)}")

    svc = state.get("services", {})
    if svc.get("running"):
        running = f"{svc['running']} servicios activos"
        if svc.get("stopped"):
            running += f" ({svc['stopped']} detenidos)"
        facts.append(running)

    threat = state.get("threat", {})
    level = (threat.get("level") or "green").lower()
    word = _LEVEL_WORD.get(level, level.upper())
    if level == "green":
        facts.append("nivel de amenaza VERDE")
    else:
        reasons = ", ".join(threat.get("reasons", [])[:3])
        facts.append(f"nivel de amenaza {word}" + (f" ({reasons})" if reasons else ""))

    proj = state.get("project", {})
    if proj.get("is_repo"):
        bits = [f"proyecto {proj.get('repo_name', '?')}"]
        if proj.get("branch"):
            bits.append(f"rama {proj['branch']}")
        dirty = proj.get("dirty_count") or 0
        bits.append(f"{dirty} cambios sin confirmar" if dirty else "sin cambios pendientes")
        facts.append(", ".join(bits))

    prod = state.get("productivity", {})
    if prod.get("top"):
        foco = f"foco de hoy: {prod['top']}"
        if prod.get("total_seconds"):
            foco += f" ({_fmt_uptime(prod['total_seconds'])} registrados)"
        facts.append(foco)

    net = state.get("network", {})
    if net.get("devices"):
        dev = f"{net['devices']} dispositivos en red"
        if net.get("unknown"):
            dev += f" ({net['unknown']} desconocidos)"
        facts.append(dev)

    watches = state.get("watches", {})
    if watches.get("count"):
        facts.append(f"{watches['count']} vigilancia(s) activa(s)")

    usage = state.get("usage", {})
    if usage.get("calls"):
        facts.append(f"{usage['calls']} llamadas de IA hoy")

    return facts


def build_context_block(state: dict) -> str:
    """Bloque de texto compacto para inyectar en el prompt del agente (puro)."""
    facts = build_facts(state)
    if not facts:
        return ""
    return "ESTADO GLOBAL DEL SISTEMA (conciencia situacional):\n" + "; ".join(facts) + "."


def build_situation_report(state: dict) -> str:
    """Informe de situación hablado, con tono Stark (puro)."""
    facts = build_facts(state)
    if not facts:
        return "No dispongo de telemetría suficiente para un informe, señor."
    status = overall_status(state)
    cabecera = {
        "critical": "Informe de situación, señor. Atención: situación crítica.",
        "advisory": "Informe de situación, señor. Todo operativo, con algún aviso.",
        "nominal": "Informe de situación, señor. Todos los sistemas nominales.",
    }[status]
    return cabecera + " " + "; ".join(facts) + "."


# ----------------------------------------------------------------------------
# Recolección de dominios (aislada)
# ----------------------------------------------------------------------------
def _gather_state() -> dict:
    """Reúne el estado vivo de todos los dominios (best-effort, cada uno guardado)."""
    state = {"system": {}, "services": {}, "threat": {}, "project": {},
             "productivity": {}, "network": {}, "watches": {}, "usage": {}}

    try:
        from core.self_monitor import get_health_dashboard
        dash = get_health_dashboard()
        sysm = dash.get("system", {})
        state["system"] = {
            "ram": sysm.get("system_ram_percent"),
            "cpu": sysm.get("cpu_percent"),
            "proc_ram_mb": sysm.get("process_ram_mb"),
            "uptime_seconds": sysm.get("uptime_seconds"),
        }
        state["services"] = dash.get("services", {})
        usage = dash.get("usage", {})
        state["usage"] = {"calls": usage.get("calls", 0)}
    except Exception as e:
        logger.debug(f"[WorldModel] Sin dashboard de salud: {e}")

    try:
        from core.threat_level import compute_threat_level
        t = compute_threat_level()
        state["threat"] = {"level": t.get("level", "green"), "reasons": t.get("reasons", [])}
    except Exception as e:
        logger.debug(f"[WorldModel] Sin nivel de amenaza: {e}")

    try:
        from core.project_awareness import get_active_project
        state["project"] = get_active_project()
    except Exception as e:
        logger.debug(f"[WorldModel] Sin proyecto activo: {e}")

    try:
        from core.productivity import _load_today
        from core.resume_context import top_activity
        tally = _load_today()
        state["productivity"] = {"top": top_activity(tally),
                                 "total_seconds": sum(tally.values()) if tally else 0}
    except Exception as e:
        logger.debug(f"[WorldModel] Sin productividad: {e}")

    try:
        from core.network_sentinel import active_devices
        devices = list(active_devices or [])
        unknown = sum(1 for d in devices if not d.get("known", False))
        state["network"] = {"devices": len(devices), "unknown": unknown}
    except Exception as e:
        logger.debug(f"[WorldModel] Sin red: {e}")

    try:
        from core.watchpost import list_watches
        w = list_watches()
        state["watches"] = {"count": len(w), "labels": [x["label"] for x in w]}
    except Exception as e:
        logger.debug(f"[WorldModel] Sin vigilancias: {e}")

    return state


def snapshot(max_age: float = None) -> dict:
    """Estado unificado del mundo, cacheado unos segundos para no recalcular."""
    if max_age is None:
        max_age = float(os.getenv("JARVIS_WORLD_MODEL_TTL", "8"))
    now = time.time()
    with _cache_lock:
        if _snapshot_cache["state"] is not None and (now - _snapshot_cache["ts"]) < max_age:
            return _snapshot_cache["state"]
    state = _gather_state()
    with _cache_lock:
        _snapshot_cache["ts"] = now
        _snapshot_cache["state"] = state
    return state


def get_context_block() -> str:
    """Bloque de contexto situacional para el prompt del agente ("" si no hay)."""
    try:
        return build_context_block(snapshot())
    except Exception as e:
        logger.debug(f"[WorldModel] No se pudo construir el contexto: {e}")
        return ""


def get_situation_report() -> str:
    """Informe de situación hablado del estado global actual."""
    return build_situation_report(snapshot())
