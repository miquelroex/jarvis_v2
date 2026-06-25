import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading
from pathlib import Path
from tools.voice import stop_speak
import subprocess
import base64
import sys

# Crear la aplicación Flask
app = Flask(__name__)

# Clave secreta de sesión: nunca usar un valor fijo en el repositorio.
# Si no está definida en .env, se genera una aleatoria por sesión (las
# sesiones del navegador no sobrevivirán a un reinicio, lo cual es aceptable).
_secret_key = os.getenv('JARVIS_SECRET_KEY')
if not _secret_key or not _secret_key.strip():
    import secrets
    import logging as _logging
    _secret_key = secrets.token_hex(32)
    _logging.warning("[GUI] JARVIS_SECRET_KEY no esta definida en .env. "
                     "Se ha generado una clave aleatoria temporal para esta sesion.")
app.config['SECRET_KEY'] = _secret_key
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:5000", "http://127.0.0.1:5000"])

# Estado actual de Jarvis
jarvis_state = {
    "status": "idle",        # idle, listening, thinking, speaking
    "transcript": "",        # Lo que el usuario ha dicho
    "response": "",          # Lo que Jarvis responde
    "model": "",             # Modelo de IA actual
    "active_window": {"title": "", "app_name": ""}, # Ventana activa actual
}

# Ruta principal: sirve la página HTML
@app.route('/')
def index():
    return render_template('index.html', mapbox_token=os.getenv('MAPBOX_TOKEN', ''))

# Función para actualizar el estado desde Jarvis
def update_state(status, transcript="", response="", model=None, socratic_mode=None):
    jarvis_state["status"] = status
    if transcript:
        jarvis_state["transcript"] = transcript
    if response:
        jarvis_state["response"] = response
    if model is not None:
        jarvis_state["model"] = model
    if socratic_mode is not None:
        jarvis_state["socratic_mode"] = socratic_mode
    # Enviar el estado al navegador en tiempo real
    socketio.emit('state_update', jarvis_state)

# Cuando el navegador se conecta
@socketio.on('connect')
def handle_connect():
    from core.prompts import is_socratic_mode_active
    jarvis_state["socratic_mode"] = is_socratic_mode_active()
    emit('state_update', jarvis_state)
    emit('active_window_update', jarvis_state.get("active_window", {"title": "", "app_name": ""}))
    print("[GUI] Navegador conectado")
    
    # Enviar reporte de uso acumulado hoy al conectar
    try:
        from core.model_logging import get_daily_usage
        emit('daily_usage_update', get_daily_usage())
    except Exception as e:
        print(f"[GUI] Error al enviar reporte de uso diario inicial: {e}")
    
    # Enviar lista actual de dispositivos de red al conectar
    try:
        from core.network_sentinel import active_devices, run_quick_scan
        emit('network_devices_update', active_devices)
        run_quick_scan()
    except Exception as e:
        print(f"[GUI] Error al iniciar escaneo de red al conectar: {e}")
        
    # Enviar estado de privacidad actual al conectar
    try:
        from core.privacy_sentinel import get_privacy_status
        emit('privacy_update', get_privacy_status())
    except Exception as e:
        print(f"[GUI] Error al enviar estado de privacidad inicial: {e}")
        
    # Enviar plan activo si existe al conectar
    try:
        from core.autonomous_agent import ACTIVE_PLAN_FILE
        import json
        if ACTIVE_PLAN_FILE.exists():
            plan_data = json.loads(ACTIVE_PLAN_FILE.read_text(encoding="utf-8"))
            emit('plan_update', plan_data)
    except Exception as e:
        print(f"[GUI] Error al enviar plan activo inicial: {e}")
        
    # Enviar reporte de vulnerabilidades actual al conectar
    try:
        from core.vulnerability_patcher import REPORT_FILE
        import json
        if REPORT_FILE.exists():
            report_data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
            emit('vulnerability_update', report_data)
    except Exception as e:
        print(f"[GUI] Error al enviar reporte de vulnerabilidades inicial: {e}")

    # Enviar reporte de integridad de Jarvis al conectar
    try:
        from core.jarvis_integrity import HEALTH_FILE
        import json
        if HEALTH_FILE.exists():
            health_data = json.loads(HEALTH_FILE.read_text(encoding="utf-8"))
            emit('jarvis_health_update', health_data)
    except Exception as e:
        print(f"[GUI] Error al enviar reporte de integridad inicial: {e}")

    # Enviar healthcheck de arranque al conectar (generado por main.py al iniciar)
    try:
        from core.healthcheck import DEFAULT_REPORT_PATH
        import json
        startup_health_path = Path(DEFAULT_REPORT_PATH)
        if startup_health_path.exists():
            startup_health_data = json.loads(startup_health_path.read_text(encoding="utf-8"))
            emit('startup_healthcheck', startup_health_data)
    except Exception as e:
        print(f"[GUI] Error al enviar healthcheck de arranque inicial: {e}")

    # Enviar informe de salud de dependencias al conectar (generado por su daemon)
    try:
        from core.dependency_health import REPORT_FILE as DEP_HEALTH_FILE
        import json
        if DEP_HEALTH_FILE.exists():
            dep_health_data = json.loads(DEP_HEALTH_FILE.read_text(encoding="utf-8"))
            emit('dependency_health_update', dep_health_data)
    except Exception as e:
        print(f"[GUI] Error al enviar informe de dependencias inicial: {e}")

    # Enviar nivel de amenaza DEFCON actual al conectar
    try:
        from core.threat_level import compute_threat_level
        emit('threat_level_update', compute_threat_level())
    except Exception as e:
        print(f"[GUI] Error al enviar nivel de amenaza inicial: {e}")

    # Enviar dashboard de salud (self-monitoring) actual al conectar
    try:
        from core.self_monitor import get_health_dashboard
        emit('health_dashboard_update', get_health_dashboard())
    except Exception as e:
        print(f"[GUI] Error al enviar dashboard de salud inicial: {e}")

    # Enviar la bandeja de entrada (Inbox) actual al conectar
    try:
        from core.inbox import get_inbox_items
        emit('inbox_update', get_inbox_items())
    except Exception as e:
        print(f"[GUI] Error al enviar la bandeja de entrada inicial: {e}")

    # Enviar estado del Protocolo Blackout (modo noche) actual al conectar
    try:
        from core.night_mode import is_blackout_active
        emit('blackout_on' if is_blackout_active() else 'blackout_off')
    except Exception as e:
        print(f"[GUI] Error al enviar estado del modo noche inicial: {e}")

    # Enviar estado del Protocolo Verónica (modo enfoque) actual al conectar
    try:
        from core.focus_mode import is_focus_active, get_ends_at
        if is_focus_active():
            emit('veronica_on', {'ends_at': get_ends_at()})
        else:
            emit('veronica_off')
    except Exception as e:
        print(f"[GUI] Error al enviar estado del modo enfoque inicial: {e}")

    # Enviar un snapshot inicial de telemetría térmica al conectar
    try:
        from core.thermal_telemetry import get_thermal_snapshot
        emit('thermal_update', get_thermal_snapshot())
    except Exception as e:
        print(f"[GUI] Error al enviar telemetría térmica inicial: {e}")

    # Enviar un snapshot inicial del Packet Map al conectar
    try:
        from core.packet_map import get_packet_map
        emit('packet_map_update', get_packet_map())
    except Exception as e:
        print(f"[GUI] Error al enviar telemetría de red inicial: {e}")

    # Enviar el nivel de sarcasmo actual al conectar (sincroniza el slider)
    try:
        from core.personality import get_sarcasm_level
        emit('sarcasm_level_update', {'level': get_sarcasm_level()})
    except Exception as e:
        print(f"[GUI] Error al enviar el nivel de sarcasmo inicial: {e}")
    
    # Cargar y enviar últimos 15 logs de modelos
    try:
        log_path = Path("logs/model_usage.log")
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            import json
            recent_logs = []
            for line in lines[-15:]:
                line_str = line.strip()
                if not line_str:
                    continue
                if line_str.startswith("{"):
                    try:
                        recent_logs.append(json.loads(line_str))
                    except Exception:
                        pass
                else:
                    parts = [p.strip() for p in line_str.split(" | ", 3)]
                    if len(parts) >= 3:
                        recent_logs.append({
                            "timestamp": parts[0],
                            "tool_name": parts[1],
                            "model_name": parts[2],
                            "prompt": parts[3] if len(parts) > 3 else "",
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "cost": 0.0,
                            "provider": "unknown"
                        })
            emit('initial_logs', recent_logs)
    except Exception as e:
        print(f"[GUI] Error al cargar logs iniciales: {e}")

    # Enviar última detección del portapapeles si es reciente (menos de 60 segundos)
    try:
        from core.clipboard_monitor import LAST_DETECTION
        import time
        if LAST_DETECTION and (time.time() - LAST_DETECTION["timestamp"] < 60):
            preview = LAST_DETECTION["text"][:150] + ("..." if len(LAST_DETECTION["text"]) > 150 else "")
            emit('clipboard_detection', {
                "type": LAST_DETECTION["type"],
                "preview": preview,
                "length": len(LAST_DETECTION["text"])
            })
    except Exception as e:
        print(f"[GUI] Error al enviar última detección de portapapeles inicial: {e}")

@socketio.on('mute_request')
def handle_mute_request():
    print("[GUI] Recibida solicitud de silencio (Barge-in).")
    stop_speak()

@socketio.on('skip_suitup')
def handle_skip_suitup():
    print("[GUI] Recibida solicitud para omitir (skip) secuencia Suit Up.")
    try:
        from core.suit_up import cancel_suit_up
        cancel_suit_up()
    except Exception as e:
        print(f"[GUI] Error al intentar cancelar la secuencia Suit Up: {e}")

def update_env_var(key: str, value: str) -> None:
    """Updates a variable in the .env file and in the current os.environ."""
    import os
    from pathlib import Path
    os.environ[key] = value
    env_path = Path(".env")
    
    lines = []
    found = False
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
                
    if not found:
        lines.append(f"{key}={value}")
        
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

@socketio.on('get_whisper_config')
def handle_get_whisper_config():
    try:
        from core.whisper_stt import get_model_info
        emit('whisper_config_response', get_model_info())
    except Exception as e:
        print(f"[GUI] Error al obtener configuración de Whisper: {e}")

@socketio.on('set_whisper_model')
def handle_set_whisper_model(data):
    model_name = data.get('model')
    if model_name:
        print(f"[GUI] Solicitud para cambiar modelo de Whisper a: {model_name}")
        try:
            update_env_var("JARVIS_WHISPER_MODEL", model_name)
            from core.whisper_stt import unload_model, get_model_info
            unload_model()
            emit('whisper_config_response', get_model_info(), broadcast=True)
            print(f"[GUI] Modelo de Whisper actualizado a {model_name} y descargado de memoria.")
        except Exception as e:
            print(f"[GUI] Error al cambiar modelo de Whisper: {e}")

@socketio.on('get_services_config')
def handle_get_services_config():
    try:
        from core.services import get_services_status
        emit('services_config_response', get_services_status())
    except Exception as e:
        print(f"[GUI] Error al obtener configuración de servicios: {e}")

@socketio.on('toggle_service')
def handle_toggle_service(data):
    service_name = data.get('service')
    enable = data.get('enable', False)
    if not service_name:
        return
        
    print(f"[GUI] Solicitud para {'activar' if enable else 'desactivar'} servicio: {service_name}")
    try:
        if service_name == "network_sentinel":
            env_var = "JARVIS_SENTINEL_ENABLED"
            val = "true" if enable else "false"
            update_env_var(env_var, val)
            import core.network_sentinel as net_sentinel
            if enable:
                net_sentinel.start_network_sentinel()
            else:
                net_sentinel.stop_network_sentinel()
                
        elif service_name == "api_sentinel":
            env_var = "JARVIS_API_SENTINEL_ENABLED"
            val = "true" if enable else "false"
            update_env_var(env_var, val)
            import core.api_sentinel as api_sentinel
            if enable:
                api_sentinel.start_api_sentinel()
            else:
                api_sentinel.stop_api_sentinel()
                
        elif service_name == "vulnerability_patcher":
            env_var = "JARVIS_PATCHER_ENABLED"
            val = "true" if enable else "false"
            update_env_var(env_var, val)
            update_env_var("JARVIS_VULNERABILITY_PATCHER_ENABLED", val)
            import core.vulnerability_patcher as vuln_patcher
            if enable:
                vuln_patcher.start_vulnerability_patcher_daemon()
            else:
                vuln_patcher.stop_vulnerability_patcher_daemon()
                
        elif service_name == "integrity_sentinel":
            env_var = "JARVIS_INTEGRITY_SENTINEL_ENABLED"
            val = "true" if enable else "false"
            update_env_var(env_var, val)
            import core.jarvis_integrity as integrity
            if enable:
                integrity.start_integrity_sentinel_daemon()
            else:
                integrity.stop_integrity_sentinel_daemon()
                
        elif service_name == "test_watcher":
            env_var = "JARVIS_TEST_WATCHER"
            val = "true" if enable else "false"
            update_env_var(env_var, val)
            import core.test_watcher as test_watcher
            if enable:
                test_watcher.start_test_watcher()
            else:
                test_watcher.stop_test_watcher()
                
        elif service_name == "task_scheduler":
            env_var = "JARVIS_SCHEDULER"
            val = "true" if enable else "false"
            update_env_var(env_var, val)
            import core.scheduler as scheduler
            if enable:
                scheduler.start_scheduler()
            else:
                scheduler.stop_scheduler()
                
        elif service_name == "telegram_bot":
            env_var = "JARVIS_TELEGRAM_ENABLED"
            val = "true" if enable else "false"
            update_env_var(env_var, val)
            import core.telegram_bot as tg_bot
            if enable:
                tg_bot.start_telegram_bot()
            else:
                tg_bot.stop_telegram_bot()
                
        elif service_name == "log_maintenance":
            env_var = "JARVIS_LOG_MAINTENANCE_ENABLED"
            val = "true" if enable else "false"
            update_env_var(env_var, val)
            import core.log_maintenance as log_maintenance
            if enable:
                log_maintenance.start_log_maintenance()
            else:
                log_maintenance.stop_log_maintenance()
                
        elif service_name == "privacy_monitor":
            env_var = "JARVIS_PRIVACY_SCAN_INTERVAL"
            val = "900" if enable else "0"
            update_env_var(env_var, val)
            import core.privacy_sentinel as privacy
            if enable:
                privacy.start_privacy_monitor()
            else:
                privacy.stop_privacy_monitor()

        from core.services import get_services_status
        emit('services_config_response', get_services_status(), broadcast=True)
        print(f"[GUI] Servicio '{service_name}' actualizado: enable={enable}")
    except Exception as e:
        print(f"[GUI] Error al cambiar estado del servicio '{service_name}': {e}")

@socketio.on('run_code_request')
def handle_run_code_request(data):
    language = data.get('language')
    code = data.get('code')
    
    if not language or not code:
        emit('run_code_response', {"error": "Código o lenguaje faltantes"})
        return
        
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Limpiar cualquier plot previo para evitar falsos positivos
    plot_file = logs_dir / "plot.png"
    if plot_file.exists():
        try:
            plot_file.unlink()
        except Exception:
            pass
            
    # Escribir código temporal
    if language == 'python':
        temp_file = logs_dir / "temp_run.py"
        temp_file.write_text(code, encoding="utf-8")
        command = [sys.executable, str(temp_file)]
    elif language == 'php':
        temp_file = logs_dir / "temp_run.php"
        temp_file.write_text(code, encoding="utf-8")
        command = ["php", "-f", str(temp_file)]
    elif language in ('bat', 'cmd', 'batch'):
        temp_file = logs_dir / "temp_run.bat"
        temp_file.write_text(code, encoding="utf-8")
        if sys.platform == 'win32':
            command = ["cmd.exe", "/c", str(temp_file)]
        else:
            command = ["bash", str(temp_file)]
    else:
        emit('run_code_response', {"error": f"Lenguaje '{language}' no soportado para ejecución"})
        return
        
    try:
        # Ejecutar script con límite de 5 segundos
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(Path.cwd())
        )
        stdout = result.stdout
        stderr = result.stderr
        
        # Eliminar temporal
        try:
            temp_file.unlink()
        except Exception:
            pass
            
    except subprocess.TimeoutExpired as te:
        stdout = te.stdout or ""
        stderr = (te.stderr or "") + "\n[ERROR] Tiempo de ejecución límite excedido (5s)"
        try:
            temp_file.unlink()
        except Exception:
            pass
    except Exception as e:
        stdout = ""
        stderr = f"[ERROR] Error al iniciar ejecución: {str(e)}"
        
    # Buscar si se generó un gráfico plot.png
    image_base64 = ""
    if language == 'python' and plot_file.exists():
        try:
            with open(plot_file, "rb") as img_file:
                image_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            plot_file.unlink()
        except Exception as e:
            stderr += f"\n[ERROR] Error al leer la imagen de la gráfica: {str(e)}"
            
    emit('run_code_response', {
        "stdout": stdout,
        "stderr": stderr,
        "image_base64": image_base64
    })

@socketio.on('set_sarcasm')
def handle_set_sarcasm(data):
    try:
        from core.personality import set_sarcasm_level
        level = set_sarcasm_level((data or {}).get('level', 3))
        emit('sarcasm_level_update', {'level': level}, broadcast=True)
    except Exception as e:
        print(f"[GUI] Error al ajustar el nivel de sarcasmo: {e}")

@socketio.on('add_inbox_item')
def handle_add_inbox_item(data):
    content = (data or {}).get('content', '').strip()
    if content:
        try:
            from core.inbox import add_inbox_item, get_inbox_items
            add_inbox_item(content)
            emit('inbox_update', get_inbox_items(), broadcast=True)
        except Exception as e:
            print(f"[GUI] Error al añadir nota a la bandeja: {e}")

@socketio.on('mark_inbox_done')
def handle_mark_inbox_done(data):
    item_id = (data or {}).get('id')
    if item_id is not None:
        try:
            from core.inbox import mark_inbox_done, get_inbox_items
            mark_inbox_done(int(item_id))
            emit('inbox_update', get_inbox_items(), broadcast=True)
        except Exception as e:
            print(f"[GUI] Error al marcar nota como hecha: {e}")

@socketio.on('clear_inbox')
def handle_clear_inbox(data=None):
    try:
        from core.inbox import clear_inbox, get_inbox_items
        clear_inbox()
        emit('inbox_update', get_inbox_items(), broadcast=True)
    except Exception as e:
        print(f"[GUI] Error al vaciar la bandeja: {e}")

@socketio.on('trust_device')
def handle_trust_device(data):
    mac = data.get('mac')
    name = data.get('name', 'Dispositivo Conocido')
    if mac:
        print(f"[GUI] Solicitud para confiar en dispositivo MAC: {mac} con nombre: {name}")
        try:
            from core.network_sentinel import trust_device
            trust_device(mac, name)
        except Exception as e:
            print(f"[GUI] Error al registrar dispositivo de confianza: {e}")

@socketio.on('ignore_secret')
def handle_ignore_secret(data):
    secret_hash = data.get('hash')
    if secret_hash:
        print(f"[GUI] Solicitud para ignorar secreto con hash: {secret_hash}")
        try:
            from core.privacy_sentinel import save_ignored_hash, get_privacy_status, scan_workspace_privacy
            save_ignored_hash(secret_hash)
            
            # Re-escanear y propagar el nuevo estado de privacidad a todos los clientes
            import core.privacy_sentinel
            core.privacy_sentinel.LATEST_FINDINGS = scan_workspace_privacy()
            emit('privacy_update', get_privacy_status(), broadcast=True)
        except Exception as e:
            print(f"[GUI] Error al ignorar secreto: {e}")

@socketio.on('apply_patch')
def handle_apply_patch(data):
    package_name = data.get('package')
    target_version = data.get('version')
    if package_name and target_version:
        print(f"[GUI] Solicitud de parche recibida para: {package_name}=={target_version}")
        try:
            from core.vulnerability_patcher import apply_vulnerability_patch
            # Ejecutar de forma asíncrona para no bloquear el socket
            threading.Thread(
                target=apply_vulnerability_patch,
                args=(package_name, target_version),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[GUI] Error al aplicar el parche: {e}")

@socketio.on('solve_clipboard_error_request')
def handle_solve_clipboard_error():
    print("[GUI] Recibida solicitud para solucionar error del portapapeles.")
    from core.clipboard_monitor import LAST_DETECTION
    if not LAST_DETECTION or LAST_DETECTION["type"] != "traceback":
        emit('clipboard_action_response', {"status": "error", "message": "No hay traceback activo en el portapapeles."})
        return

    def solve_task():
        try:
            update_state("thinking", transcript="[Analizando traceback del portapapeles]")
            error_text = LAST_DETECTION["text"]

            # Invocar al modelo/agente de código para diagnosticar/solucionar
            from tools.model_delegate import ask_delegated_model
            prompt = (
                "Se ha detectado el siguiente traceback/error en el portapapeles. "
                "Diagnostica el problema y ofrece una explicación concisa y un código de solución o parche "
                "con formato markdown de diff unificado si es aplicable.\n\n"
                f"```\n{error_text}\n```"
            )
            response = ask_delegated_model("code", prompt)

            # Actualizar la GUI con la respuesta e informar por voz
            update_state("speaking", response=response)
            from tools.voice import speak
            speak("Señor, he completado el análisis del error. Aquí tiene el diagnóstico y la solución propuesta.")
            update_state("idle")
        except Exception as e:
            print(f"[GUI] Error al solucionar traceback: {e}")
            update_state("idle")

    threading.Thread(target=solve_task, daemon=True).start()

@socketio.on('summarize_clipboard_url_request')
def handle_summarize_clipboard_url():
    print("[GUI] Recibida solicitud para resumir URL del portapapeles.")
    from core.clipboard_monitor import LAST_DETECTION
    if not LAST_DETECTION or LAST_DETECTION["type"] != "url":
        emit('clipboard_action_response', {"status": "error", "message": "No hay URL activa en el portapapeles."})
        return

    def summarize_task():
        try:
            url = LAST_DETECTION["text"].strip()
            update_state("thinking", transcript=f"[Resumiendo URL: {url}]")

            # Scrapear el contenido usando httpx (limitado a 1MB y timeout 5s)
            import httpx
            from tools.model_delegate import ask_delegated_model

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            with httpx.Client(follow_redirects=True, timeout=5.0) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                # Limitar lectura a 1MB
                html_content = resp.text[:1000 * 1024]

            prompt = (
                "Por favor, lee el siguiente contenido HTML extraído de una página web "
                "y genera un resumen estructurado y conciso con los puntos clave.\n\n"
                f"URL: {url}\n\n"
                f"Contenido:\n{html_content[:5000]}" # Limitar para no saturar contexto
            )
            response = ask_delegated_model("default", prompt)

            update_state("speaking", response=response)
            from tools.voice import speak
            speak("Señor, he terminado de resumir la página web solicitada.")
            update_state("idle")
        except Exception as e:
            print(f"[GUI] Error al resumir URL: {e}")
            update_state("idle")

    threading.Thread(target=summarize_task, daemon=True).start()

# Monitor de ventana activa en segundo plano
_gui_stop_event = threading.Event()

def start_active_window_monitor():
    def monitor_loop():
        import time
        from tools.active_window import get_active_window_details
        last_window = None
        while not _gui_stop_event.is_set():
            try:
                current_window = get_active_window_details()
                if not last_window or current_window["title"] != last_window["title"] or current_window["app_name"] != last_window["app_name"]:
                    last_window = current_window
                    jarvis_state["active_window"] = {
                        "title": current_window["title"],
                        "app_name": current_window["app_name"]
                    }
                    socketio.emit('active_window_update', jarvis_state["active_window"])
            except Exception:
                pass
            _gui_stop_event.wait(timeout=2.5)

    threading.Thread(target=monitor_loop, name="ActiveWindowMonitorThread", daemon=True).start()

# Arrancar el servidor en un hilo separado
def start_gui():
    import os
    host = os.getenv("JARVIS_GUI_HOST", "127.0.0.1")
    port = int(os.getenv("JARVIS_GUI_PORT", "5000"))
    socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)

_gui_thread = None

def run_gui_in_background():
    global _gui_thread

    gui_enabled = os.getenv("JARVIS_GUI_ENABLED", "true").lower() in ("true", "1", "yes")
    if not gui_enabled:
        print("[GUI] Interfaz web desactivada por configuración (JARVIS_GUI_ENABLED=false).")
        return

    if _gui_thread is not None and _gui_thread.is_alive():
        print("[GUI] Servidor GUI ya está en ejecución.")
        return
        
    _gui_stop_event.clear()
    _gui_thread = threading.Thread(target=start_gui, name="GUIFlaskThread", daemon=True)
    _gui_thread.start()
    start_active_window_monitor()
    
    # Arrancar el monitor de privacidad local
    try:
        from core.privacy_sentinel import start_privacy_monitor
        start_privacy_monitor()
    except Exception as e:
        print(f"[GUI] Error al iniciar monitor de privacidad: {e}")
        
    print("[GUI] Interfaz disponible en http://localhost:5000")

def stop_gui_monitor():
    """Detiene el monitor de ventana activa de forma limpia."""
    _gui_stop_event.set()