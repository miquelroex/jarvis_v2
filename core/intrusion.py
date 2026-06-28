"""
core/intrusion.py — Contra-intrusión (defensa del propio equipo).

El Stark paranoico: Jarvis vigila TU sistema en busca de señales de intrusión —
procesos potencialmente hostiles (herramientas de pentest/credenciales), una
ráfaga de accesos fallidos de Windows y conexiones salientes a equipos externos—
y te avisa. *"Señor, alguien intenta acceder. He sellado el sistema."*

La detección (qué procesos son sospechosos, qué cambió respecto al sondeo
anterior, cuándo una ráfaga de logins es alarmante) son funciones PURAS y
testeables; la recolección (psutil, registro de eventos de Windows) y el daemon
se aíslan y degradan con gracia. Defensivo y local: sólo observa tu propio
equipo, no ataca ni rastrea a nadie. Off por defecto.
"""
import os
import logging
import threading

logger = logging.getLogger(__name__)

# Nombres de procesos asociados a herramientas ofensivas / de post-explotación.
SUSPICIOUS_PATTERNS = [
    "mimikatz", "psexec", "ncat", "netcat", "nc.exe", "nmap", "powersploit",
    "procdump", "lazagne", "rubeus", "cobaltstrike", "meterpreter", "metasploit",
    "wireshark", "responder", "bloodhound", "sharphound", "winpeas", "seatbelt",
]

INTRUSION_THREAD = None
stop_event = threading.Event()
_prev = None
_last_alert = {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


# ----------------------------------------------------------------------------
# Núcleo puro
# ----------------------------------------------------------------------------
def find_suspicious(process_names, patterns=None):
    """Procesos cuyo nombre casa con un patrón ofensivo (puro)."""
    pats = patterns if patterns is not None else SUSPICIOUS_PATTERNS
    found = []
    for name in process_names or []:
        ln = _norm(name)
        if any(p in ln for p in pats):
            found.append(name)
    return found


def new_suspicious(prev_names, curr_names, patterns=None):
    """Procesos sospechosos que han APARECIDO desde el sondeo anterior (puro)."""
    nuevos = set(curr_names or []) - set(prev_names or [])
    return find_suspicious(nuevos, patterns)


def failed_login_spike(prev_count: int, curr_count: int, threshold: int) -> int:
    """Incremento de accesos fallidos si alcanza el umbral; 0 si no (puro)."""
    delta = (curr_count or 0) - (prev_count or 0)
    return delta if delta >= threshold else 0


def detect_events(prev: dict, curr: dict, patterns=None, login_threshold: int = 3):
    """Eventos de intrusión de la transición prev -> curr. Puro.

    Sin prev (primer sondeo) sólo alerta de procesos sospechosos ya presentes."""
    events = []
    prev = prev or {}
    base = prev.get("process_names", []) if prev else []
    procs = new_suspicious(base, curr.get("process_names", []), patterns)
    for p in procs:
        events.append({"kind": "process", "detail": p, "severity": "high"})
    spike = failed_login_spike(prev.get("failed_logins", 0), curr.get("failed_logins", 0), login_threshold)
    if spike:
        events.append({"kind": "logins", "detail": spike, "severity": "medium"})
    return events


def describe_event(event: dict) -> str:
    """Frase de aviso de un evento de intrusión (puro)."""
    if event.get("kind") == "process":
        return f"Señor, detecto un proceso potencialmente hostil: {event['detail']}."
    if event.get("kind") == "logins":
        return f"Señor, {event['detail']} intentos de acceso fallidos en poco tiempo. Posible intrusión."
    return "Señor, detecto actividad sospechosa en el sistema."


def build_scan_report(curr: dict, login_threshold: int = 5) -> str:
    """Informe bajo demanda del estado de seguridad del equipo (puro)."""
    suspicious = find_suspicious(curr.get("process_names", []))
    failed = curr.get("failed_logins", 0) or 0
    external = curr.get("external_conns", 0) or 0
    if suspicious:
        return ("Señor, atención: detecto procesos potencialmente hostiles: "
                + ", ".join(suspicious[:5]) + ". Recomiendo investigar.")
    if failed >= login_threshold:
        return f"Señor, {failed} accesos fallidos recientes. Vigile el perímetro."
    extra = f" {external} conexiones salientes externas activas." if external else ""
    return f"Perímetro asegurado, señor. Sin señales de intrusión.{extra}"


# ----------------------------------------------------------------------------
# Recolección de señales (aislada)
# ----------------------------------------------------------------------------
def _process_names():
    try:
        import psutil
        return [p.info.get("name") or "" for p in psutil.process_iter(["name"])]
    except Exception as e:
        logger.debug(f"[Intrusion] No se pudieron leer procesos: {e}")
        return []


def _failed_login_count():
    """Nº de eventos 4625 (login fallido) recientes vía wevtutil (best-effort)."""
    try:
        import subprocess
        res = subprocess.run(
            ["wevtutil", "qe", "Security", "/q:*[System[(EventID=4625)]]",
             "/c:50", "/rd:true", "/f:text"],
            capture_output=True, text=True, timeout=8,
        )
        if res.returncode != 0:
            return 0
        return res.stdout.count("Event ID:")
    except Exception as e:
        logger.debug(f"[Intrusion] No se pudo leer el registro de seguridad: {e}")
        return 0


def _external_connection_count():
    try:
        import psutil
        from core.network_sentinel import is_private_ip
        n = 0
        for c in psutil.net_connections(kind="inet"):
            if c.status == "ESTABLISHED" and c.raddr:
                ip = c.raddr.ip if hasattr(c.raddr, "ip") else c.raddr[0]
                if ip and not is_private_ip(ip) and not ip.startswith("127."):
                    n += 1
        return n
    except Exception as e:
        logger.debug(f"[Intrusion] No se pudieron leer conexiones: {e}")
        return 0


def _gather() -> dict:
    return {
        "process_names": _process_names(),
        "failed_logins": _failed_login_count(),
        "external_conns": _external_connection_count(),
    }


def scan_now() -> str:
    """Comprobación de seguridad bajo demanda ("¿estamos seguros?")."""
    return build_scan_report(_gather())


# ----------------------------------------------------------------------------
# Entrega y daemon (aislado)
# ----------------------------------------------------------------------------
def _notify(message: str):
    import sys
    mod = sys.modules.get("gui.app")
    if mod is not None:
        try:
            mod.socketio.emit("watch_alert", {"text": message})
        except Exception:
            pass
    try:
        from tools.voice import speak
        speak(message, disable_vad=True)
    except Exception:
        pass


def run_once():
    """Un ciclo: sondea, detecta eventos nuevos y avisa (con anti-repetición)."""
    global _prev
    import time
    curr = _gather()
    threshold = int(os.getenv("JARVIS_INTRUSION_LOGIN_THRESHOLD", "3"))
    for event in detect_events(_prev, curr, login_threshold=threshold):
        key = f"{event['kind']}:{event['detail']}"
        if time.time() - _last_alert.get(key, 0) < float(os.getenv("JARVIS_INTRUSION_COOLDOWN", "600")):
            continue
        _last_alert[key] = time.time()
        _notify(describe_event(event))
    _prev = curr


def _intrusion_loop():
    if stop_event.wait(timeout=30):
        return
    while not stop_event.is_set():
        try:
            run_once()
        except Exception as e:
            logger.error(f"[Intrusion] Error en el bucle: {e}")
        interval = int(os.getenv("JARVIS_INTRUSION_INTERVAL", "120"))
        if stop_event.wait(timeout=interval):
            break


def start_intrusion_daemon():
    """Lanza la contra-intrusión. Off por defecto (JARVIS_INTRUSION_ENABLED)."""
    global INTRUSION_THREAD
    if os.getenv("JARVIS_INTRUSION_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Intrusion] Desactivado en .env.")
        return
    if INTRUSION_THREAD is not None and INTRUSION_THREAD.is_alive():
        return
    stop_event.clear()
    INTRUSION_THREAD = threading.Thread(target=_intrusion_loop, name="IntrusionDaemon", daemon=True)
    INTRUSION_THREAD.start()
    logging.info("[Intrusion] Contra-intrusión iniciada.")


def stop_intrusion_daemon():
    """Detiene la contra-intrusión."""
    stop_event.set()
