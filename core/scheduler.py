import time
import threading
import logging
import socket
import json
import hashlib
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from tools.voice import speak
from core.notifier import send_push_notification
from core.memory import (
    db_get_active_tasks,
    db_save_task,
    db_delete_task,
    db_update_task_execution
)

def is_private_ip(ip: str) -> bool:
    """Retorna True si la IP es privada (RFC 1918), loopback o link-local."""
    try:
        parts = [int(p) for p in ip.split('.')]
        if len(parts) != 4:
            return False
        # 127.0.0.0/8 (Loopback)
        if parts[0] == 127:
            return True
        # 10.0.0.0/8
        if parts[0] == 10:
            return True
        # 172.16.0.0/12
        if parts[0] == 172 and (16 <= parts[1] <= 31):
            return True
        # 192.168.0.0/16
        if parts[0] == 192 and parts[1] == 168:
            return True
        # 169.254.0.0/16 (Link-local)
        if parts[0] == 169 and parts[1] == 254:
            return True
        return False
    except Exception:
        return False

stop_event = threading.Event()
_scheduler_thread = None

def is_scheduler_running() -> bool:
    """Retorna True si el planificador está activo en segundo plano."""
    global _scheduler_thread
    return _scheduler_thread is not None and _scheduler_thread.is_alive()

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
        speak(f"Disculpe la interrupción, señor. Me he tomado la libertad de recordarle que: {target}")
        
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

def execute_url_monitor(task: dict):
    """
    Ejecuta el monitoreo de una URL descargando el contenido de forma segura,
    verificando cambios mediante hash SHA-256 y previniendo spam de alertas.
    """
    import json
    import socket
    import requests
    import hashlib
    from urllib.parse import urlparse
    
    name = task["name"]
    url = task["target"]
    interval = task["interval_seconds"]
    metadata_str = task["metadata"]
    
    # Cargar metadatos
    metadata = {}
    if metadata_str:
        try:
            metadata = json.loads(metadata_str)
        except Exception:
            pass
            
    last_hash = metadata.get("last_hash", "")
    alerted = metadata.get("alerted", False)
    allow_local_network = metadata.get("allow_local_network", False)
    
    logging.info(f"[Scheduler] Ejecutando monitor de URL: '{url}' (ID: {name})")
    now_str = datetime.now(timezone.utc).isoformat()
    
    # Si ya está alertado, evitamos descargas de red y solo actualizamos timestamps
    if alerted:
        logging.info(f"[Scheduler] Tarea '{name}' ya alertó sobre un cambio. Saltando petición de red.")
        if interval > 0:
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()
            db_update_task_execution(name, last_run=now_str, last_result="success", next_run=next_run)
        return
        
    try:
        # 1. Validar esquema
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Esquema de protocolo no permitido: {parsed.scheme}")
            
        # 2. Validar IP local
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("No se pudo extraer el hostname de la URL.")
            
        try:
            ip = socket.gethostbyname(hostname)
        except Exception as se:
            raise ValueError(f"Fallo de DNS al resolver '{hostname}': {se}")
            
        if is_private_ip(ip) and not allow_local_network:
            raise ValueError(f"Acceso bloqueado: la IP '{ip}' pertenece a la red local y la tarea no tiene permiso.")
            
        # 3. Realizar petición HTTP GET (timeout 5s, límite 1MB)
        # Usamos stream=True para leer el contenido de forma controlada y evitar descargas grandes
        response = requests.get(url, timeout=5, stream=True)
        response.raise_for_status()
        
        max_bytes = 1024 * 1024  # 1MB
        content_bytes = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                content_bytes.extend(chunk)
                if len(content_bytes) > max_bytes:
                    raise ValueError("El tamaño de la respuesta web excede el límite de 1MB permitido.")
                    
        # 4. Calcular SHA-256
        current_hash = hashlib.sha256(content_bytes).hexdigest()
        
        # 5. Comprobar si hay cambios
        change_detected = False
        if last_hash and current_hash != last_hash:
            change_detected = True
            
        # Actualizar metadatos
        metadata["last_hash"] = current_hash
        
        if change_detected:
            metadata["alerted"] = True
            # Notificaciones
            speak(f"Señor, mis sensores web registran una modificación en la página monitoreada: {name}. Sugiero revisar los detalles en el panel.")
            send_push_notification(
                title="Cambio Web Detectado",
                message=f"La página web monitoreada '{url}' ha cambiado.",
                priority="high",
                tags=["globe", "bell"]
            )
            logging.warning(f"[Scheduler] ¡Cambio detectado en '{url}' (ID: {name})!")
            
        # Guardar en base de datos
        new_metadata_str = json.dumps(metadata)
        if interval > 0:
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()
            db_update_task_execution(
                name,
                last_run=now_str,
                last_result="success",
                next_run=next_run,
                metadata=new_metadata_str
            )
        else:
            db_delete_task(name)
            
    except Exception as e:
        error_msg = str(e)
        logging.error(f"[Scheduler] Error monitoreando URL '{url}': {error_msg}")
        
        if interval > 0:
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()
            db_update_task_execution(
                name,
                last_run=now_str,
                last_result="failed",
                last_error=error_msg,
                next_run=next_run
            )
        else:
            db_update_task_execution(name, last_run=now_str, last_result="failed", last_error=error_msg)

def add_url_monitor(name: str, url: str, interval_seconds: int, allow_local_network: bool = False) -> str:
    """
    Añade un nuevo monitoreo de URL a la base de datos de forma persistente.
    Valida el esquema, la red local y los límites mínimos de intervalo.
    """
    from urllib.parse import urlparse
    import socket
    import json
    
    # 1. Validar esquema
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return f"Error: Protocolo '{parsed.scheme}' no permitido. Solo se permite http y https."
        hostname = parsed.hostname
        if not hostname:
            return "Error: No se pudo extraer el nombre de host de la URL."
    except Exception as e:
        return f"Error al analizar la URL: {e}"
        
    # 2. Forzar intervalo mínimo de 5 minutos (300 segundos)
    if interval_seconds < 300:
        logging.info(f"[Scheduler] Forzando intervalo de {name} a 300 segundos (mínimo permitido).")
        interval_seconds = 300
        
    # 3. Resolver IP para validar red local
    try:
        ip = socket.gethostbyname(hostname)
    except Exception as e:
        return f"Error: No se pudo resolver el host '{hostname}': {e}"
        
    is_local = is_private_ip(ip)
    
    if is_local:
        if not allow_local_network:
            return f"Error: No se permite monitorear URLs de la red local ({ip}) por seguridad."
        else:
            # Registrar como acción pendiente
            from core.pending_actions import save_pending_action
            pending_data = {
                "name": name,
                "url": url,
                "interval_seconds": interval_seconds
            }
            save_pending_action("url_monitor_add", pending_data)
            return (
                f"Confirmación requerida: La URL '{url}' apunta a la red local ({ip}). "
                "Para iniciar el monitoreo, debe confirmar la acción diciendo 'confirma acción' o 'adelante'."
            )
            
    # IP pública, se registra de forma directa
    now_str = datetime.now(timezone.utc).isoformat()
    metadata = json.dumps({"last_hash": "", "alerted": False, "allow_local_network": False})
    
    success = db_save_task(
        name=name,
        task_type="url_monitor",
        target=url,
        interval_seconds=interval_seconds,
        next_run=now_str,
        enabled=1,
        metadata=metadata
    )
    if success:
        return f"Monitoreo de URL '{url}' registrado con éxito. Se ejecutará cada {interval_seconds} segundos."
    else:
        return "Error: No se pudo guardar la tarea de monitoreo en la base de datos."

def scheduler_loop():
    """Bucle principal del planificador en segundo plano."""
    logging.info("[Scheduler] Bucle del planificador central iniciado.")
    
    while not stop_event.is_set():
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
                    db_update_task_execution(task["name"], last_run=now.isoformat(), last_result="running")
                    
                    if task["task_type"] == "reminder":
                        # Lanzar en un hilo separado
                        t = threading.Thread(target=execute_reminder_task, args=(task,), daemon=True)
                        t.start()
                    elif task["task_type"] == "url_monitor":
                        # Lanzar en un hilo separado
                        t = threading.Thread(target=execute_url_monitor, args=(task,), daemon=True)
                        t.start()
                    else:
                        logging.warning(f"[Scheduler] Tipo de tarea no soportado en esta fase: '{task['task_type']}'")
                        db_delete_task(task["name"])
                        
            if stop_event.wait(timeout=2.0):
                break
        except Exception as e:
            logging.error(f"[Scheduler] Error en el bucle principal: {e}")
            if stop_event.wait(timeout=5.0):
                break

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

def reactivate_url_monitor(target_query: str) -> str:
    """
    Reactiva un monitor de URL que ha sido silenciado (alerted=True) tras un cambio.
    Restablece el estado de alerta a False y programa la ejecución inmediata.
    """
    import json
    from core.memory import db_update_task_execution
    
    tasks = get_active_tasks()
    matched_tasks = [t for t in tasks if t["task_type"] == "url_monitor" and (
        target_query.lower() == t["name"].lower() or 
        target_query.lower() in t["target"].lower() or 
        target_query.lower() in t["name"].lower()
    )]
    
    if not matched_tasks:
        return f"Error: No se encontró ningún monitor de URL activo que coincida con '{target_query}'."
        
    if len(matched_tasks) > 1:
        return f"Error: Múltiples monitores coinciden con '{target_query}'. Especifique el ID exacto."
        
    task = matched_tasks[0]
    metadata = {}
    if task["metadata"]:
        try:
            metadata = json.loads(task["metadata"])
        except Exception:
            pass
            
    metadata["alerted"] = False
    new_metadata_str = json.dumps(metadata)
    
    now_str = datetime.now(timezone.utc).isoformat()
    success = db_update_task_execution(
        task["name"],
        last_run=now_str,
        last_result="pending_reactivation",
        next_run=now_str,
        metadata=new_metadata_str
    )
    if success:
        return f"Éxito: Se ha reactivado el monitoreo de '{task['target']}'."
    else:
        return f"Error: No se pudo actualizar la tarea en la base de datos para '{task['target']}'."

def get_active_tasks() -> list:
    """
    Retorna la lista de tareas activas de la base de datos.
    """
    return db_get_active_tasks()

def start_scheduler():
    """Inicia el planificador central en segundo plano. Es idempotente."""
    global _scheduler_thread
    
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logging.info("[Scheduler] El planificador ya está en ejecución.")
        return
        
    stop_event.clear()
    _scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True, name="JarvisSchedulerThread")
    _scheduler_thread.start()
    logging.info("[Scheduler] Planificador central iniciado con éxito.")

def stop_scheduler():
    """Detiene el planificador central en segundo plano de forma limpia."""
    global _scheduler_thread
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        logging.info("[Scheduler] El planificador ya estaba inactivo.")
        return
        
    stop_event.set()
    logging.info("[Scheduler] Planificador central detenido.")
