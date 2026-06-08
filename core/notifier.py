import os
import urllib.request
import urllib.parse
import logging

def send_push_notification(title: str, message: str, priority: str = "default", tags: list = None) -> bool:
    """
    Envía una notificación push al móvil del usuario.
    Intenta ntfy.sh primero (si tiene JARVIS_NTFY_TOPIC configurado) y Pushover como alternativa.
    """
    success = False
    
    # 1. Canal ntfy.sh
    ntfy_topic = os.getenv("JARVIS_NTFY_TOPIC")
    if ntfy_topic and ntfy_topic.strip():
        ntfy_server = os.getenv("JARVIS_NTFY_SERVER", "https://ntfy.sh").strip().rstrip("/")
        url = f"{ntfy_server}/{ntfy_topic.strip()}"
        
        # Mapear prioridad de ntfy
        # ntfy usa: 1 (min/low), 2 (low), 3 (default), 4 (high), 5 (max/urgent)
        ntfy_priority = "3"
        if priority == "high" or priority == "max":
            ntfy_priority = "4"
        elif priority == "low" or priority == "min":
            ntfy_priority = "2"
            
        headers = {
            "Priority": ntfy_priority,
        }
        
        # ntfy permite pasar título en la cabecera "Title".
        # Para evitar problemas con caracteres no-ASCII en cabeceras HTTP, 
        # ntfy admite codificar en base64 de cabeceras precediendo con X-Title.
        try:
            import base64
            title_b64 = base64.b64encode(title.encode("utf-8")).decode("ascii")
            headers["X-Title"] = f"=?UTF-8?B?{title_b64}?="
        except Exception:
            # Fallback simple si falla b64
            headers["Title"] = title.encode("ascii", "ignore").decode("ascii")
            
        if tags:
            headers["Tags"] = ",".join(tags)
            
        try:
            req = urllib.request.Request(
                url,
                data=message.encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status in (200, 201):
                    logging.info(f"[Notifier] Notificación enviada con éxito vía ntfy.sh (topic: {ntfy_topic})")
                    success = True
        except Exception as e:
            logging.error(f"[Notifier] Error al enviar notificación vía ntfy.sh: {e}")
            
    # 2. Canal Pushover
    pushover_user = os.getenv("PUSHOVER_USER_KEY")
    pushover_token = os.getenv("PUSHOVER_APP_TOKEN")
    if pushover_user and pushover_user.strip() and pushover_token and pushover_token.strip():
        url = "https://api.pushover.net/1/messages.json"
        
        # Mapear prioridad de Pushover
        # Pushover usa: -2 (lowest), -1 (low), 0 (normal), 1 (high), 2 (emergency)
        pushover_priority = 0
        if priority == "high" or priority == "max":
            pushover_priority = 1
        elif priority == "low" or priority == "min":
            pushover_priority = -1
            
        post_data = {
            "token": pushover_token.strip(),
            "user": pushover_user.strip(),
            "title": title,
            "message": message,
            "priority": pushover_priority
        }
        
        try:
            data_encoded = urllib.parse.urlencode(post_data).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_encoded,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status in (200, 201):
                    logging.info("[Notifier] Notificación enviada con éxito vía Pushover")
                    success = True
        except Exception as e:
            logging.error(f"[Notifier] Error al enviar notificación vía Pushover: {e}")
            
    if not success and not ntfy_topic and not pushover_user:
        logging.debug("[Notifier] No se enviaron notificaciones push móviles. Configuración ausente en .env.")
        
    return success
