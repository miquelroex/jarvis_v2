"""
core/repair_guide.py — Diagnóstico con Guía de Reparación.

Más allá del Informe de Daños (que dice QUÉ está mal), Jarvis detecta los
problemas del sistema y te GUÍA paso a paso para resolverlos: *"RAM al 91%,
señor. Le guío: primero, cierre las pestañas que no use; segundo…"*.

La detección de problemas (sobre un snapshot del estado) y las guías de
reparación son funciones PURAS y testeables; la recolección del estado se aísla
(reutiliza el Cerebro de Estado Central, world_model).
"""
import logging

logger = logging.getLogger(__name__)

# Base de conocimiento: problema -> {título, pasos}. Pura y ampliable.
_REPAIRS = {
    "ram_high": {
        "title": "RAM al límite",
        "steps": [
            "cierre las aplicaciones y pestañas que no esté usando",
            "diga «libera memoria» para que purgue cachés y lance una limpieza",
            "si persiste, reinicie los servicios pesados desde el panel o el .env",
        ],
    },
    "disk_low": {
        "title": "Espacio en disco bajo",
        "steps": [
            "vacíe la papelera y la carpeta de Descargas",
            "diga «limpia los logs» para purgar temporales y registros antiguos",
            "desinstale programas que ya no use o mueva ficheros grandes a otra unidad",
        ],
    },
    "service_down": {
        "title": "Servicios caídos",
        "steps": [
            "revise el panel de servicios para ver cuál está detenido",
            "compruebe su variable JARVIS_*_ENABLED en el .env",
            "reinicie Jarvis para relanzar los servicios de segundo plano",
        ],
    },
    "tests_failing": {
        "title": "Tests en rojo",
        "steps": [
            "diga «por qué falla» o ejecute la suite para ver el primer fallo",
            "revise el último cambio que tocó ese módulo (git diff)",
            "si el error reincide, considere el Protocolo Mark II para auto-repararlo",
        ],
    },
    "threat_high": {
        "title": "Nivel de amenaza elevado",
        "steps": [
            "diga «¿estamos seguros?» para un barrido de intrusión",
            "revise los dispositivos desconocidos en el centinela de red",
            "si algo no cuadra, active el control de acceso y aísle el equipo",
        ],
    },
    "dirty_repo": {
        "title": "Muchos cambios sin confirmar",
        "steps": [
            "revise el diff con «¿qué cambié?»",
            "agrupe y confirme los cambios con un commit descriptivo",
            "considere una rama si el trabajo aún no está listo",
        ],
    },
}


# ----------------------------------------------------------------------------
# Detección de problemas (pura, sobre un snapshot del mundo)
# ----------------------------------------------------------------------------
def detect_problems(state: dict, ram_threshold=85.0, disk_threshold=90.0,
                    dirty_threshold=25):
    """Lista de IDs de problema detectados en el estado, por gravedad. Puro."""
    problems = []
    sysm = state.get("system", {}) or {}
    try:
        ram = float(sysm.get("ram") or 0)
    except (TypeError, ValueError):
        ram = 0
    if ram >= ram_threshold:
        problems.append(("ram_high", 2))

    try:
        disk = float(sysm.get("disk") or 0)
    except (TypeError, ValueError):
        disk = 0
    if disk >= disk_threshold:
        problems.append(("disk_low", 2))

    if (state.get("services", {}) or {}).get("stopped"):
        problems.append(("service_down", 1))

    threat = (state.get("threat", {}) or {}).get("level", "green")
    if str(threat).lower() in ("red", "violet"):
        problems.append(("threat_high", 3))

    if state.get("tests_failing"):
        problems.append(("tests_failing", 2))

    dirty = (state.get("project", {}) or {}).get("dirty_count") or 0
    if dirty >= dirty_threshold:
        problems.append(("dirty_repo", 1))

    problems.sort(key=lambda p: p[1], reverse=True)  # más grave primero
    return [pid for pid, _ in problems]


def repair_guide(problem_id: str) -> dict:
    """Guía de reparación de un problema, o {} si no hay (puro)."""
    return _REPAIRS.get(problem_id, {})


def format_guide(problem_id: str) -> str:
    """Texto hablado de la guía de un problema (puro)."""
    g = repair_guide(problem_id)
    if not g:
        return ""
    pasos = "; ".join(f"{i}) {s}" for i, s in enumerate(g["steps"], 1))
    return f"{g['title']}, señor. Le guío: {pasos}."


def build_diagnosis(state: dict, top: int = 2) -> str:
    """Diagnóstico + guía de los problemas más graves del estado (puro)."""
    problems = detect_problems(state)
    if not problems:
        return ("No detecto nada que reparar, señor. Todos los sistemas en orden.")
    guias = [format_guide(p) for p in problems[:top] if format_guide(p)]
    return " ".join(guias)


# ----------------------------------------------------------------------------
# Recolección (aislada)
# ----------------------------------------------------------------------------
def _gather_state() -> dict:
    state = {}
    try:
        from core.world_model import snapshot
        state = dict(snapshot())
    except Exception as e:
        logger.debug(f"[RepairGuide] Sin estado del mundo: {e}")
    # Disco (no está en world_model) + tests en rojo (test_watcher).
    try:
        import os
        import shutil
        total, used, _ = shutil.disk_usage("C:\\")
        state.setdefault("system", {})["disk"] = round(used / total * 100, 2) if total else 0
    except Exception:
        pass
    try:
        from core.test_watcher import get_watcher_status
        last = get_watcher_status().get("last_run", {})
        state["tests_failing"] = last.get("last_run_time") is not None and last.get("last_success") is False
    except Exception:
        pass
    return state


def get_diagnosis() -> str:
    """Diagnóstico con guía bajo demanda ("diagnostícame" / "¿qué reparo?")."""
    return build_diagnosis(_gather_state())
