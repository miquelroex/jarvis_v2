"""
core/project_awareness.py — Conciencia del proyecto git activo.

Detecta el repositorio en el que trabajas y resume su estado (rama, último
commit, archivos sin confirmar) para que Jarvis responda con contexto.

Resolución del "proyecto activo":
  - Si defines JARVIS_PROJECTS_DIR, intenta resolver la carpeta del editor activo
    (ventana en primer plano) contra los repos de ese directorio base.
  - Si no, usa el propio repositorio de Jarvis.

Módulo ligero (stdlib); los imports de tools se hacen de forma perezosa.
"""
import os
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Aplicaciones (app_name de la ventana activa) consideradas editores de código.
_EDITORS = {"code", "cursor", "windsurf", "pycharm64", "pycharm", "devenv", "sublime_text", "rider64"}


def _run_git(args: list, cwd) -> str:
    """Ejecuta un comando git en cwd y devuelve stdout (o None si falla)."""
    try:
        res = subprocess.run(
            ["git"] + args, cwd=str(cwd),
            capture_output=True, text=True, timeout=8,
        )
        return res.stdout.strip() if res.returncode == 0 else None
    except Exception as e:
        logger.debug(f"[ProjectAwareness] git {args} falló en {cwd}: {e}")
        return None


def get_git_state(repo_dir) -> dict:
    """Estado de git de un directorio: {is_repo, repo_name, branch, last_commit, dirty_count}."""
    repo_dir = Path(repo_dir)
    state = {
        "is_repo": False,
        "repo_name": repo_dir.name,
        "branch": None,
        "last_commit": None,
        "dirty_count": 0,
    }
    top = _run_git(["rev-parse", "--show-toplevel"], repo_dir)
    if not top:
        return state
    state["is_repo"] = True
    state["repo_name"] = Path(top).name
    state["branch"] = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_dir)
    state["last_commit"] = _run_git(["log", "-1", "--pretty=%h %s"], repo_dir)
    status = _run_git(["status", "--porcelain"], repo_dir)
    state["dirty_count"] = len([l for l in status.splitlines() if l.strip()]) if status else 0
    return state


def _resolve_active_repo_dir() -> Path:
    """Best-effort: carpeta del proyecto que el usuario edita, o el repo de Jarvis."""
    base = os.getenv("JARVIS_PROJECTS_DIR", "").strip()
    if base:
        try:
            from tools.active_window import get_active_window_details
            details = get_active_window_details()
            app = (details.get("app_name") or "").lower()
            title = details.get("title") or ""
            if app in _EDITORS and title:
                # Heurística de título de editor: "archivo - carpeta - Visual Studio Code".
                parts = [p.strip() for p in title.split(" - ") if p.strip()]
                for name in reversed(parts):
                    candidate = Path(base) / name
                    if candidate.exists() and (candidate / ".git").exists():
                        return candidate
        except Exception as e:
            logger.debug(f"[ProjectAwareness] No se pudo resolver por ventana activa: {e}")
    return PROJECT_ROOT


def get_active_project() -> dict:
    """Estado de git del proyecto activo."""
    return get_git_state(_resolve_active_repo_dir())


def get_context_line() -> str:
    """Resumen de una línea del proyecto activo para inyectar en el contexto del LLM.

    Cadena vacía si no hay repositorio."""
    s = get_active_project()
    if not s["is_repo"]:
        return ""
    parts = [f"Proyecto activo: {s['repo_name']}"]
    if s["branch"]:
        parts.append(f"rama {s['branch']}")
    parts.append(f"{s['dirty_count']} cambios sin confirmar" if s["dirty_count"] else "sin cambios pendientes")
    if s["last_commit"]:
        parts.append(f"último commit: {s['last_commit']}")
    return " · ".join(parts)