import os
import re
import ast
import logging
from langchain.tools import tool
from core.agent_manager import reload_agent

@tool
def create_dynamic_tool(name: str, description: str, python_code: str) -> str:
    """
    Creates and registers a new LangChain tool dynamically at runtime from Python code.
    Use this tool when you realize you lack a specific tool or custom logic needed to solve the user's request (e.g., custom algorithms, math formulas, parsing formats).
    - name: must be a clean python identifier, lowercase, e.g. 'calculate_fibonacci'.
    - description: clear explanation of what the tool does and its parameters.
    - python_code: complete python code containing the decorated `@tool` function.
    """
    # 1. Normalizar el nombre para evitar inyecciones o rutas no válidas
    clean_name = re.sub(r"[^a-zA-Z0-9_]", "", name).lower()
    if not clean_name:
        return "Error: El nombre de la herramienta no es válido."
        
    filename = f"{clean_name}.py"
    tools_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
    filepath = os.path.join(tools_dir, filename)
    
    # 2. Validar sintaxis de Python
    try:
        ast.parse(python_code)
    except SyntaxError as e:
        return (
            f"Error: El código contiene un error de sintaxis de Python: '{e.msg}' "
            f"en la línea {e.lineno}, columna {e.offset}."
        )

    # 3. Asegurar importación de @tool y decoración
    # Inyectar importaciones si faltan
    imports_needed = []
    if "from langchain.tools import tool" not in python_code and "from langchain_core.tools import tool" not in python_code:
        imports_needed.append("from langchain.tools import tool")
        
    # Si no tiene el decorador @tool, intentar colocarlo antes de la primera función 'def '
    if "@tool" not in python_code:
        if "def " in python_code:
            python_code = python_code.replace("def ", "@tool\ndef ", 1)
        else:
            return "Error: El código debe contener al menos una definición de función ('def ...')."
            
    if imports_needed:
        python_code = "\n".join(imports_needed) + "\n\n" + python_code

    # 4. Guardar archivo
    try:
        os.makedirs(tools_dir, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(python_code)
            
        logging.info(f"Guardada nueva herramienta dinámica: {filepath}")
    except Exception as e:
        return f"Error al escribir el archivo de la herramienta: {str(e)}"
        
    # 5. Recargar el agente
    try:
        reload_agent()
    except Exception as e:
        # Si falló al recargar, eliminar el archivo malogrado para no romper futuras cargas
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
        return f"Error al registrar/recargar la nueva herramienta: {str(e)}"
        
    return (
        f"¡Herramienta '{clean_name}' creada, validada y registrada con éxito! "
        f"Ya está disponible en mi sistema. Puedes llamarla de inmediato en tu siguiente paso."
    )
