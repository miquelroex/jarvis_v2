"""
core/visual_memory.py — Memoria Visual ("¿dónde dejé las llaves?").

Jarvis observa la escena por la webcam (a demanda o periódicamente), reconoce los
objetos destacados y DÓNDE están, y lo recuerda con su hora. Luego puedes
preguntarle: *"¿dónde dejé las llaves?" → "Sobre la mesa, señor, hace veinte
minutos."*. Reutiliza la visión de Gemini (sin dependencias nuevas).

El parseo de la escena, la búsqueda del objeto y el tiempo relativo son funciones
PURAS y testeables; la captura de la cámara, la llamada a visión y el daemon se
aíslan y degradan con gracia (nunca en CI). Registro local en
logs/visual_memory.jsonl.
"""
import os
import re
import json
import time
import logging
import threading
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_FILE = Path("logs/visual_memory.jsonl")
_lock = threading.Lock()

VISUAL_THREAD = None
stop_event = threading.Event()

# Palabras de la pregunta que NO son el objeto buscado.
_STOPWORDS = {
    "donde", "deje", "dejo", "dejado", "deja", "puse", "puesto", "esta", "estan",
    "este", "estos", "estas", "mis", "mi", "tus", "el", "la", "los", "las", "un",
    "una", "unos", "unas", "he", "has", "visto", "ver", "ves", "viste", "encuentro",
    "encuentra", "hay", "algun", "alguna", "que", "del", "de", "con", "por", "para",
    "senor", "jarvis", "recuerdas", "sabes", "esta",
}

_VISION_PROMPT = (
    "Observa esta imagen de una webcam y lista los objetos personales DESTACADOS "
    "que ves y dónde están. Responde ÚNICAMENTE con JSON válido, sin texto extra:\n"
    '{"objetos": [{"objeto": "<nombre corto>", "lugar": "<dónde está>"}]}'
)


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _tokens(text: str, min_len: int = 3):
    """Tokens significativos (sin stopwords, sin acentos) de un texto. Puro."""
    out = []
    for raw in re.findall(r"[a-z]+", _normalize(text)):
        if len(raw) >= min_len and raw not in _STOPWORDS:
            out.append(raw)
    return out


# ----------------------------------------------------------------------------
# Parseo y búsqueda (puro)
# ----------------------------------------------------------------------------
def parse_scene(raw: str):
    """Lista de {object, location} a partir del JSON del modelo (tolerante). Puro."""
    if not raw or not raw.strip():
        return []
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", raw.strip()).strip()
    try:
        data = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group())
        except Exception:
            return []
    items = data.get("objetos", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        obj = str(it.get("objeto", "")).strip()
        loc = str(it.get("lugar", "")).strip()
        if obj:
            out.append({"object": obj[:60], "location": (loc or "en algún lugar")[:120]})
    return out


def relative_time(seconds: float) -> str:
    """Expresión natural de una antigüedad en segundos (puro)."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "hace un momento"
    if seconds < 3600:
        m = seconds // 60
        return f"hace {m} minuto" + ("s" if m != 1 else "")
    if seconds < 86400:
        h = seconds // 3600
        return f"hace {h} hora" + ("s" if h != 1 else "")
    d = seconds // 86400
    return f"hace {d} día" + ("s" if d != 1 else "")


def find_object(query: str, observations, now: float = None):
    """Observación más reciente cuyo objeto casa con la pregunta, o None. Puro.

    Casa por solapamiento de tokens significativos entre la pregunta y el nombre
    del objeto observado."""
    qtokens = set(_tokens(query))
    if not qtokens:
        return None
    best = None
    for obs in observations or []:
        otokens = set(_tokens(obs.get("object", "")))
        if qtokens & otokens:
            if best is None or obs.get("ts", 0) > best.get("ts", 0):
                best = obs
    return best


def format_answer(query: str, observations, now: float = None) -> str:
    """Respuesta a "¿dónde está/dejé X?" a partir de las observaciones (puro)."""
    now = now if now is not None else time.time()
    obs = find_object(query, observations, now)
    if not obs:
        return "No recuerdo haber visto eso, señor. ¿Quiere que observe la escena?"
    cuando = relative_time(now - obs.get("ts", now))
    return f"Su {obs['object']}, señor: {obs['location']}, {cuando}."


def summarize_recent(observations, top_k: int = 5) -> str:
    """Resumen de lo último observado (puro)."""
    if not observations:
        return "Aún no he observado nada, señor."
    recientes = sorted(observations, key=lambda o: o.get("ts", 0), reverse=True)[:top_k]
    partes = [f"{o['object']} ({o['location']})" for o in recientes]
    return "Lo último que he visto, señor: " + "; ".join(partes) + "."


# ----------------------------------------------------------------------------
# Persistencia (aislada)
# ----------------------------------------------------------------------------
def record_observations(items, ts: float = None):
    """Guarda observaciones {object, location} con su hora en el registro."""
    ts = ts if ts is not None else time.time()
    if not items:
        return
    try:
        with _lock:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                for it in items:
                    rec = {"object": it["object"], "location": it["location"], "ts": ts}
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[VisualMemory] No se pudo registrar la escena: {e}")


def load_observations(limit: int = 2000):
    if not LOG_FILE.exists():
        return []
    out = []
    try:
        with _lock:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"[VisualMemory] No se pudo leer el registro: {e}")
    return out


# ----------------------------------------------------------------------------
# Captura / visión (aislado, nunca en CI)
# ----------------------------------------------------------------------------
def _analyze_scene() -> list:
    """Captura un frame y devuelve los objetos detectados (vía Gemini). [] si falla."""
    if not os.getenv("GOOGLE_API_KEY"):
        return []
    try:
        from core.presence import _capture_frame, FRAME_PATH
        if not _capture_frame(FRAME_PATH):
            return []
        from PIL import Image
        from google import genai
        img = Image.open(FRAME_PATH)
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        model = os.getenv("JARVIS_MODEL_GEMINI", "gemini-3.5-flash")
        resp = client.models.generate_content(model=model, contents=[img, _VISION_PROMPT])
        return parse_scene(resp.text or "")
    except Exception as e:
        logger.debug(f"[VisualMemory] Falló el análisis de escena: {e}")
        return []


def observe_now() -> str:
    """Observa la escena a demanda y registra lo que ve."""
    items = _analyze_scene()
    if not items:
        return "No he podido observar la escena, señor."
    record_observations(items)
    nombres = ", ".join(i["object"] for i in items[:5])
    return f"Anotado, señor. He visto: {nombres}."


def where_is(query: str) -> str:
    """Responde a "¿dónde dejé/está X?"."""
    return format_answer(query, load_observations())


def recent_scene() -> str:
    return summarize_recent(load_observations())


# ----------------------------------------------------------------------------
# Daemon opcional (observación periódica)
# ----------------------------------------------------------------------------
def _visual_loop():
    if stop_event.wait(timeout=15):
        return
    while not stop_event.is_set():
        try:
            items = _analyze_scene()
            if items:
                record_observations(items)
        except Exception as e:
            logger.error(f"[VisualMemory] Error en el bucle: {e}")
        interval = int(os.getenv("JARVIS_VISUAL_MEMORY_INTERVAL", "120"))
        if stop_event.wait(timeout=interval):
            break


def start_visual_memory_daemon():
    """Lanza la observación periódica. Off por defecto (JARVIS_VISUAL_MEMORY_ENABLED):
    usa la webcam, así que es intrusivo."""
    global VISUAL_THREAD
    if os.getenv("JARVIS_VISUAL_MEMORY_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[VisualMemory] Desactivado en .env.")
        return
    if VISUAL_THREAD is not None and VISUAL_THREAD.is_alive():
        return
    stop_event.clear()
    VISUAL_THREAD = threading.Thread(target=_visual_loop, name="VisualMemoryDaemon", daemon=True)
    VISUAL_THREAD.start()
    logging.info("[VisualMemory] Memoria visual iniciada.")


def stop_visual_memory_daemon():
    """Detiene la observación periódica."""
    stop_event.set()
