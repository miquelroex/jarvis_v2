"""
core/github_report.py — Resumen de GitHub por voz (vía `gh`).

Sin abrir el navegador, Jarvis te da el parte del repositorio: PRs e issues
abiertos pendientes y el estado del último pipeline de CI. Usa el CLI `gh` (ya
instalado y autenticado).

build_github_summary es puro y testeable; las llamadas a `gh` se aíslan.
"""
import json
import logging
import subprocess

logger = logging.getLogger(__name__)


def _run_gh(args: list):
    """Ejecuta gh y devuelve (returncode, stdout). (1, '') si no está disponible."""
    try:
        res = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=20)
        return res.returncode, res.stdout
    except Exception as e:
        logger.warning(f"[GitHubReport] gh no disponible: {e}")
        return 1, ""


def _gh_json(args: list):
    """Ejecuta un comando gh con salida JSON y la parsea. None si falla."""
    code, out = _run_gh(args)
    if code != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


def _plural(n, sing, plur):
    return sing if n == 1 else plur


def build_github_summary(data: dict) -> str:
    """Construye el parte de GitHub a partir de los datos recolectados (puro)."""
    if not data.get("available", True):
        return "No he podido consultar GitHub, señor. Verifique que `gh` esté autenticado."

    parts = ["Parte de GitHub, señor."]

    prs = data.get("pr_count", 0)
    if prs:
        parts.append(f"{prs} {_plural(prs, 'pull request abierto', 'pull requests abiertos')} "
                     f"{_plural(prs, 'pendiente', 'pendientes')} de revisión.")
    else:
        parts.append("Sin pull requests abiertos.")

    issues = data.get("issue_count", 0)
    if issues:
        parts.append(f"{issues} {_plural(issues, 'issue abierta', 'issues abiertas')}.")

    ci = data.get("ci")
    if ci:
        title = ci.get("displayTitle", "")
        status = (ci.get("status") or "").lower()
        conclusion = (ci.get("conclusion") or "").lower()
        if status != "completed":
            parts.append("El último pipeline está en ejecución.")
        elif conclusion == "success":
            parts.append("El último pipeline está en verde.")
        elif conclusion == "failure":
            parts.append(f"Atención: el último pipeline está en ROJO ({title}).")
        elif conclusion:
            parts.append(f"El último pipeline terminó en estado {conclusion}.")

    if prs == 0 and issues == 0 and not ci:
        parts.append("Todo tranquilo, señor.")
    return " ".join(parts)


def _count(args):
    data = _gh_json(args)
    return len(data) if isinstance(data, list) else None


def get_github_summary() -> str:
    """Parte de GitHub con datos reales del repo actual."""
    pr = _count(["pr", "list", "--json", "number", "--limit", "50"])
    issue = _count(["issue", "list", "--json", "number", "--limit", "50"])
    ci_list = _gh_json(["run", "list", "--branch", "main", "--limit", "1",
                        "--json", "status,conclusion,displayTitle"])
    ci = ci_list[0] if isinstance(ci_list, list) and ci_list else None

    available = not (pr is None and issue is None and ci is None)
    return build_github_summary({
        "available": available,
        "pr_count": pr or 0,
        "issue_count": issue or 0,
        "ci": ci,
    })
