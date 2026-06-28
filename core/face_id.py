"""
core/face_id.py — Reconocimiento facial LOCAL y privado (OpenCV LBPH).

Capa de identidad sobre la Detección de Presencia: enrolas una cara una vez
("recuérdame, soy el señor") y a partir de ahí Jarvis distingue quién aparece —
*"Bienvenido, señor"* frente a *"detecto a un desconocido"*. Todo el
procesamiento es LOCAL (nada sale del equipo), a diferencia de la opción por
Gemini Vision; tus caras nunca van a la nube.

OpenCV (opencv-contrib-python) es una dependencia OPCIONAL de importación
perezosa: si no está instalada, los comandos lo dicen con la orden de
instalación, y el resto de Jarvis no se ve afectado. La lógica de resolución de
identidad y la gestión de etiquetas son PURAS y testeables; la detección,
entrenamiento y predicción con OpenCV se aíslan (nunca se ejecutan en CI).

Instalación para activarlo:  pip install opencv-contrib-python
"""
import os
import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("logs/faces")
MODEL_PATH = DATA_DIR / "lbph.yml"
LABELS_PATH = DATA_DIR / "labels.json"
_lock = threading.Lock()

# LBPH: distancia (confidence) MENOR = mejor coincidencia. Umbral por defecto.
DEFAULT_THRESHOLD = float(os.getenv("JARVIS_FACE_THRESHOLD", "70"))


# ----------------------------------------------------------------------------
# Lógica de identidad y etiquetas (pura)
# ----------------------------------------------------------------------------
def resolve_identity(label_id, confidence, labels: dict, threshold: float) -> str:
    """Nombre reconocido o 'desconocido' a partir de una predicción LBPH. Puro.

    En LBPH la `confidence` es una DISTANCIA: cuanto menor, mejor. Sólo se acepta
    si está por debajo del umbral y la etiqueta está registrada."""
    if label_id is None or confidence is None:
        return "desconocido"
    if confidence <= threshold:
        return (labels or {}).get(str(label_id), "desconocido")
    return "desconocido"


def next_label_id(labels: dict) -> int:
    """Siguiente id de etiqueta libre (puro)."""
    ids = [int(k) for k in (labels or {})]
    return (max(ids) + 1) if ids else 0


def add_label(labels: dict, name: str):
    """Registra `name` reutilizando su id si ya existe. Devuelve (labels, id). Puro."""
    labels = dict(labels or {})
    for k, v in labels.items():
        if v.strip().lower() == name.strip().lower():
            return labels, int(k)
    nid = next_label_id(labels)
    labels[str(nid)] = name.strip()
    return labels, nid


def greeting_for(name: str) -> str:
    """Saludo según la identidad reconocida (puro)."""
    if not name or name == "desconocido":
        return "Señor, detecto a alguien que no reconozco."
    return f"Bienvenido, {name}."


def is_known(name: str) -> bool:
    """¿La identidad corresponde a alguien reconocido? (puro)."""
    return bool(name) and name != "desconocido"


# ----------------------------------------------------------------------------
# Persistencia de etiquetas (aislado de disco, pero formato simple)
# ----------------------------------------------------------------------------
def load_labels() -> dict:
    try:
        if LABELS_PATH.exists():
            return json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug(f"[FaceID] No se pudieron leer las etiquetas: {e}")
    return {}


def save_labels(labels: dict):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LABELS_PATH.write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[FaceID] No se pudieron guardar las etiquetas: {e}")


# ----------------------------------------------------------------------------
# OpenCV (opcional, perezoso, aislado)
# ----------------------------------------------------------------------------
def _cv2():
    """Importa cv2 de forma perezosa. Lanza si no está instalado."""
    import cv2
    return cv2


def is_available() -> bool:
    """¿Está OpenCV disponible para reconocimiento facial?"""
    try:
        cv2 = _cv2()
        return hasattr(cv2, "face")  # face está en opencv-contrib
    except Exception:
        return False


_INSTALL_MSG = ("Necesito OpenCV para el reconocimiento facial, señor. "
                "Instálelo con: pip install opencv-contrib-python")


def _detect_faces(gray):
    """Devuelve las cajas (x,y,w,h) de caras en una imagen en gris (aislado)."""
    cv2 = _cv2()
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    return list(cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60)))


def _largest_face_roi(cv2, gray, faces):
    """ROI en gris (100x100) de la cara más grande, o None."""
    if not len(faces):
        return None
    x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
    return cv2.resize(gray[y:y + h, x:x + w], (100, 100))


def enroll(name: str, samples: int = 20) -> str:
    """Enrola una cara: captura varias muestras de la webcam y reentrena el modelo."""
    if not name or not name.strip():
        return "¿Con qué nombre le registro, señor?"
    if not is_available():
        return _INSTALL_MSG
    try:
        import time
        import numpy as np
        cv2 = _cv2()
        from core.presence import _capture_frame, FRAME_PATH

        with _lock:
            labels = load_labels()
            labels, label_id = add_label(labels, name)
            sample_dir = DATA_DIR / str(label_id)
            sample_dir.mkdir(parents=True, exist_ok=True)

            captured = 0
            for _ in range(samples * 3):
                if captured >= samples:
                    break
                if not _capture_frame(FRAME_PATH):
                    continue
                gray = cv2.cvtColor(cv2.imread(FRAME_PATH), cv2.COLOR_BGR2GRAY)
                roi = _largest_face_roi(cv2, gray, _detect_faces(gray))
                if roi is not None:
                    cv2.imwrite(str(sample_dir / f"{captured}.png"), roi)
                    captured += 1
                time.sleep(0.1)

            if captured == 0:
                return "No he conseguido ver su cara con claridad, señor. Inténtelo de nuevo."

            # Reentrenar LBPH con TODAS las muestras de todas las etiquetas.
            faces, ids = [], []
            for lid in labels:
                for img in (DATA_DIR / lid).glob("*.png"):
                    faces.append(cv2.imread(str(img), cv2.IMREAD_GRAYSCALE))
                    ids.append(int(lid))
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.train(faces, np.array(ids))
            recognizer.write(str(MODEL_PATH))
            save_labels(labels)
        return f"Le he memorizado, {name}. Ya sabré reconocerle, señor."
    except Exception as e:
        logger.warning(f"[FaceID] Error al enrolar: {e}")
        return f"No he podido completar el registro facial, señor: {e}"


def identify(path: str = None) -> str:
    """Identifica a la persona más prominente del frame. Devuelve un nombre o 'desconocido'."""
    if not is_available() or not MODEL_PATH.exists():
        return "desconocido"
    try:
        cv2 = _cv2()
        from core.presence import _capture_frame, FRAME_PATH
        path = path or FRAME_PATH
        if path == FRAME_PATH and not _capture_frame(FRAME_PATH):
            return "desconocido"
        gray = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2GRAY)
        roi = _largest_face_roi(cv2, gray, _detect_faces(gray))
        if roi is None:
            return "desconocido"
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(str(MODEL_PATH))
        label_id, confidence = recognizer.predict(roi)
        return resolve_identity(label_id, confidence, load_labels(), DEFAULT_THRESHOLD)
    except Exception as e:
        logger.debug(f"[FaceID] Error al identificar: {e}")
        return "desconocido"


def identify_greeting():
    """Saludo personalizado si se reconoce a alguien; None si no hay nada que decir."""
    if not is_available() or not MODEL_PATH.exists():
        return None
    name = identify()
    return greeting_for(name)


# ----------------------------------------------------------------------------
# Comandos por voz
# ----------------------------------------------------------------------------
def who_is_there() -> str:
    """Responde a "¿quién soy?" / "¿quién hay?"."""
    if not is_available():
        return _INSTALL_MSG
    if not MODEL_PATH.exists():
        return "Aún no he memorizado ninguna cara, señor. Dígame: 'recuérdame, soy el señor'."
    name = identify()
    if is_known(name):
        return f"Es usted, {name}." if name == "señor" else f"Le reconozco: {name}, señor."
    return "No reconozco a quien tengo delante, señor."
