"""
core/resume_context.py — "¿En qué estaba?" (Reanudar Contexto).

Al volver, Jarvis retoma tu última sesión de trabajo cruzando tres fuentes ya
existentes: el estado git del proyecto activo (project_awareness), los ficheros
que tenías a medias (git status) y tu actividad principal del día
(productivity). "Retomamos donde lo dejó, señor: el proyecto X, rama Y…".

El parseo de los ficheros cambiados y la composición del mensaje son funciones
PURAS y testeables; la lectura de git/productividad se aísla.
"""
import logging

logger = logging.getLogger(__name__)


def changed_files_from_status(porcelain: str, limit: int = 3):
    """Ficheros (rutas) de una salida `git status --porcelain`, sin repetir. Puro.

    Maneja renombrados ("R  old -> new" se queda con el destino). Devuelve como
    mucho `limit` rutas, en el orden en que aparecen."""
    files = []
    seen = set()
    for line in (porcelain or "").splitlines():
        line = line.rstrip()
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:  # renombrado: nos quedamos con el destino
            path = path.split(" -> ", 1)[1].strip()
        path = path.strip('"')
        if path and path not in seen:
            seen.add(path)
            files.append(path)
        if len(files) >= limit:
            break
    return files


def _basename(path: str) -> str:
    """Nombre de fichero de una ruta (puro, sin tocar el disco)."""
    return path.replace("\\", "/").rstrip("/").split("/")[-1] or path


def top_activity(tally: dict):
    """Etiqueta con más tiempo imputado hoy, ignorando 'Otros' (puro). None si vacío."""
    candidates = {k: v for k, v in (tally or {}).items() if k and k != "Otros"}
    if not candidates:
        return None
    return max(candidates.items(), key=lambda kv: kv[1])[0]


def build_resume(repo_name=None, branch=None, last_commit=None,
                 changed_files=None, activity=None) -> str:
    """Compone la frase de reanudación a partir de las señales disponibles. Puro."""
    if not repo_name and not changed_files and not activity:
        return ("No tengo aún un contexto de trabajo claro, señor. "
                "En cuanto se ponga manos a la obra, tomaré nota.")
    parts = ["Retomamos donde lo dejó, señor"]
    if repo_name:
        proj = f"el proyecto {repo_name}"
        if branch:
            proj += f", rama {branch}"
        parts.append(proj)
    if changed_files:
        nombres = ", ".join(_basename(f) for f in changed_files)
        verbo = "el archivo" if len(changed_files) == 1 else "los archivos"
        parts.append(f"tenía a medias {verbo} {nombres}")
    if activity:
        parts.append(f"su foco principal era {activity}")
    frase = ". ".join(parts) + "."
    if last_commit:
        frase += f" Su último commit: {last_commit}."
    return frase


# ----------------------------------------------------------------------------
# Recolección de datos (aislada)
# ----------------------------------------------------------------------------
def _gather():
    """Reúne (repo_name, branch, last_commit, changed_files, activity) del entorno."""
    repo_name = branch = last_commit = None
    changed_files = []
    activity = None
    try:
        from core.project_awareness import get_active_project, _resolve_active_repo_dir, _run_git
        state = get_active_project()
        if state.get("is_repo"):
            repo_name = state.get("repo_name")
            branch = state.get("branch")
            last_commit = state.get("last_commit")
            porcelain = _run_git(["status", "--porcelain"], _resolve_active_repo_dir())
            changed_files = changed_files_from_status(porcelain or "")
    except Exception as e:
        logger.debug(f"[ResumeContext] No se pudo leer el estado del proyecto: {e}")
    try:
        from core.productivity import _load_today
        activity = top_activity(_load_today())
    except Exception as e:
        logger.debug(f"[ResumeContext] No se pudo leer la productividad: {e}")
    return repo_name, branch, last_commit, changed_files, activity


def get_resume_context() -> str:
    """Frase hablada para retomar la última sesión de trabajo."""
    repo_name, branch, last_commit, changed_files, activity = _gather()
    return build_resume(repo_name, branch, last_commit, changed_files, activity)
