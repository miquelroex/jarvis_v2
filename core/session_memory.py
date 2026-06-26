"""
core/session_memory.py — Memoria de Sesión con Callbacks.

Jarvis recuerda lo que se ha dicho en los últimos minutos de la conversación y
lo enlaza de forma natural: "Como mencionó antes, señor, sobre el módulo de
red…". Da continuidad y sensación de que sigue el hilo.

A diferencia de core/memory.py (SQLite de largo plazo) y semantic_memory.py
(RAG por embeddings), esto es un buffer EN MEMORIA de los turnos recientes
(rotativo y con caducidad temporal). El motor de detección de callbacks es una
función PURA y testeable que opera sobre una lista de turnos.
"""
import os
import time
import unicodedata
import threading
from collections import deque

# Buffer rotativo de turnos {role, text, ts}. role ∈ {"user", "jarvis"}.
_MAX_TURNS = 40
TURNS = deque(maxlen=_MAX_TURNS)
_lock = threading.Lock()
_last_callback_topic = None  # evita repetir el mismo callback seguido

# Palabras vacías en español (no son "temas"). Se ignoran al extraer tópicos.
_STOPWORDS = {
    "para", "pero", "como", "cuando", "donde", "porque", "aunque", "entonces",
    "tambien", "tienes", "tiene", "tengo", "quiero", "puedes", "puedo", "hacer",
    "esto", "esta", "este", "esos", "esas", "estos", "estas", "eso", "señor",
    "jarvis", "favor", "ahora", "luego", "antes", "sobre", "menciono", "dijiste",
    "dije", "dijo", "vamos", "venga", "claro", "vale", "gracias", "bien", "mejor",
    "algo", "nada", "todo", "todos", "todas", "muy", "mas", "menos", "sido",
    "estar", "estoy", "estamos", "seria", "seria", "habia", "habias",
}


def normalize_text(text: str) -> str:
    """Minúsculas y sin acentos (puro)."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def extract_topics(text: str, min_len: int = 4):
    """Tokens significativos de un texto (temas candidatos), en orden y sin repetir.

    Minúsculas, sin acentos, sólo alfabéticos de longitud >= min_len que no sean
    palabras vacías. Puro."""
    norm = normalize_text(text or "")
    topics = []
    seen = set()
    word = []
    for ch in norm + " ":
        if ch.isalpha():
            word.append(ch)
            continue
        token = "".join(word)
        word = []
        if len(token) >= min_len and token not in _STOPWORDS and token not in seen:
            seen.add(token)
            topics.append(token)
    return topics


def build_callback_phrase(topic: str) -> str:
    """Frase de enlace natural para un tema (puro)."""
    return f"Como mencionó antes, señor, sobre {topic}…"


def find_callback(current_text, turns, now=None, window_seconds: int = 600,
                  skip_recent: int = 1, min_topic_len: int = 5):
    """Detecta un tema del mensaje actual ya tratado en un turno anterior. Puro.

    Recorre `turns` (más antiguos primero) dentro de la ventana temporal,
    saltando los `skip_recent` más recientes (el propio mensaje en curso), y
    devuelve {topic, phrase} para el primer tema relevante reaparecido, o None.
    Sólo considera temas de longitud >= min_topic_len para evitar ruido."""
    now = now if now is not None else time.time()
    current_topics = {t for t in extract_topics(current_text) if len(t) >= min_topic_len}
    if not current_topics:
        return None
    considered = turns[:-skip_recent] if skip_recent > 0 else list(turns)
    for turn in considered:
        ts = turn.get("ts", 0)
        if now - ts > window_seconds:
            continue  # demasiado antiguo
        past_topics = {t for t in extract_topics(turn.get("text", "")) if len(t) >= min_topic_len}
        shared = current_topics & past_topics
        if shared:
            topic = sorted(shared, key=len, reverse=True)[0]
            return {"topic": topic, "phrase": build_callback_phrase(topic)}
    return None


def summarize_topics(turns, top_k: int = 5, min_len: int = 5):
    """Temas más frecuentes de una lista de turnos, por frecuencia. Puro."""
    from collections import Counter
    counts = Counter()
    for turn in turns:
        for t in extract_topics(turn.get("text", ""), min_len=min_len):
            counts[t] += 1
    return [t for t, _ in counts.most_common(top_k)]


# ----------------------------------------------------------------------------
# Estado vivo (buffer en memoria)
# ----------------------------------------------------------------------------
def record_turn(role: str, text: str, ts=None):
    """Registra un turno de la conversación en el buffer (best-effort)."""
    if not text or not text.strip():
        return
    with _lock:
        TURNS.append({"role": role, "text": text.strip(), "ts": ts if ts is not None else time.time()})


def maybe_callback(current_text: str):
    """Devuelve una frase de callback si el mensaje retoma un tema reciente.

    Conservador: no repite el mismo tema dos veces seguidas, sólo activo si
    JARVIS_SESSION_CALLBACKS no está desactivado. Lee el buffer vivo."""
    global _last_callback_topic
    if os.getenv("JARVIS_SESSION_CALLBACKS", "true").lower() not in ("true", "1", "yes"):
        return None
    with _lock:
        turns = list(TURNS)
    window = int(os.getenv("JARVIS_SESSION_WINDOW", "600"))
    cb = find_callback(current_text, turns, window_seconds=window)
    if not cb:
        return None
    if cb["topic"] == _last_callback_topic:
        return None  # ya lo enlazamos hace nada
    _last_callback_topic = cb["topic"]
    return cb["phrase"]


def session_summary() -> str:
    """Resumen hablado de los temas tratados en la sesión reciente."""
    with _lock:
        turns = list(TURNS)
    topics = summarize_topics(turns)
    if not topics:
        return "Aún no hemos hablado de gran cosa, señor."
    return "En los últimos minutos hemos hablado de: " + ", ".join(topics) + ", señor."


def clear_session():
    """Vacía el buffer de la sesión (p. ej. al reiniciar una conversación)."""
    global _last_callback_topic
    with _lock:
        TURNS.clear()
    _last_callback_topic = None
