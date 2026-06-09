import os
import sys
import ast
import json
import time
import logging
import threading
import inspect
import subprocess
from pathlib import Path
from os import listdir, walk
from importlib import import_module, reload
from tools.filesystem import WORKSPACE_ROOT

# Configuración de archivos y estado
HEALTH_FILE = Path("logs/jarvis_health.json")
INTEGRITY_LOCK = threading.Lock()
LATEST_HEALTH_REPORT = {
    "status": "secure",
    "last_scan": "",
    "syntax_failures": [],
    "tools_failures": [],
    "env_check": [],
    "test_results": {"ran": 0, "failures": 0, "errors": 0, "passed": True}
}

INTEGRITY_THREAD = None
stop_event = threading.Event()
LAST_STATUS = "secure"

def check_codebase_syntax() -> list:
    """Recorre core/, tools/ y gui/ buscando errores de sintaxis en archivos .py."""
    failures = []
    root_path = Path(WORKSPACE_ROOT)
    folders_to_scan = ["core", "tools", "gui"]
    
    for folder_name in folders_to_scan:
        folder_path = root_path / folder_name
        if not folder_path.exists():
            continue
            
        for root, _, files in walk(folder_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        ast.parse(content)
                    except SyntaxError as se:
                        rel_path = file_path.relative_to(root_path).as_posix()
                        failures.append({
                            "file": rel_path,
                            "error": f"Error de sintaxis en línea {se.lineno}: {se.msg}"
                        })
                    except Exception as e:
                        rel_path = file_path.relative_to(root_path).as_posix()
                        failures.append({
                            "file": rel_path,
                            "error": f"Error al leer archivo: {str(e)}"
                        })
    return failures

def check_tools_load_status() -> list:
    """Intenta importar dinámicamente cada herramienta de tools/ y reporta fallos."""
    failures = []
    root_path = Path(WORKSPACE_ROOT)
    tools_dir = root_path / "tools"
    
    if not tools_dir.exists():
        return [{"file": "tools/", "error": "El directorio tools no existe."}]
        
    # Asegurar que el workspace esté en el sys.path
    if str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))
        
    for filename in listdir(tools_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"tools.{filename[:-3]}"
            try:
                # Importar o recargar módulo para comprobar fallos
                if module_name in sys.modules:
                    reload(sys.modules[module_name])
                else:
                    import_module(module_name)
            except Exception as e:
                failures.append({
                    "file": f"tools/{filename}",
                    "error": str(e)
                })
    return failures

def check_env_variables() -> list:
    """Verifica que las variables clave de entorno estén presentes y no vacías."""
    required_keys = [
        "OPENROUTER_API_KEY",
        "GOOGLE_API_KEY",
        "TAVILY_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_USER_ID"
    ]
    results = []
    for key in required_keys:
        val = os.getenv(key)
        configured = val is not None and len(val.strip()) > 0
        results.append({
            "name": key,
            "configured": configured
        })
    return results

def run_unit_tests() -> dict:
    """Ejecuta silenciosamente la suite de pruebas unitarias y parsea los resultados."""
    logging.info("[Integrity] Ejecutando suite de pruebas unitarias...")
    try:
        venv_python = str(Path(WORKSPACE_ROOT) / ".venv" / "Scripts" / "python.exe")
        if not os.path.exists(venv_python):
            venv_python = "python"
            
        result = subprocess.run(
            [venv_python, "-m", "unittest", "discover", "-s", "tests"],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            timeout=25
        )
        
        # Parsea el output para buscar el resumen final
        # Ejemplo: "Ran 86 tests in 12.265s\n\nOK" o "FAILED (failures=1, errors=2)"
        ran_count = 0
        failures_count = 0
        errors_count = 0
        passed = result.returncode == 0
        
        output = result.stderr or ""
        # Buscar la línea "Ran X tests in Ys"
        for line in output.splitlines():
            if line.startswith("Ran ") and " tests in " in line:
                parts = line.split()
                try:
                    ran_count = int(parts[1])
                except ValueError:
                    pass
            elif "FAILED" in line and "(" in line:
                # Ejemplo: FAILED (failures=1, errors=2)
                details = line.split("(", 1)[1].replace(")", "")
                for part in details.split(","):
                    part = part.strip()
                    if part.startswith("failures="):
                        try:
                            failures_count = int(part.split("=")[1])
                        except ValueError:
                            pass
                    elif part.startswith("errors="):
                        try:
                            errors_count = int(part.split("=")[1])
                        except ValueError:
                            pass
                            
        # Si falló pero no pudimos parsear números específicos
        if not passed and failures_count == 0 and errors_count == 0:
            failures_count = 1  # Forzar al menos uno para reportar
            
        return {
            "ran": ran_count,
            "failures": failures_count,
            "errors": errors_count,
            "passed": passed,
            "raw_output": output[-500:] # Guardar los últimos 500 caracteres del error
        }
    except Exception as e:
        logging.error(f"[Integrity] Error al correr suite de tests: {e}")
        return {
            "ran": 0,
            "failures": 1,
            "errors": 0,
            "passed": False,
            "raw_output": f"Fallo al ejecutar subproceso de unittest: {str(e)}"
        }

def run_integrity_check() -> dict:
    """Ejecuta todas las validaciones de salud de Jarvis y actualiza reportes y alertas."""
    global LATEST_HEALTH_REPORT, LAST_STATUS
    
    with INTEGRITY_LOCK:
        logging.info("[Integrity] Iniciando autodiagnóstico de salud de Jarvis...")
        
        syntax_failures = check_codebase_syntax()
        tools_failures = check_tools_load_status()
        env_check = check_env_variables()
        test_results = run_unit_tests()
        
        # Determinar estado
        # Crítico: Errores de sintaxis en el código o fallos graves al importar herramientas
        if syntax_failures or tools_failures:
            status = "critical"
        # Warning: Variables de entorno requeridas faltantes o fallos en las pruebas unitarias
        elif not test_results["passed"] or any(not item["configured"] for item in env_check if item["name"] in ["OPENROUTER_API_KEY", "GOOGLE_API_KEY"]):
            status = "warning"
        else:
            status = "secure"
            
        LATEST_HEALTH_REPORT = {
            "status": status,
            "last_scan": time.strftime("%Y-%m-%d %H:%M:%S"),
            "syntax_failures": syntax_failures,
            "tools_failures": tools_failures,
            "env_check": env_check,
            "test_results": test_results
        }
        
        # Guardar reporte en logs
        try:
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            HEALTH_FILE.write_text(json.dumps(LATEST_HEALTH_REPORT, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logging.error(f"[Integrity] Error al escribir logs/jarvis_health.json: {e}")
            
        # Emitir actualización a la GUI
        try:
            from gui.app import socketio
            socketio.emit("jarvis_health_update", LATEST_HEALTH_REPORT)
        except Exception:
            pass
            
        # Alertas si pasa de seguro a warning/critical
        if status != "secure" and LAST_STATUS == "secure":
            msg = f"Atención señor. Se ha detectado una degradación de integridad en Jarvis. Estado del sistema: {status.upper()}."
            if syntax_failures:
                msg += f" Hay {len(syntax_failures)} fallos de sintaxis."
            if tools_failures:
                msg += f" {len(tools_failures)} herramientas no pudieron ser importadas."
            if not test_results["passed"]:
                msg += " La suite de pruebas unitarias ha fallado."
                
            # Alerta por Voz (VAD desactivado para asegurar mensaje completo)
            try:
                from tools.voice import speak
                speak(msg, disable_vad=True)
            except Exception:
                pass
                
            # Alerta a Telegram
            try:
                from core.telegram_bot import send_mfa_request
                # Enviar mensaje con formato seguro
                import html
                telegram_msg = f"<b>⚠️ ALERTA DE INTEGRIDAD EN JARVIS</b>\n\n"
                telegram_msg += f"Estado: <code>{status.upper()}</code>\n"
                telegram_msg += f"Escaneo: {LATEST_HEALTH_REPORT['last_scan']}\n\n"
                if syntax_failures:
                    telegram_msg += f"<b>Errores de sintaxis:</b>\n"
                    for f in syntax_failures[:3]:
                        telegram_msg += f"• <i>{html.escape(f['file'])}</i>: {html.escape(f['error'])}\n"
                if tools_failures:
                    telegram_msg += f"<b>Fallos en Herramientas:</b>\n"
                    for f in tools_failures[:3]:
                        telegram_msg += f"• <i>{html.escape(f['file'])}</i>: {html.escape(f['error'])}\n"
                if not test_results["passed"]:
                    telegram_msg += f"<b>Pruebas unitarias fallidas:</b> {test_results['failures']} fallos, {test_results['errors']} errores.\n"
                    
                from core.telegram_bot import bot as tg_bot
                telegram_user_id = os.getenv("TELEGRAM_USER_ID")
                if tg_bot and telegram_user_id:
                    tg_bot.send_message(telegram_user_id, telegram_msg, parse_mode="HTML")
            except Exception as e:
                logging.error(f"[Integrity] Error al enviar alerta de integridad por Telegram: {e}")
                
        LAST_STATUS = status
        return LATEST_HEALTH_REPORT

def _integrity_sentinel_loop():
    """Bucle infinito del hilo daemon del sentinel de integridad."""
    # Espera inicial para no sobrecargar el arranque de Jarvis (30 segundos)
    if stop_event.wait(timeout=30):
        return
        
    while not stop_event.is_set():
        try:
            run_integrity_check()
        except Exception as e:
            logging.error(f"[Integrity] Error en el bucle del sentinel: {e}")
        # Cada 20 minutos (1200 segundos)
        if stop_event.wait(timeout=1200):
            break

def start_integrity_sentinel_daemon():
    """Lanza el daemon del sentinel de integridad en segundo plano. Es idempotente."""
    global INTEGRITY_THREAD
    
    if os.getenv("JARVIS_INTEGRITY_SENTINEL_ENABLED", "True").lower() not in ("true", "1", "yes"):
        logging.info("[Integrity] Disabled in .env.")
        return
        
    if INTEGRITY_THREAD is not None and INTEGRITY_THREAD.is_alive():
        logging.info("[Integrity] Already running.")
        return
        
    stop_event.clear()
    INTEGRITY_THREAD = threading.Thread(target=_integrity_sentinel_loop, name="JarvisIntegritySentinel", daemon=True)
    INTEGRITY_THREAD.start()
    logging.info("[Integrity] Sentinel de Integridad de Jarvis iniciado en segundo plano (cada 20m).")

def stop_integrity_sentinel_daemon():
    """Detiene el sentinel de integridad de forma limpia."""
    logging.info("[Integrity] Deteniendo sentinel de integridad...")
    stop_event.set()
