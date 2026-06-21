import os
import webbrowser
import unicodedata
import re
from datetime import datetime

from tools.browser import open_website
from tools.launcher import open_windows_app
from tools.time import get_time
from tools.date import get_date

def normalize_text(text: str) -> str:
    """Normaliza el texto quitando acentos, convirtiendo a minúsculas y limpiando espacios."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text

def handle_fast_command(command: str):
    """
    Comprueba si el comando introducido coincide con una orden local rápida
    (abrir navegador, aplicaciones de Windows, preguntar la hora/fecha).
    Retorna la respuesta de Jarvis si se maneja localmente, o None si debe ir al agente.
    """
    text = normalize_text(command)

    # --- Comandos rápidos de Memoria Persistente ---
    from core.memory import save_memory, search_memories, delete_memory_by_content, get_all_memories

    # 1. Guardar recuerdos
    match_save_pref = None
    for pref in ["recuerda que ", "recuerda ", "guardar en memoria "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            match_save_pref = pref
            break
    if match_save_pref is not None:
        content_to_save = command[len(match_save_pref):].strip()
        if content_to_save:
            saved = save_memory(content_to_save, category="preference", source="fast_command")
            if saved:
                return f"Entendido, señor. He guardado en mi memoria: {content_to_save}."
            else:
                return f"Señor, ese recuerdo ya estaba registrado en mi memoria."
        return "Señor, ¿qué es lo que desea que recuerde?"

    # 2. Olvidar recuerdos
    match_delete_pref = None
    for pref in ["olvida que ", "olvida ", "borra de tu memoria "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            match_delete_pref = pref
            break
    if match_delete_pref is not None:
        content_to_delete = command[len(match_delete_pref):].strip()
        if content_to_delete:
            deleted = delete_memory_by_content(content_to_delete)
            if deleted:
                return f"Entendido, señor. He olvidado lo relacionado con: {content_to_delete}."
            else:
                return f"No he encontrado ningún recuerdo relacionado con '{content_to_delete}', señor."
        return "Señor, ¿qué recuerdo desea que olvide?"

    # 3. Consultar recuerdos
    # Consulta general
    if text == "que recuerdas" or text == "dime mis recuerdos":
        mems = get_all_memories(limit=20)
        if mems:
            formatted = "\n".join(f"- {m['content']}" for m in mems)
            return f"Esto es lo que recuerdo, señor:\n{formatted}"
        return "No tengo recuerdos guardados por ahora, señor."

    # Consulta específica
    match_query_pref = None
    for pref in ["que recuerdas de ", "que recuerdas sobre "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            match_query_pref = pref
            break
    if match_query_pref is not None:
        query_text = command[len(match_query_pref):].strip()
        if query_text:
            matches = search_memories(query_text)
            if matches:
                formatted = "\n".join(f"- {m['content']}" for m in matches)
                return f"Recuerdo lo siguiente sobre '{query_text}', señor:\n{formatted}"
            return f"No tengo recuerdos relacionados con '{query_text}', señor."
        return "Señor, ¿de qué desea que haga memoria?"


    # --- Comandos rápidos del Centinela de Pruebas ---
    from core.test_watcher import start_test_watcher, stop_test_watcher, is_watcher_running, get_watcher_status
    
    # Activar
    activate_keywords = [
        "activa el centinela de pruebas", "activar centinela de pruebas", 
        "iniciar centinela", "activa el watcher de tests", "iniciar watcher de tests"
    ]
    if any(kw in text for kw in activate_keywords):
        if is_watcher_running():
            return "Señor, el centinela de pruebas ya está activo en segundo plano."
        start_test_watcher(force=True)
        return "Entendido, señor. He activado el centinela de pruebas en segundo plano."
        
    # Desactivar
    deactivate_keywords = [
        "desactiva el centinela de pruebas", "desactivar centinela de pruebas", 
        "detener centinela", "desactiva el watcher de tests", "detener watcher de tests"
    ]
    if any(kw in text for kw in deactivate_keywords):
        if not is_watcher_running():
            return "Señor, el centinela de pruebas ya estaba inactivo."
        stop_test_watcher()
        return "Entendido, señor. He desactivado el centinela de pruebas."
        
    # Estado
    status_keywords = [
        "estado del centinela de pruebas", "estado del centinela", 
        "estado del watcher", "como estan los tests", "situacion de los tests"
    ]
    if any(kw in text for kw in status_keywords):
        status = get_watcher_status()
        running_str = "activo" if status["running"] else "inactivo"
        last_run = status["last_run"]
        
        resp = f"El centinela de pruebas se encuentra actualmente {running_str}, señor.\n"
        if last_run["last_run_time"]:
            time_str = datetime.fromtimestamp(last_run["last_run_time"]).strftime("%H:%M:%S")
            outcome = "exitoso" if last_run["last_success"] else "fallido"
            resp += f"Última comprobación: {time_str} ({last_run['last_test_module']}) -> Estado: {outcome}."
        else:
            resp += "Aún no se ha realizado ninguna comprobación de cambios."
        return resp


    # --- Comando rápido: estado de los servicios locales ---
    services_status_keywords = [
        "estado de los servicios", "estado de servicios",
        "estado de los servicios locales", "como estan los servicios",
        "que servicios estan activos", "informe de servicios"
    ]
    if any(kw in text for kw in services_status_keywords):
        from core.services import get_services_status
        status = get_services_status()
        running = [name for name, st in status.items() if st == "running"]
        stopped = [name for name, st in status.items() if st == "stopped"]
        disabled = [name for name, st in status.items() if st == "disabled"]

        def _pretty(name):
            return name.replace("_", " ")

        resp = (
            f"Señor, informe de servicios: {len(running)} activos, "
            f"{len(stopped)} detenidos y {len(disabled)} desactivados."
        )
        if running:
            resp += "\nActivos: " + ", ".join(_pretty(s) for s in running) + "."
        if stopped:
            resp += "\nDetenidos: " + ", ".join(_pretty(s) for s in stopped) + "."
        return resp


    # --- Comando rápido: resumen del día (Daily Digest) ---
    digest_keywords = [
        "resumen del dia", "resumen de hoy", "que he hecho hoy",
        "dame el resumen del dia", "informe del dia", "resumen diario"
    ]
    if any(kw in text for kw in digest_keywords):
        from core.daily_digest import generate_daily_digest
        try:
            return generate_daily_digest()
        except Exception as e:
            return f"Lo siento, señor, no pude generar el resumen del día: {e}"


    # --- Comandos rápidos del Planificador de Tareas ---
    # 1. Crear recordatorio
    match_reminder = re.search(r"\b(en|cada)\s+(\d+)\s+(segundo|segundos|seg|s|minuto|minutos|min|m|hora|horas|h)\b", text)
    if match_reminder and (text.startswith("recuerdame ") or text.startswith("recuerda ")):
        prefix_len = 11 if text.startswith("recuerdame ") else 9
        match_start = match_reminder.start()
        reminder_text = command[prefix_len:match_start].strip()
        
        # Limpiar conectores iniciales comunes ("que", "a", "de")
        reminder_norm = normalize_text(reminder_text)
        if reminder_norm.startswith("que "):
            reminder_text = reminder_text[4:].strip()
        elif reminder_norm.startswith("de "):
            reminder_text = reminder_text[3:].strip()
        elif reminder_norm.startswith("a "):
            reminder_text = reminder_text[2:].strip()
            
        qty = int(match_reminder.group(2))
        unit = match_reminder.group(3)
        multiplier = 1
        if "min" in unit or unit == "m":
            multiplier = 60
        elif "hor" in unit or unit == "h":
            multiplier = 3600
            
        delay_seconds = qty * multiplier
        is_periodic = (match_reminder.group(1) == "cada")
        interval_seconds = delay_seconds if is_periodic else 0
        
        if reminder_text:
            import uuid
            # Generar un ID único amigable para la tarea
            safe_text = re.sub(r"[^a-zA-Z0-9_]", "", normalize_text(reminder_text))[:20]
            task_name = f"reminder_{safe_text}_{uuid.uuid4().hex[:6]}"
            
            from core.scheduler import add_reminder
            success = add_reminder(task_name, reminder_text, delay_seconds, interval_seconds)
            if success:
                period_str = f"cada {qty} {unit}" if is_periodic else f"en {qty} {unit}"
                return f"Entendido, señor. He programado el recordatorio: '{reminder_text}' para ejecutarse {period_str}."
            else:
                return "Lo siento, señor. Hubo un problema al guardar el recordatorio."

    # 2. Listar recordatorios
    list_keywords = ["lista las tareas", "que recordatorios tienes", "dime mis tareas", "dime mis recordatorios", "ver recordatorios"]
    if any(kw in text for kw in list_keywords):
        from core.scheduler import get_active_tasks
        tasks = get_active_tasks()
        if not tasks:
            return "No tiene ningún recordatorio programado, señor."
            
        formatted = []
        for t in tasks:
            try:
                # next_run es una fecha en formato ISO UTC. La mostramos amigable.
                dt = datetime.fromisoformat(t["next_run"])
                # Local time formatting
                time_str = dt.astimezone().strftime("%d/%m/%Y a las %H:%M:%S")
            except Exception:
                time_str = t["next_run"]
                
            period_str = f" (Cada {t['interval_seconds']}s)" if t["interval_seconds"] > 0 else ""
            formatted.append(f"- '{t['target']}' (ID: {t['name']}) -> Próxima: {time_str}{period_str}")
        return "Señor, estas son las tareas programadas activas:\n" + "\n".join(formatted)

    # 3. Cancelar recordatorio
    cancel_pref = None
    for pref in ["cancela la tarea ", "elimina el recordatorio ", "olvida el recordatorio ", "borra el recordatorio ", "cancela el recordatorio "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            cancel_pref = pref
            break
    if cancel_pref is not None:
        task_query = command[len(cancel_pref):].strip()
        if task_query:
            from core.scheduler import cancel_task, get_active_tasks
            # Buscar por ID exacto primero
            deleted = cancel_task(task_query)
            if deleted:
                return f"Entendido, señor. He cancelado y eliminado la tarea programada '{task_query}'."
                
            # Si no coincide el ID exacto, buscar coincidencias en el ID o en el contenido (target)
            tasks = get_active_tasks()
            matched_tasks = [t for t in tasks if task_query.lower() in t["name"].lower() or task_query.lower() in t["target"].lower()]
            if len(matched_tasks) == 1:
                cancel_task(matched_tasks[0]["name"])
                return f"Entendido, señor. He cancelado el recordatorio '{matched_tasks[0]['target']}'."
            elif len(matched_tasks) > 1:
                return f"Señor, encontré múltiples recordatorios que coinciden con '{task_query}'. Por favor, especifique el ID exacto."
                
            return f"No encontré ningún recordatorio o tarea programada que coincida con '{task_query}', señor."
        return "Señor, ¿qué recordatorio desea que cancele?"

    # --- Comandos del Monitor de URLs (Fase 2) ---
    # 1. Crear monitor de URL
    match_monitor = re.search(r"\b(monitorea|vigila)\s+(\S+)\s+cada\s+(\d+)\s+(minuto|minutos|min|m|hora|horas|h)\b", text)
    if match_monitor:
        # Usar la posición del match para extraer la URL del comando original y preservar mayúsculas/minúsculas
        start, end = match_monitor.span(2)
        url_text = command[start:end].strip()
        if not url_text.startswith(("http://", "https://")):
            url_text = "https://" + url_text
            
        qty = int(match_monitor.group(3))
        unit = match_monitor.group(4)
        multiplier = 60
        if "hor" in unit or unit == "h":
            multiplier = 3600
        interval_seconds = qty * multiplier
        
        import uuid
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url_text)
            host_clean = re.sub(r"[^a-zA-Z0-9_]", "", parsed.netloc.replace(".", "_"))[:20]
        except Exception:
            host_clean = "site"
        task_name = f"monitor_{host_clean}_{uuid.uuid4().hex[:6]}"
        
        from core.scheduler import add_url_monitor
        res_msg = add_url_monitor(task_name, url_text, interval_seconds, allow_local_network=True)
        return res_msg

    # 2. Reactivar monitor de URL (limpiar alerta)
    reactivate_pref = None
    for pref in ["reactiva el monitoreo de ", "reactiva el monitor de ", "limpia la alerta de ", "reactivar monitoreo de "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            reactivate_pref = pref
            break
            
    if reactivate_pref is not None:
        target_query = command[len(reactivate_pref):].strip()
        if target_query:
            from core.scheduler import reactivate_url_monitor
            res = reactivate_url_monitor(target_query)
            if res.startswith("Éxito:"):
                return f"Entendido, señor. {res[7:]}"
            else:
                return f"Señor, {res}"
        return "Señor, ¿qué monitoreo de URL desea reactivar?"

    # --- Comandos locales estándar ---
    websites = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
        "chatgpt": "https://chatgpt.com",
        "whatsapp": "https://web.whatsapp.com",
    }

    apps = {
        "calculadora": "calc",
        "bloc de notas": "notepad",
        "notepad": "notepad",
        "explorador": "explorer",
        "archivos": "explorer",
        "chrome": "chrome",
        "spotify": "spotify",
    }

    for name, url in websites.items():
        if f"abre {name}" in text or f"abrir {name}" in text:
            open_website.invoke({"url": url})
            return f"Abriendo {name}, señor."

    for name, executable in apps.items():
        if f"abre {name}" in text or f"abrir {name}" in text:
            open_windows_app.invoke({"app_executable": executable})
            return f"Abriendo {name}, señor."

    if "que hora es" in text or "dime la hora" in text:
        res = get_time.invoke({})
        # Extraer la hora en formato HH:MM
        match = re.search(r"(\d{2}:\d{2})", res)
        if match:
            return f"Son las {match.group(1)}, señor."
        now = datetime.now()
        return f"Son las {now.hour:02d}:{now.minute:02d}, señor."

    if "que dia es" in text or "fecha de hoy" in text or "que fecha es" in text:
        res = get_date.invoke({})
        return f"Hoy es {res}."

    # --- Comandos Rápidos del Asistente Git Inteligente ---
    # 1. Resumen de rama / branch
    branch_keywords = [
        "resumen de rama", "como esta mi rama", "estado de la rama", 
        "resumen de branch", "estado de branch", "resumen de git"
    ]
    if any(kw in text for kw in branch_keywords):
        from core.git_assistant import generate_branch_summary
        return generate_branch_summary()

    # 2. Generar mensaje de commit / proponer commit
    commit_keywords = [
        "genera commit", "haz commit", "crea un mensaje de commit", 
        "sugiere un commit", "genera un mensaje de commit", "crear commit",
        "crea mensaje de commit"
    ]
    if any(kw in text for kw in commit_keywords):
        from core.git_assistant import generate_commit_message
        commit_msg = generate_commit_message(staged=True)
        if commit_msg.startswith("No he detectado") or commit_msg.startswith("Error"):
            return commit_msg
        
        # Guardar en acciones pendientes para confirmación directa
        from core.pending_actions import save_pending_action
        save_pending_action("git_commit", {"message": commit_msg})
        
        return (
            f"Señor, he analizado los cambios en staging y le sugiero el siguiente mensaje de commit:\n\n"
            f"`{commit_msg}`\n\n"
            f"Para aplicarlo de inmediato, responda con 'confirma acción' o 'adelante'."
        )

    # 3. Generar changelog
    changelog_keywords = ["crea un changelog", "generar changelog", "crear changelog", "changelog de la rama"]
    if any(kw in text for kw in changelog_keywords):
        from core.git_assistant import generate_branch_changelog
        return generate_branch_changelog(compare_branch="main")

    # Resumen nocturno / diario (Daily Digest)
    if ("resumen del dia" in text or "resumen de hoy" in text
            or "resumen nocturno" in text or "como ha ido el dia" in text):
        from core.daily_digest import generate_daily_digest
        return generate_daily_digest()

    return None
