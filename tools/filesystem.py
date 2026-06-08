import os
import shutil
import datetime
from pathlib import Path
from langchain.tools import tool

# Definir la raíz del proyecto para seguridad de accesos
WORKSPACE_ROOT = os.path.abspath(os.getcwd())

def _is_path_safe(path: str) -> bool:
    """Verifica si la ruta resuelta está dentro del directorio del proyecto (WORKSPACE_ROOT)."""
    try:
        resolved = Path(path).resolve()
        root = Path(WORKSPACE_ROOT).resolve()
        return root in resolved.parents or resolved == root
    except Exception:
        return False

@tool
def list_workspace_dir(relative_path: str = ".") -> str:
    """
    Lists the files and folders inside a given directory in the workspace.
    The path must be relative to the workspace root.
    Use this when the user asks to see files, check folder structure, or search for a file in the project.
    """
    target_path = os.path.join(WORKSPACE_ROOT, relative_path)
    
    if not _is_path_safe(target_path):
        return "Acceso denegado: No se permite listar directorios fuera de la carpeta del proyecto, señor."

    if not os.path.exists(target_path):
        return f"El directorio '{relative_path}' no existe en el espacio de trabajo, señor."

    if not os.path.isdir(target_path):
        return f"La ruta '{relative_path}' no es un directorio válido."

    try:
        entries = os.listdir(target_path)
        folders = []
        files = []
        for entry in entries:
            # Ignorar carpetas ocultas y .venv
            if entry.startswith(".") or entry == "__pycache__" or entry == ".venv":
                continue
            entry_path = os.path.join(target_path, entry)
            if os.path.isdir(entry_path):
                folders.append(f"📁 {entry}/")
            else:
                files.append(f"📄 {entry}")
        
        output = f"Contenido del directorio '{relative_path}':\n\n"
        if not folders and not files:
            output += "(Directorio vacío)"
            return output

        output += "\n".join(sorted(folders) + sorted(files))
        return output
    except Exception as e:
        return f"Error al listar el directorio: {str(e)}"

@tool
def read_workspace_file(relative_path: str) -> str:
    """
    Reads the text contents of a file inside the workspace.
    The path must be relative to the workspace root.
    Use this when the user asks to check code, read files, inspect configurations, or check details of a project file.
    """
    target_path = os.path.join(WORKSPACE_ROOT, relative_path)
    
    if not _is_path_safe(target_path):
        return "Acceso denegado: No se permite leer archivos fuera de la carpeta del proyecto, señor."

    if not os.path.exists(target_path):
        return f"El archivo '{relative_path}' no existe, señor."

    if os.path.isdir(target_path):
        return f"La ruta '{relative_path}' es un directorio, no un archivo."

    # Seguridad adicional: no revelar credenciales del .env al LLM por error
    filename = os.path.basename(target_path)
    if filename == ".env":
        return "Acceso denegado: Por seguridad de sus claves de API, no tengo permitido leer el archivo .env, señor."

    # Evitar lectura de archivos binarios grandes
    ext = os.path.splitext(target_path)[1].lower()
    if ext in [".png", ".jpg", ".jpeg", ".zip", ".tar", ".gz", ".exe", ".pyc"]:
        return f"Acceso denegado: El archivo '{relative_path}' es de formato binario ({ext}) y no puede leerse como texto."

    try:
        # Limitar la lectura a un máximo de 8000 caracteres para no saturar el contexto
        with open(target_path, "r", encoding="utf-8", errors="ignore") as file:
            content = file.read(12000)
            
        output = f"### Contenido de '{relative_path}':\n\n"
        output += content
        if len(content) >= 12000:
            output += "\n\n*(Nota: El archivo ha sido recortado para no saturar el contexto)*"
        return output
    except Exception as e:
        return f"Error al leer el archivo: {str(e)}"

def execute_write_file(relative_path: str, content: str, append: bool = False) -> str:
    """Ejecuta la escritura del archivo física realizando una copia de seguridad previa si ya existe."""
    target_path = os.path.join(WORKSPACE_ROOT, relative_path)
    
    # 1. Crear backup si el archivo existe
    if os.path.exists(target_path) and os.path.isfile(target_path):
        try:
            backup_dir = os.path.join(WORKSPACE_ROOT, "logs", "backup")
            os.makedirs(backup_dir, exist_ok=True)
            
            basename = os.path.basename(target_path)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{basename}.{timestamp}.bak")
            
            shutil.copy2(target_path, backup_path)
        except Exception as e:
            # Reportar backup fallido pero continuar con la escritura
            print(f"[Backup] Warning: No se pudo crear copia de seguridad: {e}")
            
    # 2. Escribir el archivo
    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        mode = "a" if append else "w"
        with open(target_path, mode, encoding="utf-8") as file:
            file.write(content)
            
        action_verb = "añadido contenido a" if append else "escrito"
        return f"He {action_verb} '{relative_path}' con éxito, señor."
    except Exception as e:
        return f"Error al escribir en el archivo: {str(e)}"

@tool
def write_workspace_file(relative_path: str, content: str, append: bool = False) -> str:
    """
    Writes or appends text content to a file inside the workspace.
    The path must be relative to the workspace root.
    Use this when the user asks to write code, save a note, edit a file, or create a new file in the project.
    """
    target_path = os.path.join(WORKSPACE_ROOT, relative_path)
    
    if not _is_path_safe(target_path):
        return "Acceso denegado: No se permite escribir archivos fuera de la carpeta del proyecto, señor."

    filename = os.path.basename(target_path)
    if filename == ".env":
        return "Acceso denegado: Por seguridad, no tengo permitido modificar el archivo .env, señor."

    # 3. Interceptar si es una ruta crítica
    is_critical = False
    resolved_target = Path(target_path).resolve()
    resolved_root = Path(WORKSPACE_ROOT).resolve()
    
    try:
        rel_to_root = resolved_target.relative_to(resolved_root)
        rel_parts = rel_to_root.parts
        if rel_parts:
            first_dir = rel_parts[0]
            if first_dir in ["core", "tools", "gui"]:
                is_critical = True
            elif len(rel_parts) == 1 and first_dir == "main.py":
                is_critical = True
    except ValueError:
        pass

    if is_critical:
        from core.pending_actions import save_pending_action
        data = {
            "relative_path": relative_path,
            "content": content,
            "append": append
        }
        save_pending_action("file_write", data)
        return (
            f"La ruta '{relative_path}' es parte de los componentes críticos del sistema. "
            f"Por razones de seguridad, esta escritura requiere confirmación verbal o por terminal. "
            f"Si desea proceder a escribir el archivo, por favor diga 'confirmo acción' o 'adelante'."
        )

    # Escritura directa para rutas no críticas
    return execute_write_file(relative_path, content, append)
