import os
import logging
import threading

# Import service modules
import gui.app as gui_app
import core.telegram_bot as tg_bot
import core.network_sentinel as net_sentinel
import core.api_sentinel as api_sentinel
import core.vulnerability_patcher as vuln_patcher
import core.jarvis_integrity as integrity
import core.test_watcher as test_watcher
import core.scheduler as scheduler
import core.ram_guard as ram_guard
import core.log_maintenance as log_maintenance
import core.clipboard_monitor as clipboard_monitor
import core.dependency_health as dep_health
import core.daily_digest as daily_digest
import core.morning_briefing as morning_briefing
import core.threat_level as threat_level
import core.self_monitor as self_monitor
import core.proactive_vision as proactive_vision
import core.night_mode as night_mode

def start_all_services():
    """
    Arranca todos los servicios de segundo plano en orden secuencial.
    Cada start_* es idempotente y valida su propia configuración en .env.
    """
    logging.info("[Services] Iniciando arranque centralizado de servicios de Jarvis...")

    # 1. Web GUI (Flask + Socket.IO) — controlado por JARVIS_GUI_ENABLED
    try:
        gui_app.run_gui_in_background()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Web GUI: {e}")

    # 2. Bot de Telegram (Control Remoto) — controlado internamente por TELEGRAM_BOT_TOKEN
    #    y adicionalmente por JARVIS_TELEGRAM_ENABLED
    try:
        tg_enabled = os.getenv("JARVIS_TELEGRAM_ENABLED", "true").lower() in ("true", "1", "yes")
        if tg_enabled:
            tg_bot.start_telegram_bot()
        else:
            logging.info("[Services] Bot de Telegram desactivado por configuración.")
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Bot de Telegram: {e}")

    # 3. Centinela de Red Local — controlado por JARVIS_SENTINEL_ENABLED
    try:
        net_sentinel.start_network_sentinel()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Centinela de Red Local: {e}")

    # 4. Centinela de APIs de terceros — controlado por JARVIS_API_SENTINEL_ENABLED
    try:
        api_sentinel.start_api_sentinel()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Centinela de APIs: {e}")

    # 5. Reparador Autónomo de Dependencias (Patcher) — controlado por JARVIS_VULNERABILITY_PATCHER_ENABLED / JARVIS_PATCHER_ENABLED
    try:
        patcher_enabled = os.getenv("JARVIS_PATCHER_ENABLED")
        if patcher_enabled is not None:
            # Alias: JARVIS_PATCHER_ENABLED sobreescribe JARVIS_VULNERABILITY_PATCHER_ENABLED
            os.environ["JARVIS_VULNERABILITY_PATCHER_ENABLED"] = patcher_enabled
        vuln_patcher.start_vulnerability_patcher_daemon()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Reparador de Dependencias: {e}")

    # 6. Sentinel de Integridad de Jarvis — controlado por JARVIS_INTEGRITY_SENTINEL_ENABLED
    try:
        integrity.start_integrity_sentinel_daemon()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Sentinel de Integridad: {e}")

    # 7. Centinela de Pruebas Unitarias (Test Watcher) — controlado por JARVIS_TEST_WATCHER
    try:
        test_watcher.start_test_watcher()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Centinela de Pruebas: {e}")

    # 8. Planificador de Tareas (Scheduler) — controlado por JARVIS_SCHEDULER
    try:
        sched_enabled = os.getenv("JARVIS_SCHEDULER", "true").lower() in ("true", "1", "yes")
        if sched_enabled:
            scheduler.start_scheduler()
        else:
            logging.info("[Services] Planificador de tareas desactivado por configuración.")
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Planificador de Tareas: {e}")

    # 9. RAM Guard — siempre activo (es ligero y protege el sistema)
    try:
        ram_guard.start_ram_guard()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar RAM Guard: {e}")

    # 10. Mantenimiento de logs/temporales — controlado por JARVIS_LOG_MAINTENANCE_ENABLED
    try:
        log_maintenance.start_log_maintenance()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Mantenimiento de Logs: {e}")

    # 11. Monitor de Portapapeles (Clipboard Monitor) — controlado por JARVIS_CLIPBOARD_MONITOR_ENABLED
    try:
        clipboard_monitor.start_clipboard_monitor()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Monitor de Portapapeles: {e}")

    # 12. Auditoría de Salud de Dependencias — controlado por JARVIS_DEP_HEALTH_ENABLED
    try:
        dep_health.start_dependency_health_daemon()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Auditoría de Dependencias: {e}")

    # 13. Resumen Diario programado (Daily Digest) — controlado por JARVIS_DAILY_DIGEST_ENABLED
    try:
        daily_digest.start_daily_digest_daemon()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Resumen Diario: {e}")

    # 14. Briefing Matutino programado — controlado por JARVIS_MORNING_BRIEFING_ENABLED
    try:
        morning_briefing.start_morning_briefing_daemon()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Briefing Matutino: {e}")

    # 15. Nivel de Amenaza DEFCON — controlado por JARVIS_THREAT_LEVEL_ENABLED (on por defecto)
    try:
        threat_level.start_threat_level_daemon()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Nivel de Amenaza DEFCON: {e}")

    # 16. Dashboard de Salud (Self-Monitoring) — controlado por JARVIS_SELF_MONITOR_ENABLED (on por defecto)
    try:
        self_monitor.start_self_monitor_daemon()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Dashboard de Salud: {e}")

    # 17. JARVIS Proactivo Visual — controlado por JARVIS_PROACTIVE_VISION_ENABLED (off por defecto)
    try:
        proactive_vision.start_proactive_vision_daemon()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Visión Proactiva: {e}")

    # 19. Protocolo Blackout (modo noche) — controlado por JARVIS_BLACKOUT_ENABLED (off por defecto)
    try:
        night_mode.start_night_mode_daemon()
    except Exception as e:
        logging.error(f"❌ [Services] Error al iniciar Protocolo Blackout: {e}")

    logging.info("[Services] Arranque de servicios completado.")

def stop_all_services():
    """
    Detiene todos los servicios en orden inverso al de arranque.
    Usa bloques try/except individuales para que un fallo no bloquee la parada de los demás.
    """
    logging.info("[Services] Deteniendo todos los servicios en orden inverso...")

    # 19. Protocolo Blackout (modo noche)
    try:
        night_mode.stop_night_mode_daemon()
    except Exception as e:
        logging.error(f"Error al detener Protocolo Blackout: {e}")

    # 17. JARVIS Proactivo Visual
    try:
        proactive_vision.stop_proactive_vision_daemon()
    except Exception as e:
        logging.error(f"Error al detener Visión Proactiva: {e}")

    # 16. Dashboard de Salud (Self-Monitoring)
    try:
        self_monitor.stop_self_monitor_daemon()
    except Exception as e:
        logging.error(f"Error al detener Dashboard de Salud: {e}")

    # 15. Nivel de Amenaza DEFCON
    try:
        threat_level.stop_threat_level_daemon()
    except Exception as e:
        logging.error(f"Error al detener Nivel de Amenaza DEFCON: {e}")

    # 14. Briefing Matutino programado
    try:
        morning_briefing.stop_morning_briefing_daemon()
    except Exception as e:
        logging.error(f"Error al detener Briefing Matutino: {e}")

    # 13. Resumen Diario programado (Daily Digest)
    try:
        daily_digest.stop_daily_digest_daemon()
    except Exception as e:
        logging.error(f"Error al detener Resumen Diario: {e}")

    # 12. Auditoría de Salud de Dependencias
    try:
        dep_health.stop_dependency_health_daemon()
    except Exception as e:
        logging.error(f"Error al detener Auditoría de Dependencias: {e}")

    # 10. Mantenimiento de logs
    try:
        log_maintenance.stop_log_maintenance()
    except Exception as e:
        logging.error(f"Error al detener Mantenimiento de Logs: {e}")

    # 11. Monitor de Portapapeles (Clipboard Monitor)
    try:
        clipboard_monitor.stop_clipboard_monitor()
    except Exception as e:
        logging.error(f"Error al detener Monitor de Portapapeles: {e}")

    # 9. RAM Guard
    try:
        ram_guard.stop_ram_guard()
    except Exception as e:
        logging.error(f"Error al detener RAM Guard: {e}")

    # 8. Planificador de Tareas (Scheduler)
    try:
        scheduler.stop_scheduler()
    except Exception as e:
        logging.error(f"Error al detener Planificador de Tareas: {e}")

    # 7. Centinela de Pruebas Unitarias (Test Watcher)
    try:
        test_watcher.stop_test_watcher()
    except Exception as e:
        logging.error(f"Error al detener Centinela de Pruebas: {e}")

    # 6. Sentinel de Integridad de Jarvis
    try:
        integrity.stop_integrity_sentinel_daemon()
    except Exception as e:
        logging.error(f"Error al detener Sentinel de Integridad: {e}")

    # 5. Reparador de Dependencias (Patcher)
    try:
        vuln_patcher.stop_vulnerability_patcher_daemon()
    except Exception as e:
        logging.error(f"Error al detener Reparador de Dependencias: {e}")

    # 4. Centinela de APIs
    try:
        api_sentinel.stop_api_sentinel()
    except Exception as e:
        logging.error(f"Error al detener Centinela de APIs: {e}")

    # 3. Centinela de Red Local
    try:
        net_sentinel.stop_network_sentinel()
    except Exception as e:
        logging.error(f"Error al detener Centinela de Red Local: {e}")

    # 2. Bot de Telegram
    try:
        tg_bot.stop_telegram_bot()
    except Exception as e:
        logging.error(f"Error al detener Bot de Telegram: {e}")

    # 1. Monitor de GUI (Active Window)
    try:
        gui_app.stop_gui_monitor()
    except Exception as e:
        logging.error(f"Error al detener monitor de GUI: {e}")

    # Detener monitores de soporte de GUI (Privacy monitor)
    try:
        from core.privacy_sentinel import stop_privacy_monitor
        stop_privacy_monitor()
    except Exception as e:
        logging.error(f"Error al detener monitor de privacidad: {e}")

    logging.info("[Services] Todos los servicios detenidos.")

def get_services_status() -> dict:
    """
    Retorna un diccionario con el estado actual de cada servicio:
    'running' (si el hilo está vivo), 'stopped' (hilo no activo/detenido),
    o 'disabled' (si la variable de entorno correspondiente lo desactiva).
    """
    status = {}

    # 1. Web GUI
    gui_enabled = os.getenv("JARVIS_GUI_ENABLED", "true").lower() in ("true", "1", "yes")
    if not gui_enabled:
        status["web_gui"] = "disabled"
    else:
        gui_alive = gui_app._gui_thread is not None and gui_app._gui_thread.is_alive()
        status["web_gui"] = "running" if gui_alive else "stopped"

    # 2. Bot de Telegram
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_enabled = os.getenv("JARVIS_TELEGRAM_ENABLED", "true").lower() in ("true", "1", "yes")
    if not tg_token or not tg_token.strip() or not tg_enabled:
        status["telegram_bot"] = "disabled"
    else:
        bot_alive = tg_bot.bot_thread is not None and tg_bot.bot_thread.is_alive()
        status["telegram_bot"] = "running" if bot_alive else "stopped"

    # 3. Centinela de Red
    if os.getenv("JARVIS_SENTINEL_ENABLED", "True").lower() != "true":
        status["network_sentinel"] = "disabled"
    else:
        net_alive = net_sentinel.sentinel_thread is not None and net_sentinel.sentinel_thread.is_alive()
        status["network_sentinel"] = "running" if net_alive else "stopped"

    # 4. Centinela de APIs
    if os.getenv("JARVIS_API_SENTINEL_ENABLED", "false").lower() not in ("true", "1", "yes"):
        status["api_sentinel"] = "disabled"
    else:
        api_alive = api_sentinel.SENTINEL_THREAD is not None and api_sentinel.SENTINEL_THREAD.is_alive()
        status["api_sentinel"] = "running" if api_alive else "stopped"

    # 5. Patcher de Dependencias
    patcher_key = os.getenv("JARVIS_PATCHER_ENABLED", os.getenv("JARVIS_VULNERABILITY_PATCHER_ENABLED", "false"))
    if patcher_key.lower() not in ("true", "1", "yes"):
        status["vulnerability_patcher"] = "disabled"
    else:
        patcher_alive = vuln_patcher.PATCHER_THREAD is not None and vuln_patcher.PATCHER_THREAD.is_alive()
        status["vulnerability_patcher"] = "running" if patcher_alive else "stopped"

    # 6. Sentinel de Integridad
    if os.getenv("JARVIS_INTEGRITY_SENTINEL_ENABLED", "false").lower() not in ("true", "1", "yes"):
        status["integrity_sentinel"] = "disabled"
    else:
        integrity_alive = integrity.INTEGRITY_THREAD is not None and integrity.INTEGRITY_THREAD.is_alive()
        status["integrity_sentinel"] = "running" if integrity_alive else "stopped"

    # 7. Test Watcher
    if os.getenv("JARVIS_TEST_WATCHER", "false").lower() != "true":
        status["test_watcher"] = "disabled"
    else:
        watcher_alive = test_watcher._watcher_thread is not None and test_watcher._watcher_thread.is_alive()
        status["test_watcher"] = "running" if watcher_alive else "stopped"

    # 8. Task Scheduler
    sched_enabled = os.getenv("JARVIS_SCHEDULER", "true").lower() in ("true", "1", "yes")
    if not sched_enabled:
        status["task_scheduler"] = "disabled"
    else:
        status["task_scheduler"] = "running" if scheduler.is_scheduler_running() else "stopped"

    # 9. RAM Guard
    ram_alive = ram_guard.RAM_GUARD_THREAD is not None and ram_guard.RAM_GUARD_THREAD.is_alive()
    status["ram_guard"] = "running" if ram_alive else "stopped"

    # 10. Mantenimiento de logs
    lm_enabled = os.getenv("JARVIS_LOG_MAINTENANCE_ENABLED", "true").lower() in ("true", "1", "yes")
    if not lm_enabled:
        status["log_maintenance"] = "disabled"
    else:
        lm_alive = log_maintenance.MAINTENANCE_THREAD is not None and log_maintenance.MAINTENANCE_THREAD.is_alive()
        status["log_maintenance"] = "running" if lm_alive else "stopped"

    # 11. Privacy Monitor
    try:
        interval = int(os.getenv("JARVIS_PRIVACY_SCAN_INTERVAL", "900"))
        if interval <= 0:
            status["privacy_monitor"] = "disabled"
        else:
            from core.privacy_sentinel import MONITOR_THREAD
            privacy_alive = MONITOR_THREAD is not None and MONITOR_THREAD.is_alive()
            status["privacy_monitor"] = "running" if privacy_alive else "stopped"
    except Exception:
        status["privacy_monitor"] = "stopped"

    # 12. Clipboard Monitor
    clipboard_enabled = os.getenv("JARVIS_CLIPBOARD_MONITOR_ENABLED", "true").lower() in ("true", "1", "yes")
    if not clipboard_enabled:
        status["clipboard_monitor"] = "disabled"
    else:
        status["clipboard_monitor"] = "running" if clipboard_monitor.is_clipboard_monitor_running() else "stopped"

    # 13. Auditoría de Salud de Dependencias
    if os.getenv("JARVIS_DEP_HEALTH_ENABLED", "false").lower() not in ("true", "1", "yes"):
        status["dependency_health"] = "disabled"
    else:
        dep_alive = dep_health.HEALTH_THREAD is not None and dep_health.HEALTH_THREAD.is_alive()
        status["dependency_health"] = "running" if dep_alive else "stopped"

    # 14. Resumen Diario programado (Daily Digest)
    if os.getenv("JARVIS_DAILY_DIGEST_ENABLED", "false").lower() not in ("true", "1", "yes"):
        status["daily_digest"] = "disabled"
    else:
        digest_alive = daily_digest.DIGEST_THREAD is not None and daily_digest.DIGEST_THREAD.is_alive()
        status["daily_digest"] = "running" if digest_alive else "stopped"

    # 15. Briefing Matutino programado
    if os.getenv("JARVIS_MORNING_BRIEFING_ENABLED", "false").lower() not in ("true", "1", "yes"):
        status["morning_briefing"] = "disabled"
    else:
        briefing_alive = morning_briefing.BRIEFING_THREAD is not None and morning_briefing.BRIEFING_THREAD.is_alive()
        status["morning_briefing"] = "running" if briefing_alive else "stopped"

    # 16. Nivel de Amenaza DEFCON (on por defecto)
    if os.getenv("JARVIS_THREAT_LEVEL_ENABLED", "true").lower() not in ("true", "1", "yes"):
        status["threat_level"] = "disabled"
    else:
        threat_alive = threat_level.THREAT_THREAD is not None and threat_level.THREAT_THREAD.is_alive()
        status["threat_level"] = "running" if threat_alive else "stopped"

    # 17. Dashboard de Salud (Self-Monitoring) (on por defecto)
    if os.getenv("JARVIS_SELF_MONITOR_ENABLED", "true").lower() not in ("true", "1", "yes"):
        status["self_monitor"] = "disabled"
    else:
        monitor_alive = self_monitor.MONITOR_THREAD is not None and self_monitor.MONITOR_THREAD.is_alive()
        status["self_monitor"] = "running" if monitor_alive else "stopped"

    # 18. JARVIS Proactivo Visual (off por defecto)
    if os.getenv("JARVIS_PROACTIVE_VISION_ENABLED", "false").lower() not in ("true", "1", "yes"):
        status["proactive_vision"] = "disabled"
    else:
        vision_alive = proactive_vision.VISION_THREAD is not None and proactive_vision.VISION_THREAD.is_alive()
        status["proactive_vision"] = "running" if vision_alive else "stopped"

    # 19. Protocolo Blackout (modo noche) (off por defecto)
    if os.getenv("JARVIS_BLACKOUT_ENABLED", "false").lower() not in ("true", "1", "yes"):
        status["night_mode"] = "disabled"
    else:
        blackout_alive = night_mode.BLACKOUT_THREAD is not None and night_mode.BLACKOUT_THREAD.is_alive()
        status["night_mode"] = "running" if blackout_alive else "stopped"

    return status
