"""
core/startup.py — Generador de saludo dinámico de arranque para JARVIS.

Genera un texto de bienvenida contextual leyendo:
  - Hora actual (mañana / tarde / noche)
  - RAM consumida por el proceso Jarvis
  - RAM del sistema total
  - Estado de servicios activos
  - Número de recordatorios pendientes
  - Dispositivos en la red local (del último escaneo)

El saludo es formal, técnico y al estilo JARVIS de Iron Man.
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path


def _get_greeting_by_time() -> str:
    """Devuelve el saludo adecuado según la hora del día."""
    hour = datetime.now().hour
    if 6 <= hour < 14:
        return "Buenos días"
    elif 14 <= hour < 21:
        return "Buenas tardes"
    else:
        return "Buenas noches"


def _get_process_ram_mb() -> float:
    """Retorna el uso de RAM del proceso Jarvis en MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def _get_system_ram_percent() -> float:
    """Retorna el porcentaje de RAM del sistema utilizado."""
    try:
        import psutil
        return psutil.virtual_memory().percent
    except Exception:
        return 0.0


def _get_services_summary() -> tuple[int, list[str]]:
    """Retorna (n_running, stopped_services)."""
    try:
        from core.services import get_services_status
        status = get_services_status()
        running = sum(1 for v in status.values() if v == "running")
        stopped = [k for k, v in status.items() if v == "stopped"]
        return running, stopped
    except Exception:
        return 0, []


def _get_pending_reminders() -> int:
    """Retorna el número de recordatorios pendientes."""
    try:
        from core.scheduler import get_active_tasks
        tasks = get_active_tasks()
        return sum(1 for t in tasks if t.get("task_type") == "reminder")
    except Exception:
        return 0


def _get_network_devices() -> tuple[int, int]:
    """Retorna (n_known, n_unknown) del último escaneo de red."""
    try:
        scan_file = Path("logs/last_network_scan.json")
        if not scan_file.exists():
            return 0, 0
        devices = json.loads(scan_file.read_text(encoding="utf-8"))
        known = sum(1 for d in devices if d.get("known", False))
        unknown = len(devices) - known
        return known, unknown
    except Exception:
        return 0, 0


def generate_startup_greeting(include_telemetry: bool = True) -> str:
    """
    Genera el texto del saludo de arranque de JARVIS.
    
    Returns:
        str: Texto completo listo para ser sintetizado por voz.
    """
    greeting = _get_greeting_by_time()
    parts = [f"{greeting}, señor. Los sistemas de Jarvis se encuentran en línea y operativos."]

    if include_telemetry:
        try:
            # RAM del proceso
            process_ram = _get_process_ram_mb()
            system_percent = _get_system_ram_percent()

            if process_ram > 0:
                parts.append(
                    f"Consumo de memoria del sistema: {process_ram:.0f} megabytes del proceso Jarvis, "
                    f"con el {system_percent:.0f} por ciento de la RAM del sistema utilizada."
                )

            # Estado de servicios
            running, stopped = _get_services_summary()
            if running > 0:
                parts.append(f"Tengo {running} servicios activos en segundo plano.")
            if stopped:
                parts.append(
                    f"Advierto que los siguientes servicios no están activos: {', '.join(stopped)}. "
                    "Puede revisar su configuración si lo considera oportuno, señor."
                )

            # Recordatorios pendientes
            reminders = _get_pending_reminders()
            if reminders == 1:
                parts.append("Tiene un recordatorio pendiente en su planificador.")
            elif reminders > 1:
                parts.append(f"Tiene {reminders} recordatorios pendientes en su planificador.")

            # Red local
            known, unknown = _get_network_devices()
            if unknown > 0:
                parts.append(
                    f"Señor, mi último escaneo de red registra {unknown} dispositivo"
                    f"{'s' if unknown > 1 else ''} desconocido{'s' if unknown > 1 else ''} "
                    "en la red local. Le sugiero revisar el panel de red."
                )
            elif known > 0:
                parts.append(f"La red local está despejada. {known} dispositivo{'s' if known > 1 else ''} conocido{'s' if known > 1 else ''} activo{'s' if known > 1 else ''}.")

        except Exception as e:
            logging.warning(f"[Startup] Error al generar telemetría del saludo: {e}")

    parts.append("¿En qué puedo servirle?")
    return " ".join(parts)


def generate_wake_greeting() -> str:
    """
    Genera el saludo de vuelta al estado activo (cuando el usuario dice 'despierta').
    Más corto y contundente que el saludo de arranque completo.
    """
    greeting = _get_greeting_by_time()
    process_ram = _get_process_ram_mb()
    running, _ = _get_services_summary()

    parts = [f"{greeting}, señor. Protocolos de Jarvis reactivados."]
    if process_ram > 0 and running > 0:
        parts.append(
            f"Todos los sistemas en línea. {running} servicios operativos. "
            f"Uso de memoria nominal: {process_ram:.0f} megabytes. A sus órdenes."
        )
    else:
        parts.append("Todos los sistemas en línea. A sus órdenes.")

    return " ".join(parts)


def generate_presence_greeting() -> str:
    """
    Saludo de bienvenida al detectar el dispositivo del usuario en la red local.
    """
    greeting = _get_greeting_by_time()
    return (
        f"{greeting}, señor. Mi centinela de red ha detectado su presencia en la red local. "
        "Bienvenido a casa. Todos los sistemas de Jarvis están operativos y a su disposición. "
        "¿Desea un informe de estado?"
    )
