import os
import logging
from langchain.tools import tool
from core.git_assistant import (
    generate_commit_message,
    generate_branch_changelog,
    generate_branch_summary,
    apply_git_commit
)

@tool
def git_diff_summary(staged: bool = True) -> str:
    """
    Analiza los cambios en el repositorio (staged por defecto) y genera un mensaje
    de commit sugerido siguiendo la convención de 'Conventional Commits'.
    """
    return generate_commit_message(staged=staged)

@tool
def git_branch_changelog(compare_branch: str = "main") -> str:
    """
    Genera un changelog detallado y estructurado en Markdown que resume las diferencias
    y commits de la rama actual en comparación con la rama especificada (por defecto 'main').
    """
    return generate_branch_changelog(compare_branch=compare_branch)

@tool
def git_branch_summary() -> str:
    """
    Obtiene un resumen estructurado del estado de la rama actual de git, listando los archivos
    modificados, rama activa y estado general del espacio de trabajo.
    """
    return generate_branch_summary()

@tool
def git_apply_commit(message: str) -> str:
    """
    Aplica un commit de Git en el repositorio local con el mensaje de confirmación provisto.
    Si JARVIS_SAFE_MODE está activo, solicita confirmación de seguridad antes de ejecutarlo.
    """
    safe_mode = os.getenv("JARVIS_SAFE_MODE", "True").lower() in ("true", "1", "yes")
    if safe_mode:
        from core.pending_actions import save_pending_action
        save_pending_action("git_commit", {"message": message})
        
        try:
            from core.telegram_bot import send_mfa_request
            send_mfa_request("command", {"command": f"git commit -m '{message}'"})
        except Exception as e:
            logging.error(f"[MFA] Error enviando solicitud MFA para commit: {e}")

        return (
            f"La creación del commit con el mensaje '{message}' requiere confirmación de seguridad. "
            "Por favor, diga 'confirma acción' o 'adelante' para autorizarlo."
        )
    else:
        return apply_git_commit(message)
