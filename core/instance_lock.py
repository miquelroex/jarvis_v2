"""
Módulo de bloqueo de instancia única para Jarvis.
Previene la ejecución de múltiples instancias simultáneas
usando un archivo de bloqueo con PID en logs/jarvis.lock.
"""
import os
import sys
import atexit
import logging
from pathlib import Path

LOCK_FILE = Path("logs/jarvis.lock")

_lock_acquired = False


def _is_jarvis_process(pid: int) -> bool:
    """
    Verifica si el proceso con el PID dado parece ser una instancia de Jarvis.
    Comprueba el command line del proceso para evitar falsos positivos
    por reutilización de PIDs por parte del sistema operativo.
    """
    try:
        import psutil
        proc = psutil.Process(pid)
        cmdline = " ".join(proc.cmdline()).lower()
        # Verificar que el proceso es Python ejecutando algo relacionado con Jarvis
        return "python" in cmdline and ("main.py" in cmdline or "jarvis" in cmdline)
    except Exception:
        # Si no podemos obtener info del proceso, asumimos que no es Jarvis
        return False


def acquire_instance_lock() -> bool:
    """
    Intenta adquirir el lock de instancia única.
    
    Returns:
        True si el lock fue adquirido exitosamente.
        False si ya hay otra instancia de Jarvis corriendo.
    """
    global _lock_acquired

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    if LOCK_FILE.exists():
        try:
            stored_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            # Lock corrupto, lo eliminamos
            logging.warning("[InstanceLock] Lock file corrupto. Eliminando y continuando.")
            _remove_lock_file()
            stored_pid = None

        if stored_pid is not None:
            # Comprobar si el PID sigue vivo
            try:
                import psutil
                if psutil.pid_exists(stored_pid) and _is_jarvis_process(stored_pid):
                    logging.error(
                        f"[InstanceLock] Ya hay una instancia de Jarvis corriendo (PID: {stored_pid}). "
                        "No se puede arrancar otra."
                    )
                    return False
                else:
                    # PID no existe o no es Jarvis → lock obsoleto
                    logging.warning(
                        f"[InstanceLock] Lock obsoleto detectado (PID: {stored_pid} ya no es Jarvis). "
                        "Eliminando lock y continuando."
                    )
                    _remove_lock_file()
            except ImportError:
                # psutil no disponible, verificar con señal 0
                try:
                    os.kill(stored_pid, 0)
                    # El proceso existe, pero no podemos verificar cmdline
                    logging.error(
                        f"[InstanceLock] Ya hay un proceso con PID {stored_pid} activo. "
                        "No se puede confirmar si es Jarvis sin psutil."
                    )
                    return False
                except OSError:
                    # PID no existe
                    logging.warning(
                        f"[InstanceLock] Lock obsoleto (PID: {stored_pid} no existe). Eliminando."
                    )
                    _remove_lock_file()

    # Escribir nuevo lock con PID actual
    current_pid = os.getpid()
    try:
        LOCK_FILE.write_text(str(current_pid), encoding="utf-8")
        _lock_acquired = True
        atexit.register(release_instance_lock)
        logging.info(f"[InstanceLock] Lock de instancia adquirido (PID: {current_pid}).")
        return True
    except OSError as e:
        logging.error(f"[InstanceLock] No se pudo escribir el archivo de lock: {e}")
        return False


def release_instance_lock():
    """Libera el lock de instancia si fue adquirido por este proceso."""
    global _lock_acquired

    if not _lock_acquired:
        return

    _remove_lock_file()
    _lock_acquired = False
    logging.info("[InstanceLock] Lock de instancia liberado.")


def _remove_lock_file():
    """Elimina el archivo de lock de forma segura."""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except OSError as e:
        logging.error(f"[InstanceLock] Error al eliminar lock file: {e}")
