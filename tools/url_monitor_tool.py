from langchain.tools import tool
from core.scheduler import add_url_monitor, reactivate_url_monitor

@tool("add_url_monitor")
def add_url_monitor_tool(name: str, url: str, interval_seconds: int, allow_local_network: bool = False) -> str:
    """
    Añade una URL al planificador de tareas para monitorear cambios en su contenido.
    La tarea se ejecutará de forma periódica con un timeout corto de 5s y límite de descarga de 1MB.
    
    Parámetros:
    - name: Nombre identificador único de la tarea (usar minúsculas y guiones bajos, ej: 'monitor_mi_web').
    - url: La dirección URL a monitorear (debe comenzar con http:// o https://).
    - interval_seconds: Intervalo de monitoreo en segundos (mínimo de 300 segundos / 5 minutos).
    - allow_local_network: Si es True, permite monitorear URLs locales de la LAN (requiere confirmación adicional). Por defecto es False.
    """
    try:
        # Si la URL no empieza con http:// o https://, la auto-completamos con https://
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            
        res = add_url_monitor(name, url, interval_seconds, allow_local_network)
        return res
    except Exception as e:
        return f"Error al añadir el monitor de URL: {str(e)}"

@tool("reactivate_url_monitor")
def reactivate_url_monitor_tool(name: str) -> str:
    """
    Reactiva un monitor de URL que está silenciado tras detectar un cambio (estado alerted: True).
    Esto restablece su estado y le permite volver a comprobar cambios y notificar al usuario.
    
    Parámetros:
    - name: Nombre/ID único o parte del target/URL del monitor a reactivar.
    """
    try:
        res = reactivate_url_monitor(name)
        return res
    except Exception as e:
        return f"Error al reactivar el monitor de URL: {str(e)}"
