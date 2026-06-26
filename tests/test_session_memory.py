"""Tests de core/session_memory.py — Memoria de Sesión con Callbacks."""
import time

import core.session_memory as sm


def setup_function(_):
    sm.clear_session()


# ---------------------------------------------------------------- normalize / topics
def test_normalize_text_strips_accents():
    assert sm.normalize_text("Módulo de Red") == "modulo de red"
    assert sm.normalize_text("") == ""


def test_extract_topics_filters_stopwords_and_short():
    topics = sm.extract_topics("Quiero revisar el módulo de red ahora")
    assert "modulo" in topics
    assert "revisar" in topics
    # 'quiero', 'ahora', 'sobre' son stopwords; 'de', 'el' demasiado cortos.
    assert "quiero" not in topics
    assert "ahora" not in topics
    assert "de" not in topics


def test_extract_topics_no_duplicates_in_order():
    topics = sm.extract_topics("red red network red")
    assert topics == ["red"] or "red" not in topics  # 'red' len 3 < 4 -> excluido
    topics2 = sm.extract_topics("network firewall network firewall")
    assert topics2 == ["network", "firewall"]


# ---------------------------------------------------------------- build_callback_phrase
def test_build_callback_phrase():
    assert sm.build_callback_phrase("red") == "Como mencionó antes, señor, sobre red…"


# ---------------------------------------------------------------- find_callback (puro)
def _turn(text, ts):
    return {"role": "user", "text": text, "ts": ts}


def test_find_callback_detects_returning_topic():
    now = 1000.0
    turns = [
        _turn("hablemos del modulo de escaneo", now - 300),
        _turn("vale, cambiemos de tema", now - 200),
        _turn("y el escaneo que comentabas", now),  # turno actual (se salta)
    ]
    cb = sm.find_callback("y el escaneo que comentabas", turns, now=now)
    assert cb is not None
    assert cb["topic"] == "escaneo"
    assert "escaneo" in cb["phrase"]


def test_find_callback_none_when_no_overlap():
    now = 1000.0
    turns = [_turn("hablemos del clima", now - 100), _turn("otra cosa distinta", now)]
    assert sm.find_callback("otra cosa distinta", turns, now=now) is None


def test_find_callback_respects_window():
    now = 1000.0
    turns = [_turn("modulo de escaneo importante", now - 5000), _turn("retomo el escaneo", now)]
    # El turno relevante quedó fuera de la ventana de 600s.
    assert sm.find_callback("retomo el escaneo", turns, now=now, window_seconds=600) is None


def test_find_callback_skips_recent():
    now = 1000.0
    # Sólo está el turno actual: skip_recent=1 lo descarta y no hay pasado.
    turns = [_turn("escaneo escaneo", now)]
    assert sm.find_callback("escaneo escaneo", turns, now=now) is None


def test_find_callback_ignores_short_topics():
    now = 1000.0
    turns = [_turn("la red", now - 100), _turn("la red otra vez", now)]
    # 'red' tiene 3 letras (< min_topic_len=5) -> no es callback.
    assert sm.find_callback("la red otra vez", turns, now=now) is None


# ---------------------------------------------------------------- summarize_topics
def test_summarize_topics_by_frequency():
    turns = [
        _turn("modulo de escaneo", 1),
        _turn("mas sobre escaneo y firewall", 2),
        _turn("firewall y escaneo otra vez", 3),
    ]
    topics = sm.summarize_topics(turns, top_k=2)
    assert topics[0] == "escaneo"  # el más frecuente
    assert "firewall" in topics


def test_summarize_topics_empty():
    assert sm.summarize_topics([]) == []


# ---------------------------------------------------------------- buffer vivo
def test_record_turn_ignores_empty():
    sm.record_turn("user", "   ")
    assert len(sm.TURNS) == 0


def test_record_turn_appends():
    sm.record_turn("user", "hola")
    sm.record_turn("jarvis", "buenas")
    assert len(sm.TURNS) == 2
    assert sm.TURNS[0]["role"] == "user"


def test_buffer_caps_at_maxlen():
    for i in range(sm._MAX_TURNS + 10):
        sm.record_turn("user", f"mensaje numero {i}")
    assert len(sm.TURNS) == sm._MAX_TURNS


# ---------------------------------------------------------------- maybe_callback
def test_maybe_callback_returns_phrase(monkeypatch):
    monkeypatch.setenv("JARVIS_SESSION_CALLBACKS", "true")
    now = time.time()
    sm.record_turn("user", "revisemos el firewall del servidor", now - 100)
    sm.record_turn("jarvis", "de acuerdo", now - 90)
    sm.record_turn("user", "volvamos al firewall", now)
    phrase = sm.maybe_callback("volvamos al firewall")
    assert phrase is not None
    assert "firewall" in phrase


def test_maybe_callback_not_repeated(monkeypatch):
    monkeypatch.setenv("JARVIS_SESSION_CALLBACKS", "true")
    now = time.time()
    sm.record_turn("user", "el firewall del servidor", now - 100)
    sm.record_turn("user", "firewall otra vez", now)
    first = sm.maybe_callback("firewall otra vez")
    assert first is not None
    # Mismo tema seguido: no se repite.
    sm.record_turn("user", "y mas firewall", now + 1)
    assert sm.maybe_callback("y mas firewall") is None


def test_maybe_callback_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_SESSION_CALLBACKS", "false")
    now = time.time()
    sm.record_turn("user", "el firewall del servidor", now - 100)
    sm.record_turn("user", "firewall otra vez", now)
    assert sm.maybe_callback("firewall otra vez") is None


# ---------------------------------------------------------------- session_summary
def test_session_summary_empty():
    assert "Aún no hemos hablado" in sm.session_summary()


def test_session_summary_lists_topics():
    sm.record_turn("user", "modulo de escaneo y firewall")
    sm.record_turn("user", "mas escaneo")
    out = sm.session_summary()
    assert "escaneo" in out
    assert out.endswith("señor.")


# ---------------------------------------------------------------- clear_session
def test_clear_session_resets():
    sm.record_turn("user", "algo del firewall")
    sm.record_turn("user", "firewall")
    sm.maybe_callback("firewall")
    sm.clear_session()
    assert len(sm.TURNS) == 0
    assert sm._last_callback_topic is None
