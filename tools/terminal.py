import os
import re
import json
import time
import subprocess
import logging
from pathlib import Path
from langchain.tools import tool
from core.pending_actions import save_pending_action, PENDING_ACTION_FILE

PENDING_COMMAND_FILE = PENDING_ACTION_FILE
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Lista de prefijos de comandos seguros que se permiten directamente
SAFE_COMMAND_PREFIXES = [
    "git status",
    "git diff",
    "git log",
    "python -m unittest",
    "pytest",
    "dir",
    "type"
]

# Lista negra de comandos del sistema destructivos o peligrosos
DANGEROUS_COMMANDS_REGEX = r"\b(del|rmdir|rd|format|shutdown|reboot|attrib|net|chkdsk|diskpart|reg|taskkill|sfc|sc|netsh|powershell|cmd)\b"

def is_command_safe(command: str) -> bool:
    """Verifica si el comando no contiene palabras del sistema prohibidas."""
    if re.search(DANGEROUS_COMMANDS_REGEX, command.lower()):
        return False
    return True

def is_command_in_allowlist(command: str) -> bool:
    """Verifica si el comando coincide con la allowlist de comandos seguros."""
    norm_cmd = command.strip().lower()
    for prefix in SAFE_COMMAND_PREFIXES:
        if norm_cmd.startswith(prefix):
            return True
    return False

def save_failed_command_log(command: str, stdout: str, stderr: str):
    """Guarda los detalles de un comando fallido en logs/last_exception.json."""
    try:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        data = {
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "timestamp": time.time()
        }
        Path("logs/last_exception.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logging.error(f"[Terminal Tool] Error al guardar log de excepción: {e}")

def execute_cmd(command: str) -> str:
    """Ejecuta el comando en el workspace de manera directa."""
    try:
        logging.info(f"Ejecutando comando en consola: {command}")
        res = subprocess.run(
            command,
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = ""
        if res.stdout:
            output += f"Salida:\n{res.stdout}\n"
        if res.stderr:
            output += f"Error/Advertencia:\n{res.stderr}\n"
        
        if not output:
            output = "El comando se ejecutó con éxito pero no devolvió ninguna salida."
            
        # Si el comando falló (código de retorno diferente de 0), intentar auto-diagnóstico
        if res.returncode != 0:
            # Registrar la última excepción/fallo para Log-to-Test Generator
            save_failed_command_log(command, res.stdout, res.stderr)
            try:
                from core.error_autofixer import diagnose_and_suggest_fix
                diagnosis = diagnose_and_suggest_fix(command, res.stdout, res.stderr)
                if diagnosis:
                    output += diagnosis
            except Exception as diag_err:
                logging.error(f"[Terminal Tool] Error al generar auto-diagnóstico: {diag_err}")
        else:
            # Si el comando tuvo éxito (código de retorno 0), registrar en el historial
            try:
                from core.macro_agent import log_terminal_command
                log_terminal_command(command)
            except Exception as log_err:
                logging.error(f"[Terminal Tool] Error al registrar comando exitoso: {log_err}")
                
        return output
    except subprocess.TimeoutExpired:
        return "Error: Tiempo de espera agotado (30 segundos)."
    except Exception as e:
        return f"Error al ejecutar comando: {str(e)}"


@tool
def run_terminal_command(command: str) -> str:
    """
    Executes a terminal command (like git status, pytest, etc.) within the workspace.
    Use this tool when the user asks to run tests, execute scripts, check git status, or similar terminal commands.
    """
    if not is_command_safe(command):
        return f"Error: El comando '{command}' fue bloqueado por seguridad por ser potencialmente destructivo o peligroso."

    # Si está en la allowlist, se ejecuta directamente
    if is_command_in_allowlist(command):
        return execute_cmd(command)

    # Detectar Modo Seguro para otros comandos
    safe_mode = os.getenv("JARVIS_SAFE_MODE", "True").lower() in ("true", "1", "yes")

    if safe_mode:
        from core.pending_actions import save_pending_action
        save_pending_action("terminal", {"command": command})
        
        try:
            from core.telegram_bot import send_mfa_request
            send_mfa_request("command", {"command": command})
        except Exception as e:
            logging.error(f"[MFA] Error enviando solicitud MFA para comando: {e}")

        return (
            f"El comando '{command}' requiere confirmación de seguridad para ejecutarse. "
            "Por favor, di 'confirma acción' o 'adelante' para autorizarlo."
        )
    else:
        # Modo Autónomo: Ejecutar directamente
        return execute_cmd(command)
