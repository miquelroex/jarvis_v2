"""
core/smart_lock.py — Smart Lock por proximidad Bluetooth.

Un daemon escanea periódicamente dispositivos Bluetooth LE y vigila la presencia
de tu móvil/reloj (por MAC o por nombre) y su intensidad de señal (RSSI). Cuando
te alejas (el dispositivo desaparece o su señal cae por debajo del umbral durante
varios escaneos consecutivos), Jarvis bloquea Windows. Cuando regresas, te recibe.

Nota de seguridad: Windows no permite desbloquear la sesión por software sin
credenciales, así que el "desbloqueo" se limita a un saludo de bienvenida.

Nota de privacidad: muchos móviles (p.ej. iPhone) rotan su dirección BLE por
privacidad; en esos casos conviene emparejar por nombre (JARVIS_SMART_LOCK_NAME)
o desactivar la aleatorización de MAC.

Módulo ligero: bleak y el bloqueo del SO se importan/aíslan de forma perezosa y
mockeable. La lógica de decisión es pura y testeable.
"""
import os
import sys
import logging
import threading

logger = logging.getLogger(__name__)

LOCK_THREAD = None
stop_event = threading.Event()
_warned_no_bleak = False

# Estado de la máquina de presencia (persistente entre escaneos).
_absent_count = 0
_was_present = True


def _norm_mac(mac: str) -> str:
    return (mac or "").strip().upper().replace("-", ":")


def _evaluate_presence(devices, target_mac: str, target_name: str, rssi_threshold: int):
    """Decide si el dispositivo objetivo está presente (puro).

    devices: lista de dicts {address, name, rssi}.
    Devuelve (present: bool, best_rssi: int|None).
    """
    target_mac = _norm_mac(target_mac)
    target_name = (target_name or "").strip().lower()
    best_rssi = None
    for d in devices:
        addr = _norm_mac(d.get("address", ""))
        name = (d.get("name") or "").strip().lower()
        matches = False
        if target_mac and addr == target_mac:
            matches = True
        elif target_name and name and target_name in name:
            matches = True
        if not matches:
            continue
        rssi = d.get("rssi")
        if rssi is None:
            continue
        if best_rssi is None or rssi > best_rssi:
            best_rssi = rssi
    if best_rssi is None:
        return False, None
    return best_rssi >= rssi_threshold, best_rssi


def _decide(present: bool, absent_count: int, was_present: bool, absent_threshold: int):
    """Máquina de estados de proximidad (pura).

    Devuelve (new_absent_count, new_was_present, action) donde action es
    None | "lock" | "welcome".
    """
    action = None
    if present:
        if not was_present:
            action = "welcome"
        return 0, True, action
    absent_count += 1
    if was_present and absent_count >= absent_threshold:
        action = "lock"
        was_present = False
    return absent_count, was_present, action


def _scan_devices(timeout: float):
    """Escanea dispositivos BLE y devuelve [{address, name, rssi}]. Best-effort:
    [] si bleak no está disponible o falla el adaptador."""
    global _warned_no_bleak
    try:
        import asyncio
        from bleak import BleakScanner
    except Exception:
        if not _warned_no_bleak:
            logger.warning("[SmartLock] bleak no disponible; instala 'bleak' para usar Smart Lock.")
            _warned_no_bleak = True
        return []
    try:
        async def _run():
            found = await BleakScanner.discover(timeout=timeout, return_adv=True)
            out = []
            for address, (device, adv) in found.items():
                out.append({
                    "address": address,
                    "name": getattr(device, "name", None) or getattr(adv, "local_name", None),
                    "rssi": getattr(adv, "rssi", None),
                })
            return out
        return asyncio.run(_run())
    except Exception as e:
        logger.warning(f"[SmartLock] Error al escanear Bluetooth: {e}")
        return []


def _lock_workstation():
    """Bloquea la sesión de Windows (best-effort, mockeable)."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return True
    except Exception as e:
        logger.warning(f"[SmartLock] No se pudo bloquear la estación: {e}")
        return False


def _welcome():
    try:
        from tools.voice import speak
        speak("Bienvenido de nuevo, señor. Reanudando operaciones.", disable_vad=True)
    except Exception as e:
        logger.warning(f"[SmartLock] No se pudo emitir el saludo: {e}")


def _lock_loop():
    """Bucle del daemon: escanea, evalúa presencia y actúa."""
    global _absent_count, _was_present
    if stop_event.wait(timeout=10):
        return
    while not stop_event.is_set():
        try:
            target_mac = os.getenv("JARVIS_SMART_LOCK_MAC", "")
            target_name = os.getenv("JARVIS_SMART_LOCK_NAME", "")
            rssi_threshold = int(os.getenv("JARVIS_SMART_LOCK_RSSI_THRESHOLD", "-85"))
            absent_threshold = int(os.getenv("JARVIS_SMART_LOCK_ABSENT_SCANS", "3"))
            scan_timeout = float(os.getenv("JARVIS_SMART_LOCK_SCAN_TIMEOUT", "6"))

            devices = _scan_devices(scan_timeout)
            present, rssi = _evaluate_presence(devices, target_mac, target_name, rssi_threshold)
            _absent_count, _was_present, action = _decide(
                present, _absent_count, _was_present, absent_threshold)

            if action == "lock":
                logging.info("[SmartLock] Dispositivo ausente; bloqueando la estación.")
                _lock_workstation()
            elif action == "welcome":
                logging.info(f"[SmartLock] Dispositivo de vuelta (RSSI {rssi}); dando la bienvenida.")
                _welcome()
        except Exception as e:
            logger.error(f"[SmartLock] Error en el bucle del daemon: {e}")

        interval = int(os.getenv("JARVIS_SMART_LOCK_INTERVAL", "20"))
        if stop_event.wait(timeout=interval):
            break


def start_smart_lock_daemon():
    """Lanza el daemon de Smart Lock. Idempotente. Off por defecto
    (JARVIS_SMART_LOCK_ENABLED) y requiere MAC o nombre configurado."""
    global LOCK_THREAD, _absent_count, _was_present
    if os.getenv("JARVIS_SMART_LOCK_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[SmartLock] Desactivado en .env.")
        return
    if not os.getenv("JARVIS_SMART_LOCK_MAC", "").strip() and not os.getenv("JARVIS_SMART_LOCK_NAME", "").strip():
        logging.info("[SmartLock] Sin MAC ni nombre configurado; daemon no iniciado.")
        return
    if LOCK_THREAD is not None and LOCK_THREAD.is_alive():
        return
    _absent_count = 0
    _was_present = True
    stop_event.clear()
    LOCK_THREAD = threading.Thread(target=_lock_loop, name="SmartLockDaemon", daemon=True)
    LOCK_THREAD.start()
    logging.info("[SmartLock] Daemon de bloqueo por proximidad iniciado.")


def stop_smart_lock_daemon():
    """Detiene el daemon de Smart Lock."""
    stop_event.set()
