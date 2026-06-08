import os
import re
from pathlib import Path
from langchain.tools import tool

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MACROS_DIR = PROJECT_ROOT / "macros"

@tool
def check_command_efficiency(force: bool = False) -> str:
    """
    Checks the efficiency of the user's terminal commands.
    It analyzes history, identifies repetitive tasks, and suggests macro automations.
    """
    from core.macro_agent import generate_efficiency_report
    try:
        return generate_efficiency_report()
    except Exception as e:
        return f"Error al generar reporte de eficiencia: {e}"

@tool
def create_macro_shortcut(name: str, commands: list[str]) -> str:
    """
    Creates a macro automation script (batch file) under the 'macros/' folder.
    - name: Name of the macro shortcut (e.g., 'quick_push' or 'run_tests').
    - commands: A list of command strings to execute sequentially in the macro.
    
    Example input:
    - name: "build_and_test"
    - commands: ["npm run build", "npm run test"]
    """
    # Sanitizar el nombre
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '', name).lower().strip()
    if not clean_name:
        return "Error: Nombre de macro inválido."
        
    if not commands:
        return "Error: La lista de comandos no puede estar vacía."
        
    try:
        MACROS_DIR.mkdir(exist_ok=True)
        macro_file = MACROS_DIR / f"{clean_name}.bat"
        
        # Generar contenido del batch script
        lines = ["@echo off"]
        for cmd in commands:
            lines.append(cmd.strip())
            
        macro_file.write_text("\n".join(lines), encoding="utf-8")
        
        rel_path = macro_file.relative_to(PROJECT_ROOT).as_posix()
        
        # Retornar mensaje con formato de bloque de código Markdown para que se cargue en el panel de artefactos
        cmd_list_str = "\n".join([f"  - {c}" for c in commands])
        report = (
            f"🟢 **Macro '{clean_name}' creado con éxito**\n\n"
            f"El script se ha guardado en `{rel_path}` con la siguiente secuencia de comandos:\n"
            f"{cmd_list_str}\n\n"
            "Puedes revisarlo y ejecutarlo directamente desde el panel de artefactos a la derecha:\n"
            f"```bat\n"
            f"{macro_file.read_text(encoding='utf-8')}\n"
            f"```"
        )
        return report
    except Exception as e:
        return f"Error al crear el macro: {e}"
