"""
core/game_mode.py — Modo Gaming / Bajo Consumo.

Pausa temporalmente los servicios de segundo plano pesados para liberar CPU y
RAM mientras se juega o se hace una tarea exigente, y los reanuda al salir.

Diseño:
  - enter_game_mode() pausa SOLO los servicios pesados que estén 'running' en ese
    momento, recordando cuáles fueron para reanudar exactamente esos al salir
    (así se respeta lo que el usuario tuviera desactivado por configuración).
  - exit_game_mode() reanuda los servicios que se pausaron.
  - Se mantienen activos RAM Guard (protege el sistema) y las interfaces
    (GUI/Telegram), que no son cargas pesadas.

Módulo ligero (logging + importlib; importa core.services de forma perezosa).
"""
import logging
import importlib

logger = logging.getLogger(__name__)

# Servicios pesados que se pausan en modo gaming.
# (clave_de_estado, módulo, función_de_arranque, función_de_parada)
_GAME_MODE_SERVICES = [
    ("test_watcher", "core.test_watcher", "start_test_watcher", "stop_test_watcher"),
    ("network_sentinel", "core.network_sentinel", "start_network_sentinel", "stop_network_sentinel"),
    ("api_sentinel", "core.api_sentinel", "start_api_sentinel", "stop_api_sentinel"),
    ("vulnerability_patcher", "core.vulnerability_patcher", "start_vulnerability_patcher_daemon", "stop_vulnerability_patcher_daemon"),
    ("integrity_sentinel", "core.jarvis_integrity", "start_integrity_sentinel_daemon", "stop_integrity_sentinel_daemon"),
    ("task_scheduler", "core.scheduler", "start_scheduler", "stop_scheduler"),
    ("clipboard_monitor", "core.clipboard_monitor", "start_clipboard_monitor", "stop_clipboard_monitor"),
    ("log_maintenance", "core.log_maintenance", "start_log_maintenance", "stop_log_maintenance"),
]

_game_mode_active = False
_paused_services = []  # claves de estado pausadas en la última activación


def is_game_mode_active() -> bool:
    """Indica si el modo gaming está activo."""
    return _game_mode_active


def get_paused_services() -> list:
    """Retorna una copia de la lista de servicios pausados por el modo gaming."""
    return list(_paused_services)


def enter_game_mode() -> dict:
    """Activa el modo gaming: pausa los servicios pesados que estén corriendo.

    Returns:
        dict: {"already_active": bool, "paused": [claves]}
    """
    global _game_mode_active, _paused_services
    if _game_mode_active:
        return {"already_active": True, "paused": list(_paused_services)}

    try:
        from core.services import get_services_status
        status = get_services_status()
    except Exception as e:
        logger.error(f"[GameMode] No se pudo obtener el estado de servicios: {e}")
        status = {}

    paused = []
    for key, module_path, _start_fn, stop_fn in _GAME_MODE_SERVICES:
        if status.get(key) != "running":
            continue
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, stop_fn, None)
            if fn:
                fn()
                paused.append(key)
                logger.info(f"[GameMode] Servicio '{key}' pausado.")
        except Exception as e:
            logger.error(f"[GameMode] Error al pausar '{key}': {e}")

    _paused_services = paused
    _game_mode_active = True
    logger.info(f"[GameMode] Modo gaming activado. Pausados: {paused}")
    return {"already_active": False, "paused": paused}


def exit_game_mode() -> dict:
    """Desactiva el modo gaming: reanuda los servicios que se pausaron.

    Returns:
        dict: {"was_active": bool, "resumed": [claves]}
    """
    global _game_mode_active, _paused_services
    if not _game_mode_active:
        return {"was_active": False, "resumed": []}

    start_by_key = {key: (mp, start_fn) for key, mp, start_fn, _stop in _GAME_MODE_SERVICES}
    resumed = []
    for key in _paused_services:
        entry = start_by_key.get(key)
        if not entry:
            continue
        module_path, start_fn = entry
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, start_fn, None)
            if fn:
                fn()
                resumed.append(key)
                logger.info(f"[GameMode] Servicio '{key}' reanudado.")
        except Exception as e:
            logger.error(f"[GameMode] Error al reanudar '{key}': {e}")

    _paused_services = []
    _game_mode_active = False
    logger.info(f"[GameMode] Modo gaming desactivado. Reanudados: {resumed}")
    return {"was_active": True, "resumed": resumed}
