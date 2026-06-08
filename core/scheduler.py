import time
import threading
import logging
from datetime import datetime, timezone, timedelta
from tools.voice import speak
from core.notifier import send_push_notification
from core.memory import (
    db_get_active_tasks,
    db_save_task,
    db_delete_task,
    db_update_task_execution
)

_scheduler_running = False
_scheduler_thread = None

def is_scheduler_running() -> bool:
    """Retorna True si el planificador está activo en segundo plano."""
    global _scheduler_running
    return _scheduler_running

def execute_reminder_task(task: dict):
    """
    Ejecuta el recordatorio por voz y notificación push.
    Esta función se ejecuta en un hilo separado para no bloquear el bucle principal.
    """
    name = task["name"]
    target = task["target"]
    interval = task["interval_seconds"]
    
    logging.info(f"[Scheduler] Ejecutando recordatorio: '{target}' (ID: {name})")
    now_str = datetime.now(timezone.utc).isoformat()
    
    try:
        # 1. Alerta por voz
        speak(f"Señor, recordatorio: {target}")
        
        # 2. Notificación push
        send_push_notification(
            title="Recordatorio de Jarvis",
            message=target,
            priority="high",
            tags=["bell", "reminder"]
        )
        
        # 3. Actualización de base de datos
        if interval > 0:
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()
            db_update_task_execution(name, last_run=now_str, last_result="success", next_run=next_run)
            logging.info(f"[Scheduler] Tarea periódica '{name}' actualizada. Próxima ejecución: {next_run}")
        else:
            db_delete_task(name)
            logging.info(f"[Scheduler] Tarea única '{name}' completada y eliminada.")
            
    except Exception as e:
        error_msg = str(e)
        logging.error(f"[Scheduler] Error ejecutando recordatorio '{name}': {error_msg}")
        
        # Actualizar con fallo
        if interval > 0:
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()
            db_update_task_execution(name, last_run=now_str, last_result="failed", last_error=error_msg, next_run=next_run)
        else:
            db_update_task_execution(name, last_run=now_str, last_result="failed", last_error=error_msg)

def scheduler_loop():
    """Bucle principal del planificador en segundo plano."""
    global _scheduler_running
    logging.info("[Scheduler] Bucle del planificador central iniciado.")
    
    while _scheduler_running:
        try:
            # Obtener todas las tareas habilitadas
            active_tasks = db_get_active_tasks()
            now = datetime.now(timezone.utc)
            
            for task in active_tasks:
                next_run_str = task["next_run"]
                if not next_run_str:
                    continue
                    
                try:
                    next_run = datetime.fromisoformat(next_run_str)
                except Exception as ex:
                    logging.error(f"[Scheduler] Error al parsear fecha de ejecución para '{task['name']}': {ex}")
                    continue
                    
                # Si la hora de ejecución ya pasó o se cumple ahora
                if now >= next_run:
                    # Marcar temporalmente in-place para evitar ejecuciones repetidas antes de que termine el hilo
                    # deshabilitándola o actualizando de inmediato en la base de datos
                    # Lo más simple y seguro es actualizar last_run inmediatamente a "running"
                    db_update_task_execution(task["name"], last_run=now.isoformat(), last_result="running")
                    
                    if task["task_type"] == "reminder":
                        # Lanzar en un hilo separado
                        t = threading.Thread(target=execute_reminder_task, args=(task,), daemon=True)
                        t.start()
                    else:
                        logging.warning(f"[Scheduler] Tipo de tarea no soportado en esta fase: '{task['task_type']}'")
                        db_delete_task(task["name"])
                        
            time.sleep(2.0) # Escanear base de datos cada 2 segundos
        except Exception as e:
            logging.error(f"[Scheduler] Error en el bucle principal: {e}")
            time.sleep(5.0)

def add_reminder(name: str, target: str, seconds_delay: int, interval_seconds: int = 0) -> bool:
    """
    Añade un nuevo recordatorio dinámico a la base de datos de forma persistente.
    """
    next_run = (datetime.now(timezone.utc) + timedelta(seconds=seconds_delay)).isoformat()
    # Guardar en SQLite (source="user", enabled=1 por defecto)
    return db_save_task(
        name=name,
        task_type="reminder",
        target=target,
        interval_seconds=interval_seconds,
        next_run=next_run,
        enabled=1
    )

def cancel_task(name: str) -> bool:
    """
    Cancela y elimina una tarea programada por su nombre único.
    """
    return db_delete_task(name)

def get_active_tasks() -> list:
    """
    Retorna la lista de tareas activas de la base de datos.
    """
    return db_get_active_tasks()

def start_scheduler():
    """Inicia el planificador central en segundo plano."""
    global _scheduler_running, _scheduler_thread
    if _scheduler_running:
        logging.info("[Scheduler] El planificador ya está en ejecución.")
        return
        
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True, name="JarvisSchedulerThread")
    _scheduler_thread.start()
    logging.info("[Scheduler] Planificador central iniciado con éxito.")

def stop_scheduler():
    """Detiene el planificador central en segundo plano."""
    global _scheduler_running
    if not _scheduler_running:
        logging.info("[Scheduler] El planificador ya estaba inactivo.")
        return
        
    _scheduler_running = False
    logging.info("[Scheduler] Planificador central detenido.")
