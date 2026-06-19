"""
RAM Guard Daemon para Jarvis.
Monitoriza el consumo de memoria del proceso y del sistema.
Si se superan los umbrales configurados, pausa los servicios pesados
de forma automática para evitar que el sistema se quede sin memoria.
"""
import os
import logging
import threading

RAM_GUARD_THREAD = None
stop_event = threading.Event()

# Estado interno
_safe_mode_active = False
_services_paused = []


def _get_ram_usage_mb() -> float:
    """Retorna el uso de RAM del proceso Jarvis actual en MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def _get_system_ram_percent() -> float:
    """Retorna el porcentaje de RAM del sistema utilizado."""
    try:
        import psutil
        return psutil.virtual_memory().percent
    except Exception:
        return 0.0


def _pause_heavy_services():
    """Pausa servicios pesados en orden para liberar RAM. No cierra Jarvis."""
    global _services_paused

    paused = []

    # Orden de pausa: menos críticos primero
    service_stops = [
        ("test_watcher", "core.test_watcher", "stop_test_watcher"),
        ("network_sentinel", "core.network_sentinel", "stop_network_sentinel"),
        ("api_sentinel", "core.api_sentinel", "stop_api_sentinel"),
        ("vulnerability_patcher", "core.vulnerability_patcher", "stop_vulnerability_patcher_daemon"),
        ("integrity_sentinel", "core.jarvis_integrity", "stop_integrity_sentinel_daemon"),
        ("scheduler", "core.scheduler", "stop_scheduler"),
    ]

    for name, module_path, func_name in service_stops:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            stop_fn = getattr(mod, func_name, None)
            if stop_fn:
                stop_fn()
                paused.append(name)
                logging.warning(f"[RAM Guard] Servicio '{name}' pausado para liberar memoria.")
        except Exception as e:
            logging.error(f"[RAM Guard] Error al pausar '{name}': {e}")

    _services_paused = paused


def _ram_guard_loop():
    """Bucle principal del daemon de monitorización de RAM."""
    global _safe_mode_active

    max_ram_mb = 2500
    max_system_percent = 90
    check_interval = 30  # segundos

    try:
        max_ram_mb = int(os.getenv("JARVIS_MAX_RAM_MB", "2500"))
    except (ValueError, TypeError):
        pass

    try:
        max_system_percent = int(os.getenv("JARVIS_MAX_SYSTEM_RAM_PERCENT", "90"))
    except (ValueError, TypeError):
        pass

    # Espera inicial para no interferir con el arranque
    if stop_event.wait(timeout=15):
        return

    while not stop_event.is_set():
        try:
            process_ram = _get_ram_usage_mb()
            system_percent = _get_system_ram_percent()

            over_process_limit = process_ram > max_ram_mb
            over_system_limit = system_percent > max_system_percent

            if (over_process_limit or over_system_limit) and not _safe_mode_active:
                reason_parts = []
                if over_process_limit:
                    reason_parts.append(f"RAM de Jarvis: {process_ram:.0f} MB (límite: {max_ram_mb} MB)")
                if over_system_limit:
                    reason_parts.append(f"RAM del sistema: {system_percent:.1f}% (límite: {max_system_percent}%)")
                reason = "; ".join(reason_parts)

                logging.warning(f"[RAM Guard] ⚠️ UMBRAL SUPERADO — {reason}")

                # Alerta por voz
                try:
                    from tools.voice import speak
                    speak(
                        "Señor, detecto un incremento inusual en el consumo de memoria. "
                        "Me he tomado la libertad de suspender temporalmente los servicios secundarios "
                        "para prevenir un desbordamiento del sistema.",
                        disable_vad=True
                    )
                except Exception:
                    pass

                # Pausar servicios si está habilitado
                auto_safe = os.getenv("JARVIS_AUTO_SAFE_MODE_ON_HIGH_RAM", "true").lower() in ("true", "1", "yes")
                if auto_safe:
                    _pause_heavy_services()
                    _safe_mode_active = True
                    logging.warning("[RAM Guard] Modo seguro activado. Servicios pesados pausados.")

            elif not over_process_limit and not over_system_limit and _safe_mode_active:
                # RAM recuperada
                logging.info(
                    f"[RAM Guard] RAM normalizada (Proceso: {process_ram:.0f} MB, "
                    f"Sistema: {system_percent:.1f}%). "
                    "Los servicios permanecen pausados hasta reiniciar Jarvis."
                )
                # No reactivamos automáticamente para evitar ciclos.
                # Solo loggeamos la recuperación.

        except Exception as e:
            logging.error(f"[RAM Guard] Error en bucle de monitorización: {e}")

        if stop_event.wait(timeout=check_interval):
            break


def start_ram_guard():
    """Inicia el daemon de monitorización de RAM. Es idempotente."""
    global RAM_GUARD_THREAD

    if RAM_GUARD_THREAD is not None and RAM_GUARD_THREAD.is_alive():
        logging.info("[RAM Guard] Ya en ejecución.")
        return

    stop_event.clear()
    RAM_GUARD_THREAD = threading.Thread(
        target=_ram_guard_loop,
        name="JarvisRAMGuardThread",
        daemon=True
    )
    RAM_GUARD_THREAD.start()
    logging.info("[RAM Guard] Daemon de monitorización de RAM iniciado.")


def stop_ram_guard():
    """Detiene el daemon de RAM Guard de forma limpia."""
    logging.info("[RAM Guard] Deteniendo monitorización de RAM...")
    stop_event.set()


def is_safe_mode_active() -> bool:
    """Retorna True si el modo seguro fue activado por RAM Guard."""
    return _safe_mode_active


def get_paused_services() -> list:
    """Retorna la lista de servicios pausados por RAM Guard."""
    return list(_services_paused)
