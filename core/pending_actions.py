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
        from tools.model_delegate import ask_openrouter_model
        return ask_openrouter_model(
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
        
    elif action_type == "tool_creation":
        from tools.dynamic_tool_creator import execute_create_tool
        name = data.get("name")
        description = data.get("description")
        python_code = data.get("python_code")
        if not name or not python_code:
            return "Datos insuficientes para la creación de la herramienta dinámica."
        return execute_create_tool(name, description, python_code)
        
    else:
        return f"Tipo de acción pendiente desconocida: {action_type}"
