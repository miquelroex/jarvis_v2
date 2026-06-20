import os
import subprocess
import logging
from pathlib import Path
from tools.model_delegate import ask_code_model

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _run_git_cmd(args: list[str]) -> tuple[int, str, str]:
    """Ejecuta un comando de Git en el directorio raíz del proyecto de forma segura."""
    try:
        # En Windows, para evitar problemas con la resolución del comando 'git'
        # o variables de entorno, usamos shell=True pero pasando los argumentos serializados.
        # Aseguramos que la llamada se realiza en el directorio raíz del proyecto.
        res = subprocess.run(
            args,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            shell=True,
            timeout=15
        )
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        logging.error(f"[Git Assistant] Error al ejecutar comando {args}: {e}")
        return -1, "", str(e)

def get_git_branch() -> str:
    """Obtiene el nombre de la rama git actual."""
    code, stdout, stderr = _run_git_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if code == 0:
        return stdout.strip()
    return "unknown"

def get_git_status() -> str:
    """Obtiene el estado de git de forma simplificada."""
    code, stdout, stderr = _run_git_cmd(["git", "status", "--short"])
    if code == 0:
        return stdout.strip()
    return "Error al leer el estado de Git."

def get_git_diff(staged: bool = True) -> str:
    """Obtiene la diferencia de cambios (diff) de git."""
    args = ["git", "diff", "--cached"] if staged else ["git", "diff"]
    code, stdout, stderr = _run_git_cmd(args)
    if code == 0:
        return stdout
    return f"Error al obtener el diff: {stderr}"

def get_git_diff_stat(staged: bool = True) -> str:
    """Obtiene la telemetría resumida de líneas añadidas/eliminadas."""
    args = ["git", "diff", "--cached", "--stat"] if staged else ["git", "diff", "--stat"]
    code, stdout, stderr = _run_git_cmd(args)
    if code == 0:
        return stdout.strip()
    return ""

def get_git_log(compare_branch: str = "main") -> str:
    """Obtiene la lista de commits entre la rama de comparación y la rama actual."""
    code, stdout, stderr = _run_git_cmd(["git", "log", f"{compare_branch}..HEAD", "--oneline"])
    if code == 0:
        return stdout.strip()
    # Si la rama de comparación no existe o falla, intentar con un fallback a los últimos 10 commits
    code_fallback, stdout_fallback, _ = _run_git_cmd(["git", "log", "-n", "10", "--oneline"])
    if code_fallback == 0:
        return stdout_fallback.strip()
    return ""

def generate_commit_message(staged: bool = True) -> str:
    """Analiza los cambios en git y genera un mensaje Conventional Commit."""
    diff_content = get_git_diff(staged)
    if not diff_content.strip():
        # Si no hay staged, comprobar si hay unstaged
        if staged:
            diff_content = get_git_diff(staged=False)
            if not diff_content.strip():
                return "No he detectado ningún cambio pendiente de confirmación en el repositorio, señor."
            msg_prefix = "(Nota: Estos cambios no están en staging/index todavía, señor)\n\n"
        else:
            return "No he detectado ningún cambio pendiente de confirmación en el repositorio, señor."
    else:
        msg_prefix = ""

    # Truncar diff extremadamente largo si fuera necesario (límite razonable de tokens)
    if len(diff_content) > 15000:
        diff_content = diff_content[:15000] + "\n\n[... Diff truncado por tamaño excesivo ...]"

    prompt = f"""Genera un mensaje de commit profesional en inglés siguiendo estrictamente el estándar 'Conventional Commits' basándote en el siguiente diff de git.
El mensaje debe ser conciso (máximo 72 caracteres en la primera línea) y seguir el formato:
<tipo>(<ámbito>): <descripción corta en imperativo, presente, sin mayúscula inicial y sin punto final>

Tipos válidos: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.
Ejemplos:
- feat(voice): add Edge-TTS configuration
- fix(gui): resolve memory overflow issue

Devuelve ÚNICAMENTE el mensaje de commit sugerido en la primera línea. No agregues saludos, explicaciones, bloques de código markdown ni texto adicional.

Diff de Git:
\"\"\"
{diff_content}
\"\"\"
"""
    try:
        commit_msg = ask_code_model(prompt).strip()
        # Limpiar posibles comillas o markdown agregados por el modelo
        commit_msg = commit_msg.replace("`", "").replace("'", "").replace('"', "")
        # Si devuelve múltiples líneas, quedarse con la primera
        if "\n" in commit_msg:
            commit_msg = commit_msg.split("\n")[0].strip()
        return msg_prefix + commit_msg
    except Exception as e:
        logging.error(f"[Git Assistant] Error al llamar al modelo de código: {e}")
        return f"Error al generar el mensaje de commit: {str(e)}"

def generate_branch_summary() -> str:
    """Genera un resumen formal e inteligente del estado de la rama actual en Jarvis."""
    branch_name = get_git_branch()
    status_str = get_git_status()
    diff_stat = get_git_diff_stat(staged=True)
    if not diff_stat:
        diff_stat = get_git_diff_stat(staged=False)

    if not status_str.strip():
        return f"Señor, nos encontramos en la rama '{branch_name}'. El directorio de trabajo está completamente limpio. No hay cambios pendientes."

    prompt = f"""Actúa como JARVIS. Analiza la siguiente telemetría de Git para la rama '{branch_name}' y genera un resumen conciso y formal en español para tu señor (dirigiéndose a él como 'señor').
Dile en qué rama está trabajando, qué archivos se han modificado y cuál es el estado general del desarrollo de forma clara. Sé profesional, calmado y muy sintético (máximo 3-4 frases).

Estado de Git:
{status_str}

Resumen de cambios (diffstat):
{diff_stat}
"""
    try:
        summary = ask_code_model(prompt).strip()
        return summary
    except Exception as e:
        return f"Señor, nos encontramos en la rama '{branch_name}'. Modificaciones pendientes:\n{status_str}"

def generate_branch_changelog(compare_branch: str = "main") -> str:
    """Genera un changelog de los commits de la rama actual respecto a otra rama."""
    commits_list = get_git_log(compare_branch)
    if not commits_list.strip():
        return f"No he detectado nuevos commits en esta rama comparado con '{compare_branch}', señor."

    prompt = f"""Actúa como JARVIS. Genera un changelog elegante y estructurado en Markdown basándose en la siguiente lista de commits de Git (que están en formato oneline) entre la rama '{compare_branch}' y la actual.
Dirígete a tu señor formalmente en español. Agrupa los cambios por categorías lógicas (ej. Funcionalidades, Correcciones, Mantenimiento) y describe brevemente el progreso realizado en esta rama.

Lista de commits:
{commits_list}
"""
    try:
        changelog = ask_code_model(prompt).strip()
        return changelog
    except Exception as e:
        return f"Señor, aquí tiene la lista de commits cruda desde '{compare_branch}':\n\n{commits_list}"

def apply_git_commit(message: str) -> str:
    """Aplica un commit con el mensaje dado."""
    if not message.strip():
        return "Señor, no se puede realizar un commit con un mensaje vacío."
    
    # Comprobar si hay cambios en staging para hacer commit
    staged_diff = get_git_diff(staged=True)
    if not staged_diff.strip():
        return "Señor, no hay cambios en staging para confirmar. Por favor, añada archivos con 'git add' primero."

    code, stdout, stderr = _run_git_cmd(["git", "commit", "-m", message])
    if code == 0:
        return f"Excelente, señor. He registrado el commit con éxito.\nDetalle de salida:\n{stdout.strip()}"
    return f"Señor, he encontrado un obstáculo al aplicar el commit:\n{stderr.strip()}"
