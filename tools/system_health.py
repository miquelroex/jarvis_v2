"""
Herramienta de diagnóstico de salud del sistema para Jarvis.
Genera un reporte completo de RAM, hilos, servicios, tareas programadas
y procesos Python sin leer archivos grandes.
"""
import os
import threading
import logging
from pathlib import Path
from langchain.tools import tool


def _get_dir_size_mb(dir_path: str) -> float:
    """Calcula el tamaño de un directorio en MB sin leer contenidos."""
    total = 0
    try:
        p = Path(dir_path)
        if p.exists() and p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except OSError:
                        pass
    except Exception:
        pass
    return total / (1024 * 1024)


@tool
def system_health_report() -> str:
    """
    Generates a comprehensive system health report for Jarvis.
    Shows RAM usage of the Jarvis process, system memory status,
    active threads, running services, scheduled tasks, log/db sizes,
    and top Python processes by RAM.
    Use this when the user asks about system health, memory usage,
    diagnostics, performance, or resource consumption.
    """
    sections = []
    sections.append("═══ INFORME DE SALUD DEL SISTEMA JARVIS ═══\n")

    # --- 1. RAM del proceso Jarvis ---
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)
        vms_mb = mem_info.vms / (1024 * 1024)
        sections.append(f"📊 RAM de Jarvis (PID {os.getpid()}):")
        sections.append(f"   RSS (física): {rss_mb:.1f} MB")
        sections.append(f"   VMS (virtual): {vms_mb:.1f} MB")
    except Exception as e:
        sections.append(f"📊 RAM de Jarvis: Error al obtener datos ({e})")

    # --- 2. RAM del sistema ---
    try:
        import psutil
        vm = psutil.virtual_memory()
        total_gb = vm.total / (1024 ** 3)
        available_gb = vm.available / (1024 ** 3)
        used_gb = vm.used / (1024 ** 3)
        sections.append(f"\n💻 RAM del Sistema:")
        sections.append(f"   Total: {total_gb:.1f} GB")
        sections.append(f"   Usada: {used_gb:.1f} GB ({vm.percent}%)")
        sections.append(f"   Disponible: {available_gb:.1f} GB")
    except Exception as e:
        sections.append(f"\n💻 RAM del Sistema: Error ({e})")

    # --- 3. Hilos activos ---
    active_threads = threading.enumerate()
    sections.append(f"\n🧵 Hilos activos: {len(active_threads)}")
    for t in sorted(active_threads, key=lambda x: x.name):
        daemon_tag = " [daemon]" if t.daemon else ""
        sections.append(f"   • {t.name}{daemon_tag}")

    # --- 4. Estado de servicios ---
    try:
        from core.services import get_services_status
        status = get_services_status()
        sections.append(f"\n⚙️ Servicios:")
        for svc, state in status.items():
            icon = "🟢" if state == "running" else ("⚫" if state == "disabled" else "🔴")
            sections.append(f"   {icon} {svc}: {state}")
    except Exception as e:
        sections.append(f"\n⚙️ Servicios: Error ({e})")

    # --- 5. RAM Guard ---
    try:
        from core.ram_guard import is_safe_mode_active, get_paused_services
        if is_safe_mode_active():
            paused = get_paused_services()
            sections.append(f"\n🛡️ RAM Guard: MODO SEGURO ACTIVO")
            sections.append(f"   Servicios pausados: {', '.join(paused) if paused else 'Ninguno'}")
        else:
            sections.append(f"\n🛡️ RAM Guard: Normal")
    except Exception:
        sections.append(f"\n🛡️ RAM Guard: No disponible")

    # --- 6. Tareas programadas ---
    try:
        from core.scheduler import get_active_tasks
        tasks = get_active_tasks()
        sections.append(f"\n📋 Tareas programadas activas: {len(tasks)}")
        for t in tasks[:10]:  # Máximo 10 para no saturar
            task_type = t.get("task_type", "?")
            name = t.get("name", "?")
            next_run = t.get("next_run", "?")
            sections.append(f"   • [{task_type}] {name} → próx: {next_run}")
    except Exception as e:
        sections.append(f"\n📋 Tareas programadas: Error ({e})")

    # --- 7. Tamaños de logs y BD ---
    logs_size = _get_dir_size_mb("logs")
    sections.append(f"\n📁 Tamaños:")
    sections.append(f"   logs/: {logs_size:.2f} MB")

    db_path = Path("memory/jarvis.db")
    if db_path.exists():
        db_size = db_path.stat().st_size / (1024 * 1024)
        sections.append(f"   memory/jarvis.db: {db_size:.2f} MB")
    else:
        sections.append(f"   memory/jarvis.db: No existe")

    # --- 8. Top procesos Python por RAM ---
    try:
        import psutil
        python_procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info", "cmdline"]):
            try:
                pinfo = p.info
                name_lower = (pinfo.get("name") or "").lower()
                if "python" in name_lower:
                    rss = pinfo["memory_info"].rss / (1024 * 1024) if pinfo.get("memory_info") else 0
                    cmdline = pinfo.get("cmdline") or []
                    cmd_str = " ".join(cmdline)[:80] if cmdline else name_lower
                    python_procs.append((pinfo["pid"], rss, cmd_str))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        python_procs.sort(key=lambda x: x[1], reverse=True)
        sections.append(f"\n🐍 Procesos Python (top 5 por RAM):")
        for pid, rss, cmd in python_procs[:5]:
            marker = " ← ESTE" if pid == os.getpid() else ""
            sections.append(f"   PID {pid}: {rss:.1f} MB{marker}")
            sections.append(f"      {cmd}")
    except Exception as e:
        sections.append(f"\n🐍 Procesos Python: Error ({e})")

    sections.append("\n═══ FIN DEL INFORME ═══")
    return "\n".join(sections)
