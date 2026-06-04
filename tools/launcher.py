from langchain.tools import tool
import os

@tool
def open_windows_app(app_executable: str) -> str:
    """Abre una aplicación de Windows. El parámetro app_executable debe ser el nombre del ejecutable (ej. 'calc', 'notepad', 'chrome', 'spotify', 'explorer'). Usa esta herramienta cuando el usuario pida abrir o iniciar una aplicación del ordenador."""
    try:
        # El comando 'start' en Windows busca el ejecutable en el PATH
        os.system(f"start {app_executable}")
        return f"He enviado la orden para abrir {app_executable}."
    except Exception as e:
        return f"Error al intentar abrir la aplicación: {e}"
