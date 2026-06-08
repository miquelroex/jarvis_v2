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
app.config['SECRET_KEY'] = os.getenv('JARVIS_SECRET_KEY', 'jarvis-secret-fallback-token-secure-382910')
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
    return render_template('index.html')

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
    
    # Cargar y enviar últimos 15 logs de modelos
    try:
        log_path = Path("logs/model_usage.log")
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            recent_logs = []
            for line in lines[-15:]:
                parts = [p.strip() for p in line.split(" | ", 3)]
                if len(parts) >= 3:
                    recent_logs.append({
                        "timestamp": parts[0],
                        "tool_name": parts[1],
                        "model_name": parts[2],
                        "prompt": parts[3] if len(parts) > 3 else ""
                    })
            emit('initial_logs', recent_logs)
    except Exception as e:
        print(f"[GUI] Error al cargar logs iniciales: {e}")

@socketio.on('mute_request')
def handle_mute_request():
    print("[GUI] Recibida solicitud de silencio (Barge-in).")
    stop_speak()

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

# Monitor de ventana activa en segundo plano
def start_active_window_monitor():
    def monitor_loop():
        import time
        from tools.active_window import get_active_window_details
        last_window = None
        while True:
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
            time.sleep(2.5)

    threading.Thread(target=monitor_loop, name="ActiveWindowMonitorThread", daemon=True).start()

# Arrancar el servidor en un hilo separado
def start_gui():
    import os
    host = os.getenv("JARVIS_GUI_HOST", "127.0.0.1")
    port = int(os.getenv("JARVIS_GUI_PORT", "5000"))
    socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)

def run_gui_in_background():
    gui_thread = threading.Thread(target=start_gui, daemon=True)
    gui_thread.start()
    start_active_window_monitor()
    
    # Arrancar el monitor de privacidad local
    try:
        from core.privacy_sentinel import start_privacy_monitor
        start_privacy_monitor()
    except Exception as e:
        print(f"[GUI] Error al iniciar monitor de privacidad: {e}")
        
    print("[GUI] Interfaz disponible en http://localhost:5000")