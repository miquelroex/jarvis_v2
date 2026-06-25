"""
core/architecture_graph.py — Sala de Hologramas (Explorador de Arquitectura 3D).

Analiza el código del proyecto con AST y construye un grafo de dependencias entre
módulos locales (quién importa a quién), con el tamaño de cada nodo según su número
de definiciones (clases/funciones). La GUI lo proyecta como una constelación 3D
de partículas y enlaces de luz (three.js).

La lógica de análisis es pura y testeable (trabaja sobre {módulo: código}); el
acceso al disco y la emisión a la GUI se aíslan.
"""
import os
import ast
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Paquetes del proyecto que se escanean (código propio, sin dependencias externas).
SCAN_DIRS = ("core", "tools", "gui")


def _module_name_from_path(path: str, root: str) -> str:
    """Convierte una ruta de fichero .py en su nombre de módulo punteado."""
    rel = os.path.relpath(path, root).replace("\\", "/")
    if rel.endswith(".py"):
        rel = rel[:-3]
    if rel.endswith("/__init__"):
        rel = rel[:-len("/__init__")]
    return rel.replace("/", ".")


def _count_defs(source: str) -> int:
    """Número de funciones/clases de nivel definido (tamaño del nodo)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    return sum(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for n in ast.walk(tree)
    )


def _extract_imports(source: str, local_modules) -> set:
    """Devuelve el conjunto de módulos LOCALES importados por `source` (puro)."""
    out = set()
    local_modules = set(local_modules)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out

    def _match(name):
        if not name:
            return
        # Coincidencia exacta o por el prefijo de módulo local más largo.
        if name in local_modules:
            out.add(name)
            return
        parts = name.split(".")
        for i in range(len(parts), 0, -1):
            cand = ".".join(parts[:i])
            if cand in local_modules:
                out.add(cand)
                return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _match(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # Sólo imports absolutos de módulos locales (nivel 0).
            if node.level == 0 and node.module:
                _match(node.module)
    return out


def build_graph(files: dict) -> dict:
    """Construye {nodes, edges} a partir de {nombre_modulo: codigo_fuente} (puro)."""
    local_modules = set(files.keys())
    nodes = []
    edges = []
    for name in sorted(files.keys()):
        source = files[name]
        nodes.append({
            "id": name,
            "label": name,
            "group": name.split(".")[0],
            "size": _count_defs(source),
        })
        for dep in sorted(_extract_imports(source, local_modules)):
            if dep != name:
                edges.append({"source": name, "target": dep})
    return {"nodes": nodes, "edges": edges}


def _read_project_files(root: str = None) -> dict:
    """Lee los .py de los paquetes del proyecto -> {nombre_modulo: codigo}."""
    root = root or PROJECT_ROOT
    files = {}
    for d in SCAN_DIRS:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, filenames in os.walk(base):
            if "__pycache__" in dirpath:
                continue
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        files[_module_name_from_path(path, root)] = f.read()
                except Exception as e:
                    logger.warning(f"[ArchGraph] No se pudo leer {path}: {e}")
    return files


def get_architecture_graph(root: str = None) -> dict:
    """Escanea el proyecto y devuelve el grafo de arquitectura."""
    graph = build_graph(_read_project_files(root))
    graph["module_count"] = len(graph["nodes"])
    graph["edge_count"] = len(graph["edges"])
    return graph


def _emit(event: str, payload=None):
    import sys
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        if payload is None:
            mod.socketio.emit(event)
        else:
            mod.socketio.emit(event, payload)
    except Exception:
        pass


def open_holograph():
    """Abre la Sala de Hologramas en la GUI y envía el grafo actual."""
    _emit("holo_open")
    _emit("architecture_graph", get_architecture_graph())


def close_holograph():
    """Cierra la Sala de Hologramas en la GUI."""
    _emit("holo_close")