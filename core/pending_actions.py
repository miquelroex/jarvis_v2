import json
from pathlib import Path

PENDING_ACTION_FILE = Path("logs/pending_action.json")

def save_pending_action(action_type: str, data: dict) -> None:
    """
    Guarda una acción pendiente en logs/pending_action.json y envía
    una solicitud de notificación o log.
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    payload = {
        "action_type": action_type,
        "data": data,
        **data # Compatibilidad con tests y cargadores antiguos (plano)
    }
    
    PENDING_ACTION_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def load_pending_action() -> dict:
    """
    Carga la acción pendiente actual si existe.
    """
    if not PENDING_ACTION_FILE.exists():
        return None
    try:
        return json.loads(PENDING_ACTION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None

def clear_pending_action() -> None:
    """
    Limpia la acción pendiente actual eliminando el archivo JSON.
    """
    if PENDING_ACTION_FILE.exists():
        try:
            PENDING_ACTION_FILE.unlink()
        except Exception:
            pass

def execute_pending_action() -> str:
    """
    Ejecuta la acción pendiente cargada según su tipo y limpia el estado.
    """
    action = load_pending_action()
    if not action:
        return "No hay ninguna acción pendiente de confirmar."
        
    action_type = action.get("action_type")
    data = action.get("data", {})
    
    # Limpiar antes de ejecutar para evitar ejecuciones duplicadas en caso de fallo
    clear_pending_action()
    
    if action_type == "model":
        from tools.model_delegate import ask_delegated_model
        return ask_delegated_model(
            tool_name=data.get("tool_name"),
            model_env=data.get("model_env"),
            fallback_model=data.get("model_name"),
            prompt=data.get("prompt"),
            require_confirmation=False
        )
        
    elif action_type == "terminal":
        from tools.terminal import execute_cmd
        command = data.get("command")
        if not command:
            return "No se especificó ningún comando de terminal en la acción pendiente."
        return execute_cmd(command)
        
    elif action_type == "file_write":
        from tools.filesystem import execute_write_file
        relative_path = data.get("relative_path")
        content = data.get("content")
        append = data.get("append", False)
        if not relative_path:
            return "No se especificó la ruta del archivo."
        return execute_write_file(relative_path, content, append)
        
    elif action_type == "git_commit":
        from core.git_assistant import apply_git_commit
        message = data.get("message")
        if not message:
            return "No se especificó ningún mensaje para el commit en la acción pendiente."
        return apply_git_commit(message)
        
    elif action_type == "apply_docstrings":
        from core.code_documenter import write_documenter_changes
        file_path = data.get("file_path")
        modified_code = data.get("modified_code")
        if not file_path or not modified_code:
            return "Datos insuficientes en la acción pendiente para aplicar la documentación."
        success = write_documenter_changes(file_path, modified_code)
        if success:
            return f"Excelente, señor. He insertado los docstrings generados en el archivo '{Path(file_path).name}' con éxito."
        else:
            return f"Señor, hubo un inconveniente al intentar escribir los cambios en '{Path(file_path).name}'."
            
    elif action_type == "tool_creation":
        from tools.dynamic_tool_creator import execute_create_tool
        name = data.get("name")
        description = data.get("description")
        python_code = data.get("python_code")
        if not name or not python_code:
            return "Datos insuficientes para la creación de la herramienta dinámica."
        return execute_create_tool(name, description, python_code)
        
    elif action_type == "url_monitor_add":
        from datetime import datetime, timezone
        from core.memory import db_save_task
        import json
        name = data.get("name")
        url = data.get("url")
        interval_seconds = data.get("interval_seconds")
        if not name or not url or not interval_seconds:
            return "Datos insuficientes en la acción pendiente para agregar el monitoreo de URL."
        
        now_str = datetime.now(timezone.utc).isoformat()
        metadata = json.dumps({"last_hash": "", "alerted": False, "allow_local_network": True})
        
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
            return f"Acción confirmada: Se ha iniciado el monitoreo de la URL local '{url}' cada {interval_seconds} segundos."
        else:
            return f"Error al guardar la tarea de monitoreo para la URL local '{url}'."
            
    else:
        return f"Tipo de acción pendiente desconocida: {action_type}"
