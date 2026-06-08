import os
from datetime import datetime
from pathlib import Path

def log_model_usage(tool_name: str, model_name: str, prompt: str) -> None:
    """
    Registra el uso de modelos en el archivo logs/model_usage.log
    con marca de tiempo, herramienta/rol, modelo y un extracto corto del prompt.
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    short_prompt = prompt.replace("\n", " ")[:120]

    with open(logs_dir / "model_usage.log", "a", encoding="utf-8") as file:
        file.write(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"{tool_name} | {model_name} | {short_prompt}\n"
        )

    # Emitir evento de log a la GUI en tiempo real
    try:
        from gui.app import socketio, jarvis_state
        jarvis_state["model"] = model_name
        socketio.emit("new_model_log", {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tool_name": tool_name,
            "model_name": model_name,
            "prompt": short_prompt
        })
        socketio.emit('state_update', jarvis_state)
    except Exception:
        pass
