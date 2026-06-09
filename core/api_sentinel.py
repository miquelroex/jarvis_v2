import os
import time
import logging
import threading
import requests
from tools.voice import speak

# Historial de estados anteriores
# Opciones de indicador: "none", "minor", "major", "critical", "unknown"
LAST_STATUS = {
    "GitHub": "none",
    "OpenAI": "none",
    "Gemini": "none"
}

SENTINEL_THREAD = None
stop_event = threading.Event()

def is_internet_available() -> bool:
    """Verifica si hay conectividad general a internet."""
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except Exception:
        return False

def check_all_apis_status() -> dict:
    """
    Chequea el estado de GitHub, OpenAI y Gemini.
    Retorna un diccionario con los resultados.
    """
    results = {}
    
    # 1. GitHub
    try:
        r = requests.get("https://www.githubstatus.com/api/v2/summary.json", timeout=10)
        if r.status_code == 200:
            data = r.json()
            indicator = data.get("status", {}).get("indicator", "unknown")
            desc = data.get("status", {}).get("description", "Unknown status")
            results["GitHub"] = {"status": indicator, "description": desc}
        else:
            results["GitHub"] = {"status": "unknown", "description": f"HTTP Error {r.status_code}"}
    except Exception as e:
        results["GitHub"] = {"status": "critical" if is_internet_available() else "unknown", "description": str(e)}

    # 2. OpenAI
    try:
        r = requests.get("https://status.openai.com/api/v2/summary.json", timeout=10)
        if r.status_code == 200:
            data = r.json()
            indicator = data.get("status", {}).get("indicator", "unknown")
            desc = data.get("status", {}).get("description", "Unknown status")
            results["OpenAI"] = {"status": indicator, "description": desc}
        else:
            results["OpenAI"] = {"status": "unknown", "description": f"HTTP Error {r.status_code}"}
    except Exception as e:
        results["OpenAI"] = {"status": "critical" if is_internet_available() else "unknown", "description": str(e)}

    # 3. Gemini (Google AI Studio)
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key and api_key.strip():
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            client.models.generate_content(
                model=os.getenv("JARVIS_MODEL_GEMINI", "gemini-2.5-flash"),
                contents="ping",
            )
            results["Gemini"] = {"status": "none", "description": "Operational"}
        except Exception as e:
            if is_internet_available():
                results["Gemini"] = {"status": "critical", "description": str(e)}
            else:
                results["Gemini"] = {"status": "unknown", "description": "No internet connection"}
    else:
        # Fallback a ping al endpoint
        try:
            r = requests.get("https://generativelanguage.googleapis.com/", timeout=10)
            if r.status_code in (200, 404, 403, 400):
                results["Gemini"] = {"status": "none", "description": f"Reachable (HTTP {r.status_code})"}
            else:
                results["Gemini"] = {"status": "critical", "description": f"HTTP Error {r.status_code}"}
        except Exception as e:
            results["Gemini"] = {"status": "critical" if is_internet_available() else "unknown", "description": str(e)}

    return results

def start_api_sentinel():
    """Arranca el monitoreo en segundo plano. Es idempotente."""
    global SENTINEL_THREAD
    
    if os.getenv("JARVIS_API_SENTINEL_ENABLED", "True").lower() not in ("true", "1", "yes"):
        logging.info("[API Sentinel] Disabled in .env.")
        return
        
    if SENTINEL_THREAD is not None and SENTINEL_THREAD.is_alive():
        logging.info("[API Sentinel] Already running.")
        return
        
    stop_event.clear()
    SENTINEL_THREAD = threading.Thread(target=_sentinel_loop, name="APISentinelThread", daemon=True)
    SENTINEL_THREAD.start()
    logging.info("[API Sentinel] Sentinel background thread started.")

def stop_api_sentinel():
    """Detiene el monitoreo en segundo plano de forma limpia."""
    logging.info("[API Sentinel] Deteniendo api sentinel...")
    stop_event.set()

def _sentinel_loop():
    global LAST_STATUS
    # Leer el intervalo configurado
    try:
        interval = int(os.getenv("JARVIS_API_SENTINEL_INTERVAL", "300"))
    except Exception:
        interval = 300
        
    # Inicializar el estado silenciosamente
    try:
        initial_results = check_all_apis_status()
        for api, info in initial_results.items():
            LAST_STATUS[api] = info["status"]
    except Exception as e:
        logging.error(f"[API Sentinel] Error initializing statuses: {e}")
        
    while not stop_event.is_set():
        if stop_event.wait(timeout=interval):
            break
            
        try:
            # Si no hay internet general, no alertamos para evitar falsos positivos
            if not is_internet_available():
                continue
                
            current_results = check_all_apis_status()
            
            for api, info in current_results.items():
                prev = LAST_STATUS.get(api, "none")
                curr = info["status"]
                
                was_degraded = prev in ("minor", "major", "critical")
                is_degraded = curr in ("minor", "major", "critical")
                
                if curr != prev:
                    if is_degraded and not was_degraded:
                        msg = f"Advertencia: Se ha detectado una degradación de servicio en la API de {api}."
                        logging.warning(f"[API Sentinel] Alert: {msg} (Status: {curr})")
                        speak(msg, disable_vad=True)
                    elif is_degraded and was_degraded and curr == "critical" and prev != "critical":
                        msg = f"Alerta crítica: La API de {api} reporta una caída total del servicio."
                        logging.warning(f"[API Sentinel] Critical Alert: {msg}")
                        speak(msg, disable_vad=True)
                    elif not is_degraded and was_degraded:
                        msg = f"Excelente: El servicio de la API de {api} se ha restablecido por completo."
                        logging.info(f"[API Sentinel] Recovery: {msg}")
                        speak(msg, disable_vad=True)
                        
                    LAST_STATUS[api] = curr
                    
        except Exception as e:
            logging.error(f"[API Sentinel] Error in sentinel loop check: {e}")
