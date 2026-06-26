"""
core/watchpost.py — "Jarvis, vigila esto" (Puesto de Vigilancia).

Pones un fichero, un proceso o un puerto bajo vigilancia y Jarvis te avisa en
cuanto cambie su estado: "Señor, el fichero que vigilaba acaba de modificarse".

El parseo de la petición, la comparación de estados y las frases de aviso son
funciones PURAS y testeables. Las sondas (disco/psutil/socket), el registro de
vigilancias y el daemon de sondeo se aíslan. El daemon notifica por voz y emite
al HUD; off por defecto (JARVIS_WATCHPOST_ENABLED).
"""
import os
import sys
import time
import logging
import threading
import unicodedata

logger = logging.getLogger(__name__)

WATCHES = []  # [{id, kind, target, label, state}]
_lock = threading.Lock()
_id_seq = 0
WATCH_THREAD = None
stop_event = threading.Event()

KINDS = ("file", "process", "port")


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ----------------------------------------------------------------------------
# Parseo de la petición (puro)
# ----------------------------------------------------------------------------
def parse_watch_request(text: str):
    """Interpreta "vigila el fichero/proceso/puerto X". Devuelve {kind, target} o None. Puro."""
    norm = _normalize(text)
    # Localiza el objetivo tras la palabra clave del tipo.
    markers = [
        ("port", ["puerto"]),
        ("file", ["fichero", "archivo", "el file"]),
        ("process", ["proceso", "programa", "aplicacion", "la app", "el proceso"]),
    ]
    for kind, words in markers:
        for w in words:
            idx = norm.find(w)
            if idx == -1:
                continue
            tail = norm[idx + len(w):].strip()
            # Recorta conectores iniciales.
            for filler in ("llamado", "llamada", "el", "la", "de", "del", "en", "que", "se", "llama"):
                if tail.startswith(filler + " "):
                    tail = tail[len(filler) + 1:].strip()
            if kind == "port":
                # Primer token con dígitos en la cola (admite "puerto numero 5000").
                for tok in tail.split(" "):
                    digits = "".join(c for c in tok if c.isdigit())
                    if digits:
                        return {"kind": "port", "target": digits}
                return None
            target = tail.split(" ")[0].strip() if tail else ""
            if target:
                return {"kind": kind, "target": target}
    return None


def make_label(kind: str, target: str) -> str:
    """Etiqueta legible de una vigilancia (puro)."""
    nombres = {"file": "fichero", "process": "proceso", "port": "puerto"}
    return f"{nombres.get(kind, kind)} {target}"


# ----------------------------------------------------------------------------
# Comparación y frases (puro)
# ----------------------------------------------------------------------------
def state_changed(kind: str, old: dict, new: dict) -> bool:
    """¿Cambió el estado relevante entre dos sondeos? Puro."""
    if old is None or new is None:
        return False
    keys = {"file": ("exists", "mtime", "size"),
            "process": ("running", "count"),
            "port": ("open",)}.get(kind, ())
    return any(old.get(k) != new.get(k) for k in keys)


def describe_change(label: str, kind: str, old: dict, new: dict) -> str:
    """Frase de aviso del cambio detectado (puro)."""
    if kind == "file":
        if old.get("exists") and not new.get("exists"):
            return f"Señor, el {label} que vigilaba ha desaparecido."
        if not old.get("exists") and new.get("exists"):
            return f"Señor, el {label} que vigilaba acaba de aparecer."
        return f"Señor, el {label} que vigilaba acaba de modificarse."
    if kind == "process":
        if old.get("running") and not new.get("running"):
            return f"Señor, el {label} que vigilaba se ha detenido."
        if not old.get("running") and new.get("running"):
            return f"Señor, el {label} que vigilaba acaba de arrancar."
        return f"Señor, el {label} ha cambiado: ahora hay {new.get('count')} instancia(s)."
    if kind == "port":
        if new.get("open"):
            return f"Señor, el {label} que vigilaba acaba de abrirse."
        return f"Señor, el {label} que vigilaba se ha cerrado."
    return f"Señor, el {label} que vigilaba ha cambiado."


def format_watch_list(watches) -> str:
    """Texto del listado de vigilancias activas (puro)."""
    if not watches:
        return "No tengo nada bajo vigilancia, señor."
    items = "; ".join(w["label"] for w in watches)
    return f"Tengo {len(watches)} vigilancia(s) activa(s), señor: {items}."


# ----------------------------------------------------------------------------
# Sondas (aisladas)
# ----------------------------------------------------------------------------
def _probe(kind: str, target: str) -> dict:
    """Estado actual de un objetivo (acceso a disco/psutil/socket)."""
    if kind == "file":
        try:
            st = os.stat(target)
            return {"exists": True, "mtime": st.st_mtime, "size": st.st_size}
        except OSError:
            return {"exists": False, "mtime": None, "size": None}
    if kind == "process":
        try:
            import psutil
            name = _normalize(target)
            count = 0
            for p in psutil.process_iter(["name"]):
                pname = _normalize(p.info.get("name") or "")
                if name in pname:
                    count += 1
            return {"running": count > 0, "count": count}
        except Exception:
            return {"running": False, "count": 0}
    if kind == "port":
        import socket
        try:
            port = int(target)
        except ValueError:
            return {"open": False}
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            return {"open": s.connect_ex(("127.0.0.1", port)) == 0}
        finally:
            s.close()
    return {}


# ----------------------------------------------------------------------------
# Registro de vigilancias
# ----------------------------------------------------------------------------
def add_watch(kind: str, target: str) -> dict:
    """Registra una nueva vigilancia con su estado inicial. Devuelve el registro."""
    global _id_seq
    label = make_label(kind, target)
    state = _probe(kind, target)
    with _lock:
        _id_seq += 1
        watch = {"id": _id_seq, "kind": kind, "target": target, "label": label, "state": state}
        WATCHES.append(watch)
    return watch


def remove_watch(query: str) -> int:
    """Elimina las vigilancias cuyo objetivo/etiqueta casa con `query`. Devuelve cuántas."""
    q = _normalize(query)
    with _lock:
        before = len(WATCHES)
        kept = [w for w in WATCHES if q not in _normalize(w["target"]) and q not in _normalize(w["label"])]
        WATCHES[:] = kept
        return before - len(kept)


def list_watches():
    with _lock:
        return list(WATCHES)


def start_watch_command(text: str) -> str:
    """Procesa "vigila el ..." por voz y registra la vigilancia."""
    req = parse_watch_request(text)
    if not req:
        return ("¿Qué desea que vigile, señor? Indique un fichero, un proceso o "
                "un puerto, por ejemplo: \"vigila el fichero config.py\".")
    watch = add_watch(req["kind"], req["target"])
    _ensure_daemon()
    return f"Entendido, señor. Vigilaré el {watch['label']} y le avisaré en cuanto cambie."


# ----------------------------------------------------------------------------
# Entrega y daemon
# ----------------------------------------------------------------------------
def _notify(message: str):
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


def _poll_once():
    """Sondea todas las vigilancias y notifica los cambios (actualizando su estado)."""
    for watch in list_watches():
        try:
            new = _probe(watch["kind"], watch["target"])
            if state_changed(watch["kind"], watch.get("state"), new):
                _notify(describe_change(watch["label"], watch["kind"], watch["state"], new))
            with _lock:
                watch["state"] = new
        except Exception as e:
            logger.debug(f"[Watchpost] Error sondeando {watch.get('label')}: {e}")


def _watch_loop():
    while not stop_event.is_set():
        interval = int(os.getenv("JARVIS_WATCHPOST_INTERVAL", "20"))
        if stop_event.wait(timeout=interval):
            break
        _poll_once()


def _ensure_daemon():
    """Arranca el daemon de sondeo si hay vigilancias y aún no corre."""
    global WATCH_THREAD
    if WATCH_THREAD is not None and WATCH_THREAD.is_alive():
        return
    stop_event.clear()
    WATCH_THREAD = threading.Thread(target=_watch_loop, name="WatchpostDaemon", daemon=True)
    WATCH_THREAD.start()
    logging.info("[Watchpost] Puesto de vigilancia iniciado.")


def start_watchpost_daemon():
    """Arranca el daemon si está habilitado (JARVIS_WATCHPOST_ENABLED, off por defecto)."""
    if os.getenv("JARVIS_WATCHPOST_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Watchpost] Desactivado en .env.")
        return
    _ensure_daemon()


def stop_watchpost_daemon():
    """Detiene el daemon de vigilancia."""
    stop_event.set()
