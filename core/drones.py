"""
core/drones.py — "Iron Legion" (enjambre de drones).

Permite lanzar tareas largas en segundo plano como "drones" autónomos. Cada dron
corre en su propio hilo, lleva un estado en vivo (en curso / completado / fallido),
avisa por voz al terminar y se refleja en la GUI. Hay un registro de "misiones"
(tareas predefinidas) y se pueden consultar, lanzar y limpiar.

El registro de estado y el formateo son puros/aislados y testeables; la voz y la
emisión a la GUI se aíslan. Es la base de Casa Llena (multi-agente) y Mark II.
"""
import uuid
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

DRONES = {}          # id -> estado del dron
MISSIONS = {}        # nombre -> {label, fn}
_lock = threading.Lock()
_counter = 0


def register_mission(name: str, label: str, fn):
    """Registra una misión lanzable como dron (fn sin argumentos -> resultado)."""
    MISSIONS[name] = {"label": label, "fn": fn}


def list_missions() -> dict:
    return {name: m["label"] for name, m in MISSIONS.items()}


def _public(drone: dict) -> dict:
    """Vista serializable del dron (sin el hilo interno)."""
    return {k: v for k, v in drone.items() if not k.startswith("_")}


def get_drones() -> list:
    with _lock:
        return [_public(d) for d in DRONES.values()]


def _emit():
    import sys
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        mod.socketio.emit("drones_update", get_drones())
    except Exception:
        pass


def _notify_done(drone: dict):
    ok = drone["status"] == "completed"
    msg = (f"Dron {drone['short']}, {drone['name']}, misión completada, señor."
           if ok else f"Señor, el dron {drone['short']} ({drone['name']}) ha fallado.")
    try:
        from tools.voice import speak
        speak(msg, disable_vad=True, tone="success" if ok else "alert")
    except Exception as e:
        logger.warning(f"[Drones] No se pudo avisar por voz: {e}")


def format_drones(drones=None) -> str:
    """Resumen del estado del enjambre (puro respecto a la lista dada)."""
    drones = drones if drones is not None else get_drones()
    if not drones:
        return "No hay drones desplegados, señor."
    running = [d for d in drones if d["status"] == "running"]
    done = [d for d in drones if d["status"] == "completed"]
    failed = [d for d in drones if d["status"] == "failed"]
    parts = [f"{len(running)} en curso", f"{len(done)} completados", f"{len(failed)} fallidos"]
    summary = "Estado del enjambre, señor: " + ", ".join(parts) + "."
    actives = ", ".join(f"{d['short']} ({d['name']})" for d in running[:5])
    if actives:
        summary += f" Operativos: {actives}."
    return summary


def _run_drone(drone_id: str, fn):
    drone = DRONES.get(drone_id)
    if drone is None:
        return
    try:
        result = fn()
        with _lock:
            drone["status"] = "completed"
            drone["result"] = (str(result)[:500] if result else "OK")
    except Exception as e:
        logger.warning(f"[Drones] Dron {drone_id} falló: {e}")
        with _lock:
            drone["status"] = "failed"
            drone["error"] = str(e)[:300]
    finally:
        with _lock:
            drone["finished_at"] = datetime.now().isoformat()
        _emit()
        _notify_done(drone)


def launch_drone(mission_name: str, label: str = None, fn=None):
    """Lanza un dron. Por nombre de misión registrada, o con label+fn directos.
    Devuelve el estado del dron, o None si la misión no existe."""
    global _counter
    if fn is None:
        mission = MISSIONS.get(mission_name)
        if not mission:
            return None
        label = mission["label"]
        fn = mission["fn"]
    with _lock:
        _counter += 1
        did = uuid.uuid4().hex[:8]
        drone = {
            "id": did, "short": f"{_counter:02d}", "mission": mission_name,
            "name": label or mission_name, "status": "running",
            "result": None, "error": None,
            "started_at": datetime.now().isoformat(), "finished_at": None,
        }
        DRONES[did] = drone
    t = threading.Thread(target=_run_drone, args=(did, fn), name=f"Drone-{did}", daemon=True)
    drone["_thread"] = t
    t.start()
    _emit()
    return _public(drone)


def _mission_tests():
    import subprocess
    res = subprocess.run(["python", "-m", "pytest", "-q", "--no-header"],
                         capture_output=True, text=True, timeout=900)
    lines = [l for l in (res.stdout or "").splitlines() if l.strip()]
    summary = lines[-1] if lines else "sin salida"
    return f"Suite de pruebas: {summary}"


def _mission_dependencies():
    from core.dependency_health import run_and_report
    r = run_and_report() or {}
    return f"Auditoría de dependencias: {r.get('outdated', '?')} desactualizadas, {r.get('total', '?')} revisadas."


def _mission_cleanup():
    from core.log_maintenance import run_log_maintenance
    r = run_log_maintenance() or {}
    return f"Limpieza completada: {r}"


_BUILTINS_REGISTERED = False


def register_builtin_missions():
    """Registra las misiones integradas (idempotente)."""
    global _BUILTINS_REGISTERED
    if _BUILTINS_REGISTERED:
        return
    register_mission("tests", "Suite de Pruebas", _mission_tests)
    register_mission("dependencias", "Auditoría de Dependencias", _mission_dependencies)
    register_mission("limpieza", "Mantenimiento de Logs", _mission_cleanup)
    _BUILTINS_REGISTERED = True


def find_drone(short_or_id: str):
    """Localiza un dron por su número corto ('03') o por id."""
    s = (short_or_id or "").strip().lstrip("#").lstrip("0") or "0"
    with _lock:
        for d in DRONES.values():
            if d["id"] == short_or_id or d["short"] == short_or_id or d["short"].lstrip("0") == s:
                return _public(d)
    return None


def clear_finished() -> int:
    """Elimina del registro los drones que ya no están en curso. Devuelve cuántos."""
    with _lock:
        finished = [k for k, d in DRONES.items() if d["status"] != "running"]
        for k in finished:
            del DRONES[k]
    _emit()
    return len(finished)
