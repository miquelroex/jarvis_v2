"""
core/suit_up.py — Secuencia de arranque "Suit Up" para JARVIS.

Recopila telemetría real del sistema en 5 fases secuenciales y la emite
por SocketIO al frontend para la animación cinematográfica de arranque.

Fases:
  1. CORE INIT     — Python, PID, directorio de trabajo
  2. MEMORY SCAN   — RAM proceso, RAM sistema, swap
  3. SERVICES CHECK — Servicios activos/inactivos uno por uno
  4. NETWORK RECON  — Dispositivos en red, IP local
  5. FINAL STATUS   — Resumen de alertas y nivel de estado
"""

import os
import sys
import time
import logging
import platform
import threading
import socket as net_socket
from datetime import datetime
from pathlib import Path


logger = logging.getLogger(__name__)

# Duraciones (en segundos) entre fases para la animación
PHASE_DELAYS = {
    1: 1.5,
    2: 1.5,
    3: 2.0,
    4: 1.5,
    5: 1.5,
}

SUIT_UP_CANCELLED = False
SUIT_UP_RUNNING = False
_run_lock = threading.Lock()


def cancel_suit_up() -> None:
    """Cancela la secuencia de arranque Suit Up en curso."""
    global SUIT_UP_CANCELLED
    SUIT_UP_CANCELLED = True


def is_suit_up_running() -> bool:
    """True si hay una secuencia Suit Up emitiéndose ahora mismo."""
    return SUIT_UP_RUNNING


def interruptible_sleep(seconds: float) -> bool:
    """Duerme el tiempo indicado pero comprueba el flag de cancelación periódicamente."""
    global SUIT_UP_CANCELLED
    steps = int(seconds / 0.1)
    for _ in range(steps):
        if SUIT_UP_CANCELLED:
            return True
        time.sleep(0.1)
    rem = seconds - (steps * 0.1)
    if rem > 0 and not SUIT_UP_CANCELLED:
        time.sleep(rem)
    return SUIT_UP_CANCELLED


def _collect_core_init() -> dict:
    """Fase 1: Datos del núcleo del sistema."""
    try:
        python_version = platform.python_version()
    except Exception:
        python_version = "unknown"

    return {
        "phase": 1,
        "title": "CORE INIT",
        "icon": "⚡",
        "items": [
            {"label": "PYTHON", "value": f"v{python_version}", "status": "ok"},
            {"label": "PID", "value": str(os.getpid()), "status": "ok"},
            {"label": "PLATFORM", "value": platform.system(), "status": "ok"},
            {"label": "CWD", "value": str(Path.cwd()), "status": "ok"},
            {"label": "BOOT TIME", "value": datetime.now().strftime("%H:%M:%S"), "status": "ok"},
        ],
    }


def _collect_memory_scan() -> dict:
    """Fase 2: Escaneo de memoria del sistema y del proceso."""
    items = []
    try:
        import psutil

        process = psutil.Process(os.getpid())
        proc_ram_mb = process.memory_info().rss / (1024 * 1024)
        items.append({
            "label": "JARVIS PROCESS",
            "value": f"{proc_ram_mb:.1f} MB",
            "status": "ok",
        })

        vmem = psutil.virtual_memory()
        items.append({
            "label": "SYSTEM RAM",
            "value": f"{vmem.percent}% used ({vmem.used // (1024**3)}/{vmem.total // (1024**3)} GB)",
            "status": "ok" if vmem.percent < 80 else "warning",
        })

        swap = psutil.swap_memory()
        items.append({
            "label": "SWAP",
            "value": f"{swap.percent}% used",
            "status": "ok" if swap.percent < 50 else "warning",
        })

        cpu_percent = psutil.cpu_percent(interval=0.5)
        items.append({
            "label": "CPU LOAD",
            "value": f"{cpu_percent}%",
            "status": "ok" if cpu_percent < 80 else "warning",
        })
    except ImportError:
        items.append({"label": "MEMORY", "value": "psutil not available", "status": "warning"})
    except Exception as e:
        items.append({"label": "MEMORY", "value": f"Error: {e}", "status": "error"})

    return {
        "phase": 2,
        "title": "MEMORY SCAN",
        "icon": "🧠",
        "items": items,
    }


def _collect_services_check() -> dict:
    """Fase 3: Comprobación de servicios en segundo plano."""
    items = []
    try:
        from core.services import get_services_status

        status = get_services_status()
        for name, state in status.items():
            display_name = name.upper().replace("_", " ")
            if state == "running":
                items.append({"label": display_name, "value": "ONLINE", "status": "ok"})
            else:
                items.append({"label": display_name, "value": "OFFLINE", "status": "warning"})
    except Exception as e:
        items.append({"label": "SERVICES", "value": f"Error: {e}", "status": "error"})

    if not items:
        items.append({"label": "SERVICES", "value": "No services registered", "status": "warning"})

    return {
        "phase": 3,
        "title": "SERVICES CHECK",
        "icon": "🔧",
        "items": items,
    }


def _collect_network_recon() -> dict:
    """Fase 4: Reconocimiento de red local."""
    items = []

    # IP local
    try:
        hostname = net_socket.gethostname()
        local_ip = net_socket.gethostbyname(hostname)
        items.append({"label": "LOCAL IP", "value": local_ip, "status": "ok"})
        items.append({"label": "HOSTNAME", "value": hostname, "status": "ok"})
    except Exception:
        items.append({"label": "LOCAL IP", "value": "unavailable", "status": "warning"})

    # Dispositivos del último escaneo
    try:
        import json

        scan_file = Path("logs/last_network_scan.json")
        if scan_file.exists():
            devices = json.loads(scan_file.read_text(encoding="utf-8"))
            known = sum(1 for d in devices if d.get("known", False))
            unknown = len(devices) - known
            items.append({
                "label": "KNOWN DEVICES",
                "value": str(known),
                "status": "ok",
            })
            if unknown > 0:
                items.append({
                    "label": "UNKNOWN DEVICES",
                    "value": str(unknown),
                    "status": "warning",
                })
            else:
                items.append({
                    "label": "UNKNOWN DEVICES",
                    "value": "0",
                    "status": "ok",
                })
        else:
            items.append({"label": "NETWORK SCAN", "value": "No scan data", "status": "warning"})
    except Exception as e:
        items.append({"label": "NETWORK", "value": f"Error: {e}", "status": "error"})

    return {
        "phase": 4,
        "title": "NETWORK RECON",
        "icon": "📡",
        "items": items,
    }


def _collect_final_status() -> dict:
    """Fase 5: Resumen final y nivel de estado global."""
    warnings = 0
    errors = 0
    items = []

    # Alertas de vulnerabilidades
    try:
        from core.vulnerability_patcher import REPORT_FILE
        import json

        if REPORT_FILE.exists():
            report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
            vuln_count = len(report.get("vulnerabilities", []))
            if vuln_count > 0:
                warnings += vuln_count
                items.append({
                    "label": "VULNERABILITIES",
                    "value": f"{vuln_count} detected",
                    "status": "warning",
                })
            else:
                items.append({"label": "VULNERABILITIES", "value": "CLEAR", "status": "ok"})
        else:
            items.append({"label": "VULNERABILITIES", "value": "Not scanned", "status": "ok"})
    except Exception:
        items.append({"label": "VULNERABILITIES", "value": "N/A", "status": "ok"})

    # Alertas de privacidad
    try:
        from core.privacy_sentinel import get_privacy_status

        privacy = get_privacy_status()
        exposed = privacy.get("exposed_count", 0)
        if exposed > 0:
            warnings += exposed
            items.append({
                "label": "SECRETS EXPOSED",
                "value": str(exposed),
                "status": "warning",
            })
        else:
            items.append({"label": "PRIVACY", "value": "SECURED", "status": "ok"})
    except Exception:
        items.append({"label": "PRIVACY", "value": "N/A", "status": "ok"})

    # Recordatorios pendientes
    try:
        from core.scheduler import get_active_tasks

        tasks = get_active_tasks()
        reminders = sum(1 for t in tasks if t.get("task_type") == "reminder")
        if reminders > 0:
            items.append({
                "label": "PENDING REMINDERS",
                "value": str(reminders),
                "status": "ok",
            })
    except Exception:
        pass

    # Nivel de estado global
    if errors > 0:
        level = "CRITICAL"
        level_status = "error"
    elif warnings > 0:
        level = "ADVISORY"
        level_status = "warning"
    else:
        level = "NOMINAL"
        level_status = "ok"

    items.append({"label": "SYSTEM STATUS", "value": level, "status": level_status})

    return {
        "phase": 5,
        "title": "FINAL STATUS",
        "icon": "✅",
        "items": items,
        "level": level,
    }


# Mapa de funciones por fase
PHASE_COLLECTORS = {
    1: _collect_core_init,
    2: _collect_memory_scan,
    3: _collect_services_check,
    4: _collect_network_recon,
    5: _collect_final_status,
}


def run_suit_up_sequence(socketio, delay_multiplier: float = 1.0) -> None:
    """
    Ejecuta la secuencia de arranque 'Suit Up' emitiendo telemetría en 5 fases.

    Args:
        socketio: Instancia de Flask-SocketIO para emitir eventos.
        delay_multiplier: Factor para acelerar (< 1) o ralentizar (> 1) la secuencia.
    """
    global SUIT_UP_CANCELLED, SUIT_UP_RUNNING

    # Guardia anti-reentrada: si ya hay una secuencia en curso (p. ej. dos
    # conexiones del navegador casi a la vez), no lanzar otra en paralelo.
    with _run_lock:
        if SUIT_UP_RUNNING:
            logger.info("[SuitUp] Ya hay una secuencia en curso; se omite la nueva.")
            return
        SUIT_UP_RUNNING = True

    SUIT_UP_CANCELLED = False
    logger.info("[SuitUp] Iniciando secuencia de arranque Suit Up...")

    total_phases = len(PHASE_COLLECTORS)

    try:
        # Emitir evento de inicio
        socketio.emit("suitup_start", {"total_phases": total_phases})

        if interruptible_sleep(0.3 * delay_multiplier):
            logger.info("[SuitUp] Secuencia cancelada por el usuario al inicio.")
            return

        for phase_num in range(1, total_phases + 1):
            if SUIT_UP_CANCELLED:
                logger.info(f"[SuitUp] Secuencia cancelada antes de la fase {phase_num}.")
                break

            try:
                collector = PHASE_COLLECTORS[phase_num]
                data = collector()
                data["progress"] = int((phase_num / total_phases) * 100)
                data["total_phases"] = total_phases

                socketio.emit("suitup_phase", data)
                logger.info(f"[SuitUp] Fase {phase_num}/{total_phases}: {data['title']} — "
                            f"{len(data['items'])} items emitidos")

            except Exception as e:
                logger.error(f"[SuitUp] Error en fase {phase_num}: {e}")
                socketio.emit("suitup_phase", {
                    "phase": phase_num,
                    "title": f"PHASE {phase_num}",
                    "icon": "❌",
                    "items": [{"label": "ERROR", "value": str(e), "status": "error"}],
                    "progress": int((phase_num / total_phases) * 100),
                    "total_phases": total_phases,
                })

            # Pausa entre fases para la animación
            delay = PHASE_DELAYS.get(phase_num, 1.5) * delay_multiplier
            if interruptible_sleep(delay):
                logger.info(f"[SuitUp] Secuencia cancelada durante el delay de la fase {phase_num}.")
                break

        # Emitir evento de finalización si no se ha cancelado
        if not SUIT_UP_CANCELLED:
            socketio.emit("suitup_complete", {"status": "ready"})
            logger.info("[SuitUp] Secuencia Suit Up completada con éxito.")
        else:
            # Enviar evento de que se ha cancelado para sincronizar frontend si es necesario
            socketio.emit("suitup_cancelled", {"status": "cancelled"})
            logger.info("[SuitUp] Secuencia Suit Up cancelada.")
    finally:
        SUIT_UP_RUNNING = False
