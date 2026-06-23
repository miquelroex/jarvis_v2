"""
core/hud_overlay.py — HUD Overlay flotante estilo casco de Iron Man.

Ventana de escritorio sin bordes, semitransparente y siempre encima (topmost)
que muestra telemetría en vivo mientras trabajas en el IDE: hora, RAM/CPU del
sistema, RAM del proceso, uptime, nº de servicios activos, llamadas de IA hoy,
nivel DEFCON y el último comando procesado. Si hay alerta (DEFCON rojo/violeta
o RAM crítica) el borde parpadea en rojo.

Usa tkinter (stdlib): sin dependencias nuevas. La lógica de formateo es pura y
testeable; la ventana sólo se crea dentro de su propio hilo (con mainloop
propio), de modo que en CI/headless nunca se instancia Tk.
"""
import os
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

HUD_THREAD = None
stop_event = threading.Event()
_root = None
_last_command = "—"
_lock = threading.Lock()

# Paleta DEFCON para el acento del HUD.
_THREAT_COLORS = {
    "green": "#00e5ff",
    "amber": "#ffb000",
    "red": "#ff3b30",
    "violet": "#bf5af2",
}


def set_last_command(text: str):
    """Registra el último comando procesado para mostrarlo en el HUD."""
    global _last_command
    with _lock:
        _last_command = (text or "").strip() or "—"


def get_last_command() -> str:
    with _lock:
        return _last_command


def _fmt_uptime(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {seconds % 60:02d}s"


def _build_telemetry(dashboard: dict, last_command: str) -> dict:
    """Transforma el dashboard de salud en cadenas listas para el HUD (puro)."""
    sysm = dashboard.get("system", {}) or {}
    svc = dashboard.get("services", {}) or {}
    usage = dashboard.get("usage", {}) or {}
    threat = (dashboard.get("threat_level") or "green").lower()
    return {
        "clock": datetime.now().strftime("%H:%M:%S"),
        "ram": f"{sysm.get('system_ram_percent', 0)}%",
        "cpu": f"{sysm.get('cpu_percent', 0)}%",
        "proc_ram": f"{sysm.get('process_ram_mb', 0)} MB",
        "uptime": _fmt_uptime(sysm.get("uptime_seconds", 0)),
        "services": f"{svc.get('running', 0)} activos",
        "calls": str(usage.get("calls", 0)),
        "threat": threat.upper(),
        "threat_color": _THREAT_COLORS.get(threat, _THREAT_COLORS["green"]),
        "last_command": (last_command or "—")[:52],
    }


def _is_alert(dashboard: dict) -> bool:
    """True si conviene parpadear el borde (DEFCON crítico o RAM alta)."""
    threat = (dashboard.get("threat_level") or "green").lower()
    ram = (dashboard.get("system", {}) or {}).get("system_ram_percent", 0) or 0
    try:
        ram = float(ram)
    except (TypeError, ValueError):
        ram = 0
    return threat in ("red", "violet") or ram >= 90


def _get_dashboard() -> dict:
    try:
        from core.self_monitor import get_health_dashboard
        return get_health_dashboard()
    except Exception as e:
        logger.warning(f"[HUD] No se pudo leer el dashboard: {e}")
        return {}


def _run_window():
    """Crea y ejecuta la ventana HUD (sólo dentro del hilo dedicado)."""
    global _root
    import tkinter as tk

    accent = _THREAT_COLORS["green"]
    bg = "#05080d"

    root = tk.Tk()
    _root = root
    root.overrideredirect(True)                 # sin bordes ni barra de título
    root.attributes("-topmost", True)           # siempre encima
    try:
        root.attributes("-alpha", float(os.getenv("JARVIS_HUD_ALPHA", "0.86")))
    except Exception:
        root.attributes("-alpha", 0.86)
    root.configure(bg=bg)

    # Posición: esquina superior derecha por defecto.
    w, h = 270, 248
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    margin = 18
    root.geometry(f"{w}x{h}+{sw - w - margin}+{margin}")

    border = tk.Frame(root, bg=accent, padx=2, pady=2)
    border.pack(fill="both", expand=True)
    panel = tk.Frame(border, bg=bg)
    panel.pack(fill="both", expand=True)

    title = tk.Label(panel, text="J.A.R.V.I.S.  ·  HUD", fg=accent, bg=bg,
                     font=("Consolas", 11, "bold"))
    title.pack(anchor="w", padx=12, pady=(10, 2))

    clock_lbl = tk.Label(panel, text="--:--:--", fg="#cfe9ff", bg=bg,
                         font=("Consolas", 22, "bold"))
    clock_lbl.pack(anchor="w", padx=12)

    rows = {}
    grid = tk.Frame(panel, bg=bg)
    grid.pack(fill="x", padx=12, pady=(6, 4))
    for i, (key, label) in enumerate([
        ("ram", "RAM"), ("cpu", "CPU"), ("proc_ram", "PROC"),
        ("uptime", "UPTIME"), ("services", "SERVICIOS"), ("calls", "IA HOY"),
    ]):
        r, c = divmod(i, 2)
        cell = tk.Frame(grid, bg=bg)
        cell.grid(row=r, column=c, sticky="w", padx=(0, 14), pady=1)
        tk.Label(cell, text=label, fg="#5b7a90", bg=bg,
                 font=("Consolas", 8, "bold")).pack(anchor="w")
        val = tk.Label(cell, text="—", fg="#e8f4ff", bg=bg, font=("Consolas", 11, "bold"))
        val.pack(anchor="w")
        rows[key] = val

    threat_lbl = tk.Label(panel, text="DEFCON —", fg=accent, bg=bg,
                          font=("Consolas", 9, "bold"))
    threat_lbl.pack(anchor="w", padx=12, pady=(4, 0))

    cmd_lbl = tk.Label(panel, text="› —", fg="#8fb8d0", bg=bg, font=("Consolas", 8),
                       wraplength=w - 28, justify="left")
    cmd_lbl.pack(anchor="w", padx=12, pady=(2, 10))

    # Arrastrar la ventana con el ratón.
    drag = {"x": 0, "y": 0}

    def _start_drag(e):
        drag["x"], drag["y"] = e.x, e.y

    def _on_drag(e):
        root.geometry(f"+{root.winfo_x() + e.x - drag['x']}+{root.winfo_y() + e.y - drag['y']}")

    for widget in (title, clock_lbl, panel):
        widget.bind("<Button-1>", _start_drag)
        widget.bind("<B1-Motion>", _on_drag)
    root.bind("<Escape>", lambda e: stop_event.set())

    blink = {"on": False}

    def _refresh():
        if stop_event.is_set():
            try:
                root.destroy()
            except Exception:
                pass
            return
        dash = _get_dashboard()
        t = _build_telemetry(dash, get_last_command())
        clock_lbl.config(text=t["clock"])
        rows["ram"].config(text=t["ram"])
        rows["cpu"].config(text=t["cpu"])
        rows["proc_ram"].config(text=t["proc_ram"])
        rows["uptime"].config(text=t["uptime"])
        rows["services"].config(text=t["services"])
        rows["calls"].config(text=t["calls"])
        threat_lbl.config(text=f"DEFCON {t['threat']}", fg=t["threat_color"])
        title.config(fg=t["threat_color"])
        cmd_lbl.config(text=f"› {t['last_command']}")

        if _is_alert(dash):
            blink["on"] = not blink["on"]
            border.config(bg="#ff3b30" if blink["on"] else bg)
        else:
            blink["on"] = False
            border.config(bg=t["threat_color"])

        root.after(1000, _refresh)

    _refresh()
    root.mainloop()
    _root = None


def _hud_loop():
    try:
        _run_window()
    except Exception as e:
        logger.error(f"[HUD] No se pudo iniciar el overlay: {e}")


def is_hud_running() -> bool:
    return HUD_THREAD is not None and HUD_THREAD.is_alive()


def start_hud_overlay(force: bool = False):
    """Lanza el HUD Overlay flotante. Idempotente. Off por defecto
    (JARVIS_HUD_OVERLAY_ENABLED). Con force=True ignora la variable de entorno
    (para abrirlo por voz bajo demanda)."""
    global HUD_THREAD
    if not force and os.getenv("JARVIS_HUD_OVERLAY_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[HUD] Overlay desactivado en .env.")
        return
    if HUD_THREAD is not None and HUD_THREAD.is_alive():
        return
    stop_event.clear()
    HUD_THREAD = threading.Thread(target=_hud_loop, name="HudOverlay", daemon=True)
    HUD_THREAD.start()
    logging.info("[HUD] Overlay flotante iniciado.")


def stop_hud_overlay():
    """Solicita el cierre del HUD Overlay."""
    stop_event.set()
