import os
import psutil
from langchain.tools import tool

try:
    import win32gui
    import win32process
except ImportError:
    win32gui = None
    win32process = None

def get_active_window_details() -> dict:
    """
    Obtiene los detalles (título de la ventana y nombre del ejecutable)
    de la ventana activa en primer plano en Windows.
    """
    if not win32gui or not win32process:
        return {"title": "Entorno no compatible (No Windows/PyWin32)", "app_name": "Sistema", "pid": 0}

    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return {"title": "Ninguna", "app_name": "Desconocido", "pid": 0}
            
        title = win32gui.GetWindowText(hwnd) or "Sin título"
        
        # Obtener PID de la ventana
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        app_name = "Desconocido"
        if pid > 0:
            try:
                proc = psutil.Process(pid)
                # Obtener el nombre del proceso y quitar la extensión .exe
                name = proc.name()
                if name.lower().endswith(".exe"):
                    name = name[:-4]
                app_name = name
            except Exception:
                pass
                
        return {
            "title": title,
            "app_name": app_name,
            "pid": pid
        }
    except Exception as e:
        return {
            "title": "Error al consultar ventana",
            "app_name": "Sistema",
            "pid": 0,
            "error": str(e)
        }

@tool
def get_active_window(query: str = "") -> str:
    """
    Retrieves the title and application name of the active window currently in focus on the user's PC.
    Use this tool to find out what application the user is currently interacting with (e.g. VS Code, Chrome, etc.)
    and what document or webpage they have open to adapt your response to their current context.
    """
    details = get_active_window_details()
    app = details["app_name"].upper()
    title = details["title"]
    return f"La ventana activa en el PC del usuario es: {app} (Título: '{title}')."
