from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading

# Crear la aplicación Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'jarvis-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Estado actual de Jarvis
jarvis_state = {
    "status": "idle",        # idle, listening, thinking, speaking
    "transcript": "",        # Lo que el usuario ha dicho
    "response": "",          # Lo que Jarvis responde
}

# Ruta principal: sirve la página HTML
@app.route('/')
def index():
    return render_template('index.html')

# Función para actualizar el estado desde Jarvis
def update_state(status, transcript="", response=""):
    jarvis_state["status"] = status
    if transcript:
        jarvis_state["transcript"] = transcript
    if response:
        jarvis_state["response"] = response
    # Enviar el estado al navegador en tiempo real
    socketio.emit('state_update', jarvis_state)

# Cuando el navegador se conecta
@socketio.on('connect')
def handle_connect():
    emit('state_update', jarvis_state)
    print("[GUI] Navegador conectado")

# Arrancar el servidor en un hilo separado
def start_gui():
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

def run_gui_in_background():
    gui_thread = threading.Thread(target=start_gui, daemon=True)
    gui_thread.start()
    print("[GUI] Interfaz disponible en http://localhost:5000")