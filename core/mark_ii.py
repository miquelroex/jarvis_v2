"""
core/mark_ii.py — Protocolo "Mark II" (auto-mejora supervisada).

Jarvis propone una mejora a UN fichero de su propio código, la aplica en una RAMA
GIT AISLADA, valida con la suite de pruebas y:
  - si pasan -> deja el commit en la rama para que lo revises (no toca tu rama).
  - si fallan -> descarta los cambios y borra la rama.

Salvaguardas de seguridad:
  - Sólo edita ficheros dentro de una allowlist (JARVIS_MARKII_ALLOWED_DIRS).
  - Exige el árbol de trabajo limpio antes de empezar.
  - NUNCA hace push ni merge; NUNCA toca tu rama actual sin tu revisión.

Cada paso (git, tests, LLM, disco) se aísla y es mockeable; la orquestación se
prueba con mocks.
"""
import os
import re
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _slug(text: str, maxlen: int = 30) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:maxlen].strip("-") or "mejora")


def is_path_allowed(target: str, allowed_dirs) -> bool:
    """True si `target` (relativo al repo) está dentro de algún dir permitido (puro)."""
    if not target:
        return False
    norm = target.replace("\\", "/").lstrip("./")
    if ".." in norm.split("/"):
        return False
    for d in allowed_dirs:
        d = d.strip().replace("\\", "/").strip("/")
        if d and (norm == d or norm.startswith(d + "/")):
            return True
    return False


def _allowed_dirs() -> list:
    return [d for d in os.getenv("JARVIS_MARKII_ALLOWED_DIRS", "core,tools").split(",") if d.strip()]


def build_improvement_prompt(filename: str, content: str, instruction: str) -> str:
    """Prompt para que el modelo de código reescriba el fichero mejorado (puro)."""
    return (
        "Eres un ingeniero de software meticuloso. Mejora el siguiente fichero según la "
        "instrucción, MANTENIENDO la compatibilidad y sin romper su API pública ni los tests "
        "existentes. Devuelve ÚNICAMENTE el contenido COMPLETO del fichero resultante, sin "
        "explicaciones ni vallas de código.\n\n"
        f"FICHERO: {filename}\n\nINSTRUCCIÓN:\n{instruction}\n\n"
        f"CONTENIDO ACTUAL:\n{content}\n\nCONTENIDO MEJORADO COMPLETO:"
    )


def _strip_code_fences(text: str) -> str:
    """Quita vallas ```...``` si el modelo las añade pese a las instrucciones."""
    t = (text or "").strip()
    m = re.match(r"^```[a-zA-Z0-9_+-]*\n(.*)\n```$", t, re.DOTALL)
    return m.group(1) if m else t


def _run_git(args: list):
    """Ejecuta git en el repo. Devuelve (returncode, salida)."""
    try:
        res = subprocess.run(["git"] + args, cwd=str(PROJECT_ROOT),
                             capture_output=True, text=True, timeout=60)
        return res.returncode, (res.stdout + res.stderr)
    except Exception as e:
        return 1, str(e)


def _run_tests():
    """Ejecuta la suite. Devuelve (ok: bool, resumen: str)."""
    cmd = os.getenv("JARVIS_MARKII_TEST_CMD", "python -m pytest -q").split()
    try:
        res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=1800)
        lines = [l for l in (res.stdout or "").splitlines() if l.strip()]
        summary = lines[-1] if lines else "sin salida"
        return res.returncode == 0, summary
    except Exception as e:
        return False, f"error al ejecutar tests: {e}"


def _generate_improved(filename: str, content: str, instruction: str) -> str:
    from core.llm_factory import get_llm
    model = os.getenv("JARVIS_MODEL_CODE", "qwen/qwen3-coder")
    llm = get_llm(model_name=model, temperature=0.1)
    resp = llm.invoke(build_improvement_prompt(filename, content, instruction))
    return _strip_code_fences(getattr(resp, "content", str(resp)))


def run_mark_ii(target_file: str, instruction: str) -> str:
    """Aplica una mejora supervisada a `target_file` en una rama aislada."""
    target_file = (target_file or "").replace("\\", "/").strip()
    if not target_file or not instruction or not instruction.strip():
        return "Señor, necesito el fichero objetivo y la instrucción de mejora."

    if not is_path_allowed(target_file, _allowed_dirs()):
        return (f"Señor, por seguridad sólo puedo modificar ficheros dentro de "
                f"{', '.join(_allowed_dirs())}. '{target_file}' queda fuera.")

    abs_path = PROJECT_ROOT / target_file
    if not abs_path.is_file():
        return f"Señor, no encuentro el fichero {target_file}."

    # Árbol de trabajo limpio obligatorio.
    code, out = _run_git(["status", "--porcelain"])
    if out.strip():
        return ("Señor, hay cambios sin confirmar en el árbol de trabajo. "
                "Confírmelos o guárdelos antes de iniciar el Protocolo Mark II.")

    code, orig_branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    orig_branch = orig_branch.strip() or "main"

    from core.narration import narrate
    original_content = abs_path.read_text(encoding="utf-8")
    narrate("Analizando el fichero y generando la mejora con el modelo de código, señor…")
    improved = _generate_improved(target_file, original_content, instruction)
    if not improved.strip() or improved.strip() == original_content.strip():
        return "Señor, no he generado una mejora aplicable en esta ocasión."

    branch = f"markII/{_slug(instruction)}-{datetime.now().strftime('%H%M%S')}"
    code, out = _run_git(["checkout", "-b", branch])
    if code != 0:
        return f"Señor, no pude crear la rama de trabajo: {out.strip()[:200]}"

    narrate(f"Aislando los cambios en la rama {branch}…")
    try:
        abs_path.write_text(improved, encoding="utf-8")
        narrate("Ejecutando la suite de pruebas para validar la mejora…")
        ok, summary = _run_tests()
        if ok:
            _run_git(["add", target_file])
            _run_git(["commit", "-m", f"markII: {instruction[:72]}"])
            _run_git(["checkout", orig_branch])
            return (f"Mejora aplicada y validada en la rama {branch}, señor. "
                    f"Pruebas en verde ({summary}). Revísela cuando guste; no he tocado {orig_branch}.")
        else:
            _run_git(["checkout", "--", target_file])
            _run_git(["checkout", orig_branch])
            _run_git(["branch", "-D", branch])
            return (f"La mejora propuesta rompía las pruebas, señor ({summary}). "
                    f"He descartado los cambios; {orig_branch} permanece intacta.")
    except Exception as e:
        # Restaurar el estado pase lo que pase.
        _run_git(["checkout", "--", target_file])
        _run_git(["checkout", orig_branch])
        _run_git(["branch", "-D", branch])
        logger.error(f"[MarkII] Error durante la mejora: {e}")
        return f"Señor, ha ocurrido un imprevisto durante el Protocolo Mark II: {e}"
