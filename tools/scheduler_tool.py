from langchain.tools import tool
from core.scheduler import add_reminder, cancel_task, get_active_tasks
from datetime import datetime

@tool("add_reminder")
def add_reminder_tool(name: str, target: str, seconds_delay: int, interval_seconds: int = 0) -> str:
    """
    Añade un recordatorio por voz y notificación push en el planificador de Jarvis.
    
    Parámetros:
    - name: Nombre identificador único de la tarea (usar minúsculas y guiones bajos, ej: 'reminder_reunion_staff').
    - target: El mensaje descriptivo del recordatorio (ej: 'Reunión de equipo').
    - seconds_delay: Retraso en segundos antes de la primera ejecución (ej: 60 para 1 minuto).
    - interval_seconds: Intervalo de repetición periódica en segundos (0 para ejecutarse solo una vez).
    """
    try:
        success = add_reminder(name, target, seconds_delay, interval_seconds)
        if success:
            period_str = f"cada {interval_seconds}s" if interval_seconds > 0 else "de ejecución única"
            return f"Recordatorio '{target}' programado con éxito para ejecutarse en {seconds_delay}s ({period_str}), señor."
        else:
            return "No se pudo guardar el recordatorio. Compruebe si el ID del recordatorio ya existe."
    except Exception as e:
        return f"Error al programar el recordatorio: {str(e)}"

@tool("list_reminders")
def list_reminders_tool() -> str:
    """
    Lista todos los recordatorios y tareas programadas activas en el planificador de Jarvis.
    """
    try:
        tasks = get_active_tasks()
        if not tasks:
            return "No hay tareas programadas activas, señor."
            
        formatted = []
        for t in tasks:
            try:
                dt = datetime.fromisoformat(t["next_run"])
                time_str = dt.astimezone().strftime("%d/%m/%Y a las %H:%M:%S")
            except Exception:
                time_str = t["next_run"]
                
            period_str = f" (Cada {t['interval_seconds']}s)" if t["interval_seconds"] > 0 else ""
            formatted.append(f"- '{t['target']}' [ID: {t['name']}] -> Próxima: {time_str}{period_str}")
            
        return "Lista de tareas programadas activas:\n" + "\n".join(formatted)
    except Exception as e:
        return f"Error al listar recordatorios: {str(e)}"

@tool("cancel_reminder")
def cancel_reminder_tool(name: str) -> str:
    """
    Cancela y elimina un recordatorio o tarea programada de Jarvis usando su nombre/ID único.
    """
    try:
        success = cancel_task(name)
        if success:
            return f"El recordatorio '{name}' ha sido cancelado y eliminado correctamente, señor."
        else:
            return f"No se encontró ninguna tarea programada con el ID '{name}', señor."
    except Exception as e:
        return f"Error al cancelar el recordatorio: {str(e)}"
