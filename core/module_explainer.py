"""
core/module_explainer.py — "Explícame este módulo".

Jarvis lee un fichero/módulo de tu propio repositorio y te explica cómo
funciona, sus responsabilidades y cómo encaja con el resto. A diferencia de
code_documenter.py (que detecta lo que falta por documentar), aquí se EXPLICA
un módulo existente.

El núcleo es puro y testeable: extracción de la estructura por AST (docstring,
imports, clases, funciones) y un resumen estructural en español que ya es útil
SIN LLM. Si hay modelo de código disponible, se enriquece con su explicación.
La resolución del módulo a partir de lo que pides es pura sobre una lista de
candidatos; la lectura de disco y la llamada al modelo se aíslan.
"""
import ast
import glob
import logging
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)

# Palabras de relleno al pedir "explícame el módulo de X".
_FILLER = {"explicame", "explica", "explicar", "el", "la", "modulo", "module",
           "fichero", "archivo", "de", "del", "este", "esta", "como", "funciona",
           "que", "hace", "core", "tools", "py", "punto"}


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _query_tokens(query: str):
    """Tokens significativos de la petición (sin relleno). Puro."""
    norm = _normalize(query).replace("_", " ")
    tokens = []
    for raw in norm.replace("/", " ").replace("\\", " ").split():
        tok = "".join(c for c in raw if c.isalnum())
        if tok and tok not in _FILLER and len(tok) >= 2:
            tokens.append(tok)
    return tokens


def resolve_module(query: str, candidates):
    """Mejor fichero candidato para la petición, o None. Puro.

    candidates: lista de rutas (str). Puntúa por solapamiento entre los tokens
    de la petición y las partes del nombre del fichero (separado por '_')."""
    tokens = _query_tokens(query)
    if not tokens:
        return None
    best = None
    best_score = 0
    for path in candidates:
        stem = _normalize(Path(path).stem)
        stem_parts = set(stem.split("_"))
        score = 0
        for tok in tokens:
            if tok == stem:
                score += 5
            elif tok in stem_parts:
                score += 3
            elif tok in stem or stem in tok:
                score += 1
        if score > best_score:
            best_score = score
            best = path
    return best if best_score >= 1 else None


def extract_structure(source: str) -> dict:
    """Estructura de un módulo Python a partir de su código fuente. Puro.

    Devuelve {doc, imports, functions:[{name,args,doc}], classes:[{name,doc,methods}]}."""
    structure = {"doc": None, "imports": [], "functions": [], "classes": [], "error": None}
    try:
        tree = ast.parse(source or "")
    except SyntaxError as e:
        structure["error"] = f"No pude parsear el módulo: {e}"
        return structure
    structure["doc"] = ast.get_docstring(tree)
    for node in tree.body:
        if isinstance(node, ast.Import):
            structure["imports"] += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            structure["imports"].append(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            structure["functions"].append({
                "name": node.name,
                "args": [a.arg for a in node.args.args],
                "doc": (doc.splitlines()[0].strip() if doc else None),
            })
        elif isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and not n.name.startswith("_")]
            structure["classes"].append({
                "name": node.name,
                "doc": (ast.get_docstring(node) or "").splitlines()[0].strip() or None,
                "methods": methods,
            })
    return structure


def _public(names):
    return [n for n in names if not n.startswith("_")]


def build_structural_summary(structure: dict, module_name: str) -> str:
    """Resumen en español de la estructura de un módulo (sin LLM). Puro."""
    if structure.get("error"):
        return f"Señor, {structure['error']}"
    parts = [f"Módulo {module_name}"]
    doc = structure.get("doc")
    if doc:
        first = doc.strip().splitlines()[0].strip()
        parts.append(first)
    classes = structure.get("classes") or []
    functions = structure.get("functions") or []
    pub_funcs = [f for f in functions if not f["name"].startswith("_")]
    bits = []
    if classes:
        nombres = ", ".join(c["name"] for c in classes[:4])
        bits.append(f"{len(classes)} clase(s) ({nombres})")
    if pub_funcs:
        nombres = ", ".join(f["name"] for f in pub_funcs[:5])
        bits.append(f"{len(pub_funcs)} función(es) pública(s) destacando {nombres}")
    if bits:
        parts.append("Contiene " + " y ".join(bits))
    if not classes and not pub_funcs:
        parts.append("No expone clases ni funciones públicas")
    return ". ".join(parts) + ", señor."


def build_explain_prompt(structure: dict, module_name: str, source: str) -> str:
    """Prompt para que el modelo de código explique el módulo. Puro."""
    return (
        "Eres Jarvis explicando a tu desarrollador uno de sus propios módulos en español, "
        "con tono Stark (claro, preciso, algo ingenioso). Explica: (1) la responsabilidad "
        "principal del módulo en 1-2 frases, (2) sus piezas clave (clases/funciones) y qué "
        "hace cada una, (3) cómo encaja con el resto del sistema. Sé conciso y estructurado.\n\n"
        f"Módulo: {module_name}\n"
        f"Resumen estructural: {build_structural_summary(structure, module_name)}\n\n"
        f"Código fuente:\n```python\n{source[:6000]}\n```"
    )


# ----------------------------------------------------------------------------
# Acceso a disco / modelo (aislado)
# ----------------------------------------------------------------------------
def _candidate_files():
    files = []
    for pattern in ("core/*.py", "tools/*.py"):
        files += [p for p in glob.glob(pattern) if not Path(p).name.startswith("__")]
    return files


def explain_module(query: str, use_llm: bool = True) -> str:
    """Explica el módulo pedido. Devuelve texto listo para voz/HUD."""
    path = resolve_module(query, _candidate_files())
    if not path:
        return ("No identifico a qué módulo se refiere, señor. Dígame su nombre, "
                "por ejemplo: \"explícame el módulo session_memory\".")
    try:
        source = Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"No pude leer el módulo {path}, señor: {e}"
    module_name = Path(path).as_posix()
    structure = extract_structure(source)
    summary = build_structural_summary(structure, module_name)
    if not use_llm or structure.get("error"):
        return summary
    try:
        from tools.model_delegate import ask_code_model
        prompt = build_explain_prompt(structure, module_name, source)
        explanation = ask_code_model.invoke(prompt) if hasattr(ask_code_model, "invoke") else ask_code_model(prompt)
        if explanation and str(explanation).strip():
            return f"Permítame guiarle por {module_name}, señor.\n\n{explanation}"
    except Exception as e:
        logger.warning(f"[ModuleExplainer] Falló la explicación con LLM: {e}")
    return summary
