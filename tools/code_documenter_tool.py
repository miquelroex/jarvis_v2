import os
import logging
from langchain.tools import tool
from core.code_documenter import (
    scan_file_for_undocumented_elements,
    generate_docstring_for_element
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _resolve_path(file_path: str) -> str:
    """Resuelve la ruta a absoluta dentro de los límites del workspace."""
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(os.path.join(PROJECT_ROOT, file_path))
    # Seguridad básica para evitar salir del workspace
    if not file_path.startswith(PROJECT_ROOT):
        raise PermissionError("Acceso denegado: La ruta está fuera del workspace de Jarvis.")
    return file_path

@tool
def scan_undocumented_code(file_path: str) -> str:
    """
    Escanea un archivo de código Python en busca de clases, funciones, métodos
    o endpoints sin documentar. Retorna la lista formateada en Markdown.
    """
    try:
        abs_path = _resolve_path(file_path)
    except PermissionError as pe:
        return str(pe)
        
    if not os.path.exists(abs_path):
        return f"El archivo '{file_path}' no existe en el workspace, señor."
        
    elements = scan_file_for_undocumented_elements(abs_path)
    if not elements:
        return f"Buenas noticias, señor. El archivo '{os.path.basename(file_path)}' ya está completamente documentado o no contiene elementos válidos."
        
    formatted = [f"### Código sin documentar en `{os.path.basename(file_path)}`:\n"]
    for el in elements:
        parent_info = f" (en clase `{el['parent_class']}`)" if el['parent_class'] else ""
        formatted.append(f"- **{el['type'].capitalize()}**: `{el['name']}`{parent_info} en línea {el['line']}")
        
    return "\n".join(formatted)

@tool
def generate_pep257_docstrings(file_path: str, target_name: str, parent_class: str = None) -> str:
    """
    Genera una propuesta de docstring PEP 257 para la clase o función especificada en el archivo.
    Muestra el diff y guarda la acción como pendiente para confirmación explícita del usuario.
    """
    try:
        abs_path = _resolve_path(file_path)
    except PermissionError as pe:
        return str(pe)
        
    modified_code, diff, error = generate_docstring_for_element(abs_path, target_name, parent_class)
    if error:
        return f"Señor, no he podido generar el docstring: {error}"
        
    # Guardar en acciones pendientes
    from core.pending_actions import save_pending_action
    payload = {
        "file_path": abs_path,
        "target_name": target_name,
        "modified_code": modified_code
    }
    save_pending_action("apply_docstrings", payload)
    
    return (
        f"Señor, he generado la documentación propuesta para `{target_name}`. "
        f"He aquí el diff de cambios sugerido:\n\n"
        f"```diff\n{diff}\n```\n\n"
        f"Para aplicar de inmediato estos cambios al archivo, responda con 'confirma acción' o 'adelante'."
    )
