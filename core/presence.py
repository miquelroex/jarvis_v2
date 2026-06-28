"""
core/presence.py — Detección de Presencia por Webcam.

Jarvis vigila (si lo activas) la webcam y reacciona a quién hay delante: te da la
bienvenida cuando llegas, avisa si entra alguien más y nota cuando te quedas
solo. *"Bienvenido, señor."* / *"Detecto a alguien más en la sala."*

Sin dependencias nuevas: cuenta personas con Gemini Vision (la misma visión que
usa reticle_scan) sobre un frame de la webcam. La MÁQUINA DE ESTADOS de presencia
(con anti-parpadeo) y las frases son PURAS y testeables; la captura de la cámara y
la llamada a visión se aíslan y degradan con gracia (nunca se ejecutan en CI).

Fuera de alcance a propósito: reconocimiento facial de la IDENTIDAD concreta
("quién" es) — requiere face_recognition/dlib, no disponibles aquí. Esto detecta
PRESENCIA y número de personas, no identidad.
"""
import os
import re
import json
import logging
import threading

logger = logging.getLogger(__name__)

FRAME_PATH = "logs/presence_frame.png"

PRESENCE_THREAD = None
stop_event = threading.Event()
_monitor = None

_PHRASES = {
    "arrival": "Bienvenido, señor.",
    "departure": "Hasta luego, señor.",
    "companion": "Señor, detecto a alguien más en la sala.",
    "alone": "De nuevo a solas, señor.",
}

_VISION_PROMPT = (
    "¿Cuántas personas hay visibles en esta imagen de una webcam? Responde "
    'ÚNICAMENTE con un JSON válido, sin texto extra: {"people": <entero>}'
)


# ----------------------------------------------------------------------------
# Núcleo puro
# ----------------------------------------------------------------------------
def parse_person_count(raw: str) -> int:
    """Número de personas a partir de la respuesta del modelo. -1 si desconocido. Puro."""
    if not raw or not raw.strip():
        return -1
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", raw.strip()).strip()
    try:
        data = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            num = re.search(r"-?\d+", text)
            return int(num.group()) if num else -1
        try:
            data = json.loads(m.group())
        except Exception:
            return -1
    try:
        n = int(data.get("people"))
    except (TypeError, ValueError, AttributeError):
        return -1
    return max(0, n)


def event_phrase(event: str) -> str:
    """Frase Stark para un evento de presencia (puro)."""
    return _PHRASES.get(event, "")


class PresenceMonitor:
    """Máquina de estados de presencia con anti-parpadeo.

    observe(count) procesa una observación (nº de personas; <0 = desconocido) y
    devuelve la lista de eventos confirmados: 'arrival', 'departure',
    'companion' (entra alguien más), 'alone' (vuelves a estar solo). Un cambio
    sólo se confirma tras `confirm` observaciones iguales seguidas, para no
    dispararse por lecturas erráticas de la cámara."""

    def __init__(self, confirm: int = 2):
        self.confirm = max(1, confirm)
        self.count = 0
        self._pending = None
        self._pending_n = 0

    def observe(self, count: int):
        if count < 0:  # lectura fallida: no altera el estado
            return []
        if count == self.count:
            self._pending, self._pending_n = None, 0
            return []
        if count == self._pending:
            self._pending_n += 1
        else:
            self._pending, self._pending_n = count, 1
        if self._pending_n < self.confirm:
            return []
        prev = self.count
        self.count = count
        self._pending, self._pending_n = None, 0
        return self._events(prev, count)

    @staticmethod
    def _events(prev: int, count: int):
        events = []
        if prev == 0 and count >= 1:
            events.append("arrival")
        if prev >= 1 and count == 0:
            events.append("departure")
        if count > 1 and prev <= 1:
            events.append("companion")
        if count == 1 and prev > 1:
            events.append("alone")
        return events


# ----------------------------------------------------------------------------
# Captura / visión (aislado, nunca en CI)
# ----------------------------------------------------------------------------
def _capture_frame(path: str = FRAME_PATH) -> bool:
    """Captura un frame de la webcam a PNG (best-effort). True si lo logró."""
    try:
        import pygame
        import pygame.camera
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        pygame.camera.init()
        cams = pygame.camera.list_cameras()
        if not cams:
            return False
        cam = pygame.camera.Camera(cams[0])
        cam.start()
        surface = cam.get_image()
        cam.stop()
        pygame.image.save(surface, path)
        return True
    except Exception as e:
        logger.debug(f"[Presence] No se pudo capturar la webcam: {e}")
        return False


def _count_people(path: str = FRAME_PATH) -> int:
    """Cuenta personas en el frame con Gemini Vision. -1 si no se puede."""
    if not os.getenv("GOOGLE_API_KEY"):
        return -1
    try:
        from PIL import Image
        from google import genai
        img = Image.open(path)
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        model = os.getenv("JARVIS_MODEL_GEMINI", "gemini-3.5-flash")
        resp = client.models.generate_content(model=model, contents=[img, _VISION_PROMPT])
        return parse_person_count(resp.text or "")
    except Exception as e:
        logger.debug(f"[Presence] Falló el conteo por visión: {e}")
        return -1


def _observe_once() -> int:
    """Captura + cuenta. Devuelve el nº de personas (-1 si falla)."""
    if not _capture_frame():
        return -1
    return _count_people()


def get_presence_status() -> str:
    """Estado de presencia bajo demanda ("¿hay alguien?")."""
    n = _observe_once()
    if n < 0:
        return "No puedo ver la webcam ahora mismo, señor."
    if n == 0:
        return "No veo a nadie delante de la cámara, señor."
    if n == 1:
        return "Le veo a usted, señor. Nadie más en el encuadre."
    return f"Veo a {n} personas en el encuadre, señor."


# ----------------------------------------------------------------------------
# Entrega y daemon (aislado)
# ----------------------------------------------------------------------------
def _notify(message: str):
    import sys
    mod = sys.modules.get("gui.app")
    if mod is not None:
        try:
            mod.socketio.emit("presence_event", {"text": message})
        except Exception:
            pass
    if os.getenv("JARVIS_PRESENCE_VOICE", "true").lower() in ("true", "1", "yes"):
        try:
            from tools.voice import speak
            speak(message, disable_vad=True)
        except Exception:
            pass


def _presence_loop():
    global _monitor
    _monitor = PresenceMonitor(confirm=int(os.getenv("JARVIS_PRESENCE_CONFIRM", "2")))
    if stop_event.wait(timeout=10):
        return
    while not stop_event.is_set():
        try:
            for event in _monitor.observe(_observe_once()):
                phrase = event_phrase(event)
                if phrase:
                    _notify(phrase)
        except Exception as e:
            logger.error(f"[Presence] Error en el bucle: {e}")
        interval = int(os.getenv("JARVIS_PRESENCE_INTERVAL", "20"))
        if stop_event.wait(timeout=interval):
            break


def start_presence_daemon():
    """Lanza la detección de presencia. Off por defecto (JARVIS_PRESENCE_ENABLED):
    usa la webcam, así que es intrusivo y se activa explícitamente."""
    global PRESENCE_THREAD
    if os.getenv("JARVIS_PRESENCE_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Presence] Desactivado en .env.")
        return
    if PRESENCE_THREAD is not None and PRESENCE_THREAD.is_alive():
        return
    stop_event.clear()
    PRESENCE_THREAD = threading.Thread(target=_presence_loop, name="PresenceDaemon", daemon=True)
    PRESENCE_THREAD.start()
    logging.info("[Presence] Detección de presencia iniciada.")


def stop_presence_daemon():
    """Detiene la detección de presencia."""
    stop_event.set()