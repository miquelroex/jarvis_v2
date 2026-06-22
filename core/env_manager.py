"""
core/env_manager.py — Auditoría del entorno (.env Manager).

Escanea el código en busca de variables de entorno referenciadas y las compara
con lo definido en .env para avisar de:
  - requeridas que faltan: referenciadas SIN valor por defecto en el código
    (os.getenv("X") sin segundo argumento, o os.environ["X"]) y ausentes en .env.
  - vacías: presentes en .env pero con valor vacío, estando referenciadas.
  - sin usar: definidas en .env pero no referenciadas en el código (config muerta).

Seguridad: nunca lee ni expone el VALOR de ninguna variable; solo nombres y si
el valor está vacío. Módulo ligero (stdlib), testeable de forma aislada.
"""
import os
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["core", "tools", "gui"]
SCAN_ROOT_FILES = ["main.py"]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"

# os.getenv("NAME") / getenv("NAME", ...) — el grupo 2 capta si hay default (coma).
_GETENV_RE = re.compile(r"""getenv\(\s*["']([A-Z][A-Z0-9_]*)["']\s*(,?)""")
# os.environ["NAME"] — acceso por subíndice: siempre requerido (lanza si falta).
_ENVIRON_SUB_RE = re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]*)["']\s*\]""")
# os.environ.get("NAME") — opcional (devuelve None por defecto).
_ENVIRON_GET_RE = re.compile(r"""os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]*)["']""")
# Cualquier token MAYÚSCULAS_SNAKE entre comillas: indica "uso" (capta refs dinámicas).
_QUOTED_UPPER_RE = re.compile(r"""["']([A-Z][A-Z0-9_]{2,})["']""")

# Este módulo se excluye del escaneo: su docstring contiene ejemplos como
# os.getenv("X") que no son referencias reales.
_SELF_FILE = "env_manager.py"


def _iter_python_files(roots=None):
    """Itera los archivos .py a escanear (dirs de SCAN_DIRS + archivos raíz)."""
    base = PROJECT_ROOT
    dirs = roots if roots is not None else SCAN_DIRS
    for d in dirs:
        dpath = base / d
        if dpath.exists():
            for f in dpath.rglob("*.py"):
                if f.name != _SELF_FILE:
                    yield f
    if roots is None:
        for f in SCAN_ROOT_FILES:
            fpath = base / f
            if fpath.exists():
                yield fpath


def scan_code_for_env_vars(roots=None) -> dict:
    """Escanea el código y clasifica las variables referenciadas.

    Returns:
        {"required": set, "optional": set, "literals": set}
        - required/optional: vistas en os.getenv/os.environ.
        - literals: cualquier nombre MAYÚSCULAS entre comillas (uso dinámico incl.).
    """
    required, optional, literals = set(), set(), set()
    for path in _iter_python_files(roots):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in _GETENV_RE.finditer(text):
            name, has_default = m.group(1), m.group(2)
            (optional if has_default == "," else required).add(name)
        for m in _ENVIRON_SUB_RE.finditer(text):
            required.add(m.group(1))
        for m in _ENVIRON_GET_RE.finditer(text):
            optional.add(m.group(1))
        for m in _QUOTED_UPPER_RE.finditer(text):
            literals.add(m.group(1))
    return {"required": required, "optional": optional, "literals": literals}


def parse_env_definitions(env_path=None) -> dict:
    """Lee los NOMBRES definidos en .env y si su valor está vacío.

    Nunca devuelve el valor en sí. Returns: {name: is_empty(bool)}.
    """
    path = Path(env_path) if env_path else DEFAULT_ENV_PATH
    defined = {}
    if not path.exists():
        return defined
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip()
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                defined[name] = (value.strip() == "")
    except Exception as e:
        logger.error(f"[EnvManager] Error al leer {path}: {e}")
    return defined


def audit_env(roots=None, env_path=None) -> dict:
    """Audita el entorno comparando código vs .env.

    Returns un reporte con status (healthy/advisory) y las listas de hallazgos.
    No incluye ningún valor de variable.
    """
    refs = scan_code_for_env_vars(roots)
    required = refs["required"]
    all_refs = required | refs["optional"]
    # Para "sin usar" consideramos también los usos dinámicos: una variable se
    # considera usada si su nombre aparece como literal en cualquier parte.
    used_anywhere = all_refs | refs["literals"]

    defined = parse_env_definitions(env_path)
    defined_names = set(defined)

    missing_required = sorted(n for n in required if n not in defined_names)
    empty = sorted(n for n in all_refs if defined.get(n) is True)
    unused = sorted(n for n in defined_names if n not in used_anywhere)

    status = "advisory" if (missing_required or empty) else "healthy"
    return {
        "status": status,
        "missing_required": missing_required,
        "empty": empty,
        "unused": unused,
        "referenced": len(all_refs),
        "defined": len(defined_names),
    }
