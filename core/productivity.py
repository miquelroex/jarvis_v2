"""
core/productivity.py — Rastreador de Productividad por Proyecto.

Un daemon muestrea periódicamente la ventana activa (y el repo git asociado si es
un editor) e imputa el tiempo a una "actividad" (proyecto, navegador, terminal…),
acumulando el total por día. Permite consultar por voz cuánto has dedicado a cada
cosa. Todo local; ignora el tiempo de inactividad (AFK).

La clasificación, agregación y formato son puros y testeables; la lectura de la
ventana activa, el idle y el disco se aíslan.
"""
import os
import json
import time
import logging
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("logs/productivity")
PRODUCTIVITY_THREAD = None
stop_event = threading.Event()
_lock = threading.Lock()

_BROWSERS = {"chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "arc"}
_EDITORS = {"code", "devenv", "pycharm64", "pycharm", "sublime_text", "idea64", "idea",
            "antigravity ide", "antigravity", "cursor", "windsurf", "rider64", "webstorm64"}
_TERMINALS = {"windowsterminal", "wt", "cmd", "powershell", "pwsh", "bash", "conhost", "alacritty"}
_COMMS = {"discord", "slack", "telegram", "whatsapp", "teams", "zoom", "skype"}


def classify_activity(app_name: str, title: str = "", repo_name: str = None) -> str:
    """Etiqueta de actividad a partir de la app/título/repo (puro)."""
    app = (app_name or "").strip().lower()
    if not app or app in ("desconocido", "sistema"):
        return "Otros"
    if app in _BROWSERS:
        return "Navegador"
    if app in _EDITORS:
        return f"Proyecto: {repo_name}" if repo_name else "Código"
    if app in _TERMINALS:
        return "Terminal"
    if app in _COMMS:
        return "Comunicación"
    return app.capitalize()


def add_time(tally: dict, label: str, seconds: float) -> dict:
    """Suma `seconds` a `label` en el diccionario de tiempos (puro, in-place)."""
    if not label or seconds <= 0:
        return tally
    tally[label] = round(tally.get(label, 0) + seconds, 1)
    return tally


def _fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, m = seconds // 3600, (seconds % 3600) // 60
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m"
    return f"{seconds}s"


def format_summary(tally: dict, top_n: int = 6) -> str:
    """Texto del resumen de productividad del día (puro)."""
    if not tally:
        return "Aún no he registrado actividad hoy, señor."
    items = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    total = sum(tally.values())
    parts = [f"{label} {_fmt_duration(sec)}" for label, sec in items]
    return (f"Hoy ha dedicado un total de {_fmt_duration(total)}, señor. "
            + "Desglose: " + "; ".join(parts) + ".")


# ── Acceso a disco (aislado) ───────────────────────────────
def _today_path(day=None) -> Path:
    day = day or datetime.now().strftime("%Y-%m-%d")
    return DATA_DIR / f"{day}.json"


def _load_today() -> dict:
    path = _today_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_today(tally: dict):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _today_path().write_text(json.dumps(tally, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[Productivity] No se pudo guardar el registro: {e}")


def record(label: str, seconds: float):
    """Imputa tiempo a una etiqueta en el registro de hoy (thread-safe)."""
    with _lock:
        tally = _load_today()
        add_time(tally, label, seconds)
        _save_today(tally)


def get_today_summary() -> str:
    with _lock:
        return format_summary(_load_today())


# ── Lectura de contexto (aislada) ──────────────────────────
def _idle_seconds() -> float:
    """Segundos desde la última interacción del usuario (0 si no se puede leer)."""
    try:
        import ctypes

        class _LII(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = _LII()
        lii.cbSize = ctypes.sizeof(_LII)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000.0
    except Exception:
        pass
    return 0.0


def _current_label():
    try:
        from tools.active_window import get_active_window_details
        d = get_active_window_details()
    except Exception:
        return None
    app = d.get("app_name", "")
    title = d.get("title", "")
    repo = None
    if app.strip().lower() in _EDITORS:
        try:
            from core.project_awareness import get_active_project
            s = get_active_project()
            if s.get("is_repo"):
                repo = s.get("repo_name")
        except Exception:
            pass
    return classify_activity(app, title, repo)


def _productivity_loop():
    if stop_event.wait(timeout=15):
        return
    while not stop_event.is_set():
        interval = int(os.getenv("JARVIS_PRODUCTIVITY_INTERVAL", "30"))
        if stop_event.wait(timeout=interval):
            break
        try:
            idle_thr = int(os.getenv("JARVIS_PRODUCTIVITY_IDLE_THRESHOLD", "300"))
            if _idle_seconds() >= idle_thr:
                continue  # AFK: no imputar
            label = _current_label()
            if label:
                record(label, interval)
        except Exception as e:
            logger.error(f"[Productivity] Error en el bucle del daemon: {e}")


def start_productivity_daemon():
    """Lanza el rastreador. Idempotente. Off por defecto
    (JARVIS_PRODUCTIVITY_ENABLED), registra tu actividad localmente."""
    global PRODUCTIVITY_THREAD
    if os.getenv("JARVIS_PRODUCTIVITY_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Productivity] Desactivado en .env.")
        return
    if PRODUCTIVITY_THREAD is not None and PRODUCTIVITY_THREAD.is_alive():
        return
    stop_event.clear()
    PRODUCTIVITY_THREAD = threading.Thread(target=_productivity_loop, name="ProductivityDaemon", daemon=True)
    PRODUCTIVITY_THREAD.start()
    logging.info("[Productivity] Rastreador de productividad iniciado.")


def stop_productivity_daemon():
    """Detiene el rastreador."""
    stop_event.set()
