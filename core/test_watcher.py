import os
import sys
import time
import subprocess
import threading
import logging
from tools.voice import speak

# Variables globales para control del Centinela
_watcher_running = False
_watcher_thread = None
_test_lock = threading.Lock()
stop_event = threading.Event()

# Registro de estados de los tests en memoria: { "tests.test_memory": "pass"/"fail" }
_test_states = {}

# Racha de fallos consecutivos por suite (para reacciones con más "alma")
_fail_streak = {}

# Almacena el estado de los archivos para detectar cambios: { absolute_path: modification_time }
_file_mtimes = {}

# Informar sobre los últimos resultados en la consulta de estado
_last_run_summary = {
    "last_run_time": None,
    "last_test_module": None,
    "last_success": True,
    "output_snippet": ""
}

def is_watcher_running() -> bool:
    """Retorna True si el watcher está activo en segundo plano."""
    global _watcher_running
    return _watcher_running

def get_watcher_status() -> dict:
    """Retorna un diccionario con el estado actual del centinela y el último resultado."""
    global _watcher_running, _last_run_summary, _test_states
    return {
        "running": _watcher_running,
        "last_run": _last_run_summary,
        "test_states": _test_states
    }

def determine_test_module(file_path: str, workspace_root: str) -> str:
    """
    Determina de forma inteligente el módulo de prueba correspondiente a un archivo modificado.
    Retorna el nombre del módulo del test (ej. 'tests.test_memory') o None si requiere la suite completa.
    """
    rel_path = os.path.relpath(file_path, workspace_root).replace("\\", "/")
    parts = rel_path.split("/")
    
    # 1. Si es un archivo directo de test
    if len(parts) >= 2 and parts[0] == "tests" and parts[-1].startswith("test_") and parts[-1].endswith(".py"):
        module_name = parts[-1][:-3] # Eliminar .py
        return f"tests.{module_name}"
        
    # 2. Si es un archivo de código
    filename = parts[-1]
    if filename.endswith(".py") and not filename.startswith("__"):
        base_name = filename[:-3] # Eliminar .py
        
        # Comprobar candidatos estándar en la carpeta tests/
        candidates = [
            f"test_{base_name}.py",
            f"test_{base_name}_tool.py"
        ]
        for candidate in candidates:
            cand_path = os.path.join(workspace_root, "tests", candidate)
            if os.path.exists(cand_path):
                return f"tests.test_{base_name}" if "tool" not in candidate else f"tests.test_{base_name}_tool"
                
    return None

def scan_files(workspace_root: str) -> list:
    """
    Escanea el directorio del proyecto y detecta si algún archivo Python ha cambiado.
    Retorna la lista de rutas absolutas de archivos modificados.
    """
    global _file_mtimes
    modified_files = []
    
    for root, dirs, files in os.walk(workspace_root):
        # Excluir directorios pesados y temporales in-place para optimizar el escaneo
        dirs[:] = [d for d in dirs if d not in {".venv", "venv", "logs", "memory", "__pycache__", ".git", "backups"}]
        
        for file in files:
            # Ignorar backups y archivos que no sean Python
            if not file.endswith(".py") or file.startswith(".") or file.startswith("~") or file.endswith(".bak"):
                continue
                
            abs_path = os.path.abspath(os.path.join(root, file))
            try:
                mtime = os.path.getmtime(abs_path)
            except Exception:
                continue # Evitar caídas si se borra un archivo en caliente durante el escaneo
                
            if abs_path not in _file_mtimes:
                # Primera indexación
                _file_mtimes[abs_path] = mtime
            elif mtime > _file_mtimes[abs_path]:
                # Archivo modificado
                _file_mtimes[abs_path] = mtime
                modified_files.append(abs_path)
                
    return modified_files

def run_test(test_module: str = None) -> bool:
    """
    Ejecuta un test unitario específico o toda la suite con un subproceso con timeout.
    Garantiza exclusión mutua mediante un Lock.
    Retorna True si pasa con éxito, False de lo contrario.
    """
    global _test_lock, _last_run_summary, _test_states
    
    # Resolver comando a ejecutar
    if test_module:
        cmd = [sys.executable, "-m", "unittest", test_module]
        display_name = test_module
    else:
        cmd = [sys.executable, "-m", "unittest", "discover", "tests"]
        display_name = "Suite Completa"
        
    logging.info(f"[TestWatcher] Iniciando ejecución de pruebas: {display_name}...")
    
    with _test_lock:
        try:
            # Timeout holgado y configurable (la suite completa ha crecido).
            test_timeout = int(os.getenv("JARVIS_TEST_WATCHER_TIMEOUT", "180"))
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=False,
                timeout=test_timeout
            )
            success = (res.returncode == 0)
            output = res.stderr if res.stderr else res.stdout
        except subprocess.TimeoutExpired as te:
            success = False
            output = f"TIMEOUT EXPIRED: El test runner superó el límite de 30 segundos.\nStderr: {te.stderr}\nStdout: {te.stdout}"
            logging.error(f"[TestWatcher] Timeout en test {display_name}")
        except Exception as e:
            success = False
            output = f"ERROR: Fallo al ejecutar subproceso: {e}"
            logging.error(f"[TestWatcher] Error ejecutando test: {e}")

        # Guardar resumen en memoria
        _last_run_summary = {
            "last_run_time": time.time(),
            "last_test_module": display_name,
            "last_success": success,
            "output_snippet": output[-500:] if output else ""
        }
        
        # Determinar cambio de estado para alerta de voz
        prev_state = _test_states.get(display_name)
        current_state = "pass" if success else "fail"
        
        # Guardar el nuevo estado
        _test_states[display_name] = current_state

        # Actualizar racha de fallos consecutivos (para la intensidad del alivio)
        fails_before = _fail_streak.get(display_name, 0)
        _fail_streak[display_name] = fails_before + 1 if current_state == "fail" else 0

        # Reaccionar con "alma" solo ante CAMBIOS reales de estado (evita ruido repetitivo)
        if prev_state is not None:
            try:
                from core.reactions import react
                if prev_state == "pass" and current_state == "fail":
                    msg = react("test_broken", {"name": display_name})
                    logging.warning(f"[TestWatcher] Reacción emitida: {msg}")
                elif prev_state == "fail" and current_state == "pass":
                    msg = react("test_recovered", {"name": display_name, "fails": fails_before})
                    logging.info(f"[TestWatcher] Reacción emitida: {msg}")
            except Exception as e:
                logging.warning(f"[TestWatcher] No se pudo emitir la reacción: {e}")
        return success
                
def watcher_loop(workspace_root: str):
    """Bucle principal del hilo watcher con debounce y escaneo."""
    logging.info(f"[TestWatcher] Hilo del Centinela iniciado vigilando en: {workspace_root}")
    
    # Inicializar la indexación inicial de marcas de tiempo
    scan_files(workspace_root)
    
    pending_changes = set()
    last_change_time = 0
    debounce_delay = 2.5 # Debounce de 2.5 segundos
    
    while not stop_event.is_set():
        try:
            modified = scan_files(workspace_root)
            if modified:
                for f in modified:
                    pending_changes.add(f)
                last_change_time = time.time()
                logging.info(f"[TestWatcher] Detectado cambio en: {[os.path.basename(x) for x in modified]}. Esperando debounce...")
                
            # Verificar si se cumple el debounce
            if pending_changes and (time.time() - last_change_time >= debounce_delay):
                # Determinar módulos de prueba correspondientes
                test_modules = set()
                unmapped = False
                for changed_file in pending_changes:
                    module = determine_test_module(changed_file, workspace_root)
                    if module is None:
                        unmapped = True  # cambio sin test asociado (p.ej. main.py, config)
                    else:
                        test_modules.add(module)

                pending_changes.clear()

                # Ejecutar sólo los tests de los módulos afectados.
                for module in test_modules:
                    run_test(module)

                # Sólo correr la suite COMPLETA por cambios sin test asociado si se
                # pide explícitamente (evita machacar la CPU con ~1.339 tests por
                # cualquier edición de un fichero sin test propio).
                if unmapped and not test_modules:
                    if os.getenv("JARVIS_TEST_WATCHER_FULL_ON_UNMAPPED", "false").lower() in ("true", "1", "yes"):
                        run_test(None)
                    else:
                        logging.info("[TestWatcher] Cambio sin test asociado; se omite la suite completa.")
                    
            if stop_event.wait(timeout=1.0):
                break
        except Exception as e:
            logging.error(f"[TestWatcher] Error en bucle del centinela: {e}")
            if stop_event.wait(timeout=5.0):
                break

def start_test_watcher(force: bool = False):
    """
    Inicia el Centinela en segundo plano.
    Si force es True, lo inicia ignorando la variable del .env.
    Es idempotente.
    """
    global _watcher_running, _watcher_thread
    
    # Comprobar variable de entorno .env si no se fuerza la activación
    if not force:
        env_enabled = os.getenv("JARVIS_TEST_WATCHER", "false").lower() == "true"
        if not env_enabled:
            logging.info("[TestWatcher] Centinela desactivado por configuración (JARVIS_TEST_WATCHER=false).")
            return
            
    if _watcher_thread is not None and _watcher_thread.is_alive():
        logging.info("[TestWatcher] El Centinela ya está activo.")
        return
        
    _watcher_running = True
    stop_event.clear()
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _watcher_thread = threading.Thread(
        target=watcher_loop,
        args=(workspace_root,),
        daemon=True,
        name="TestWatcherThread"
    )
    _watcher_thread.start()
    logging.info("[TestWatcher] Centinela activado con éxito.")

def stop_test_watcher():
    """Detiene el Centinela en segundo plano."""
    global _watcher_running
    if not _watcher_running:
        logging.info("[TestWatcher] El Centinela ya estaba detenido.")
        return
        
    _watcher_running = False
    stop_event.set()
    logging.info("[TestWatcher] Centinela detenido.")
