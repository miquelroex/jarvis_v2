"""Tests de core/insights.py — "Señor, detecto un patrón"."""
import sys
import types
from datetime import datetime

import core.insights as ins


def _ev(action, hour=10, weekday=0, ts=None):
    return {"action": action, "hour": hour, "weekday": weekday,
            "ts": (ts or datetime(2026, 6, 1, 10)).isoformat()}


# ---------------------------------------------------------------- _phrase / _part_of_day
def test_phrase_app_prefix():
    assert ins._phrase("app:code") == "abrir code"
    assert ins._phrase("web:github") == "abrir github"
    assert ins._phrase("compilar") == "compilar"
    assert ins._phrase("") == ""


def test_part_of_day():
    assert ins._part_of_day(8) == "por las mañanas"
    assert ins._part_of_day(13) == "al mediodía"
    assert ins._part_of_day(16) == "por las tardes"
    assert ins._part_of_day(22) == "por las noches"
    assert ins._part_of_day(3) == "de madrugada"


# ---------------------------------------------------------------- weekday
def test_weekday_pattern_detected():
    events = [_ev("compilar", weekday=0) for _ in range(5)]
    out = ins.detect_weekday_patterns(events, min_count=4, dominance=0.5)
    assert len(out) == 1
    assert out[0]["kind"] == "weekday"
    assert "lunes" in out[0]["text"]
    assert out[0]["score"] == 5


def test_weekday_below_min_count():
    events = [_ev("compilar", weekday=0) for _ in range(3)]
    assert ins.detect_weekday_patterns(events, min_count=4) == []


def test_weekday_no_dominance():
    # Repartido entre lunes/martes/miércoles/jueves: ningún día domina.
    events = ([_ev("x", weekday=0)] * 2 + [_ev("x", weekday=1)] * 2 +
              [_ev("x", weekday=2)] * 2 + [_ev("x", weekday=3)] * 2)
    assert ins.detect_weekday_patterns(events, min_count=4, dominance=0.5) == []


def test_weekday_ignores_invalid_weekday():
    events = [_ev("x", weekday=None) for _ in range(5)]
    assert ins.detect_weekday_patterns(events) == []


def test_weekday_ignores_out_of_range():
    events = [_ev("x", weekday=7) for _ in range(5)]  # 7 fuera de 0..6
    assert ins.detect_weekday_patterns(events) == []


# ---------------------------------------------------------------- hour
def test_hour_pattern_detected():
    events = [_ev("x", hour=23) for _ in range(15)]
    out = ins.detect_hour_patterns(events, min_total=12, dominance=0.3)
    assert len(out) == 1
    assert out[0]["kind"] == "hour"
    assert "23:00" in out[0]["text"]


def test_hour_below_min_total():
    events = [_ev("x", hour=10) for _ in range(5)]
    assert ins.detect_hour_patterns(events, min_total=12) == []


def test_hour_no_dominance():
    events = [_ev("x", hour=h) for h in range(24)]  # uniforme
    assert ins.detect_hour_patterns(events, min_total=12, dominance=0.3) == []


def test_hour_ignores_out_of_range():
    events = [_ev("x", hour=25) for _ in range(15)]  # 25 fuera de 0..23
    assert ins.detect_hour_patterns(events, min_total=12) == []


# ---------------------------------------------------------------- sequence
def test_sequence_pattern_detected():
    seq = [_ev("app:code"), _ev("web:github")] * 3
    out = ins.detect_sequence_patterns(seq, min_count=3)
    assert len(out) == 1
    assert out[0]["kind"] == "sequence"
    assert "rutina" in out[0]["text"]
    assert out[0]["score"] == 3 * 2


def test_sequence_ignores_identical_consecutive():
    seq = [_ev("compilar")] * 5
    assert ins.detect_sequence_patterns(seq, min_count=2) == []


def test_sequence_below_min_count():
    seq = [_ev("a"), _ev("b"), _ev("a"), _ev("b")]  # par a->b x2
    assert ins.detect_sequence_patterns(seq, min_count=3) == []


def test_sequence_caps_at_top_k():
    # Tres pares distintos cada uno x3; el tope top_k=2 debe recortar.
    seq = ([_ev("a"), _ev("b")] * 3 + [_ev("c"), _ev("d")] * 3 +
           [_ev("e"), _ev("f")] * 3)
    out = ins.detect_sequence_patterns(seq, min_count=3, top_k=2)
    assert len(out) == 2


# ---------------------------------------------------------------- errors
def test_error_pattern_detected():
    store = {"sig1": {"error": "ValueError: boom", "count": 5, "solution": "fix it"}}
    out = ins.detect_error_patterns(store, min_count=3)
    assert len(out) == 1
    assert out[0]["kind"] == "error"
    assert "5 veces" in out[0]["text"]
    assert "ya sabemos" in out[0]["text"]


def test_error_below_min_count():
    store = {"s": {"error": "x", "count": 2}}
    assert ins.detect_error_patterns(store, min_count=3) == []


def test_error_at_min_count_boundary():
    store = {"s": {"error": "x", "count": 3}}  # == min_count se incluye
    assert len(ins.detect_error_patterns(store, min_count=3)) == 1


def test_error_label_fallback_when_empty():
    store = {"s": {"error": "   ", "count": 4}}
    out = ins.detect_error_patterns(store, min_count=3)
    assert "un error recurrente" in out[0]["text"]
    assert "aún sin solución" in out[0]["text"]


def test_error_caps_at_top_k():
    store = {f"s{i}": {"error": f"e{i}", "count": 9 - i} for i in range(4)}
    out = ins.detect_error_patterns(store, min_count=3, top_k=2)
    assert len(out) == 2
    # Ordenados por count desc: el primero es el de mayor count.
    assert "9 veces" in out[0]["text"]


def test_error_empty_store():
    assert ins.detect_error_patterns({}) == []
    assert ins.detect_error_patterns(None) == []


# ---------------------------------------------------------------- build / format
def test_build_insights_ranks_and_limits():
    events = ([_ev("app:code"), _ev("web:github")] * 4 +
              [_ev("compilar", weekday=0) for _ in range(5)])
    store = {"s": {"error": "Boom", "count": 6}}
    out = ins.build_insights(events, store, top_k=2)
    assert len(out) == 2
    # Ordenado por score desc.
    assert out[0]["score"] >= out[1]["score"]


def test_build_insights_dedupes_by_text():
    # Misma secuencia repetida no debe duplicar el texto.
    events = [_ev("a"), _ev("b")] * 5
    out = ins.build_insights(events, {})
    texts = [i["text"] for i in out]
    assert len(texts) == len(set(texts))


def test_build_insights_dedupe_keeps_higher_score(monkeypatch):
    # Dos insights con idéntico texto pero distinto score: gana el mayor.
    monkeypatch.setattr(ins, "detect_sequence_patterns",
                        lambda ev: [{"kind": "x", "score": 2, "text": "MISMO"}])
    monkeypatch.setattr(ins, "detect_weekday_patterns",
                        lambda ev: [{"kind": "x", "score": 9, "text": "MISMO"}])
    monkeypatch.setattr(ins, "detect_hour_patterns", lambda ev: [])
    monkeypatch.setattr(ins, "detect_error_patterns", lambda st: [])
    out = ins.build_insights([], {})
    assert len(out) == 1
    assert out[0]["score"] == 9


def test_format_for_voice_empty():
    assert ins.format_for_voice([]) == ""


def test_format_for_voice_joins():
    items = [{"text": "Uno."}, {"text": "Dos."}]
    assert ins.format_for_voice(items) == "Uno. Dos."


def test_get_insights_report_no_data(monkeypatch):
    monkeypatch.setattr(ins, "_load_events", lambda: [])
    monkeypatch.setattr(ins, "_load_error_store", lambda: {})
    report = ins.get_insights_report()
    assert "suficientes hábitos" in report


def test_get_insights_report_with_data(monkeypatch):
    events = [_ev("app:code"), _ev("web:github")] * 4
    monkeypatch.setattr(ins, "_load_events", lambda: events)
    monkeypatch.setattr(ins, "_load_error_store", lambda: {})
    report = ins.get_insights_report()
    assert "rutina" in report


# ---------------------------------------------------------------- delivery / daemon
def test_emit_gui_no_module_no_crash(monkeypatch):
    monkeypatch.delitem(sys.modules, "gui.app", raising=False)
    ins._emit_gui({"kind": "x", "text": "hola"})  # no debe lanzar


def test_emit_gui_emits(monkeypatch):
    captured = {}
    fake = types.ModuleType("gui.app")
    fake.socketio = types.SimpleNamespace(
        emit=lambda ev, payload: captured.update({"ev": ev, "payload": payload}))
    # setitem auto-restaura el módulo original tras el test (no contamina sys.modules).
    monkeypatch.setitem(sys.modules, "gui.app", fake)
    ins._emit_gui({"kind": "hour", "text": "pico"})
    assert captured["ev"] == "insight_detected"
    assert captured["payload"]["text"] == "pico"


def test_deliver_voice_gated_off(monkeypatch):
    monkeypatch.setenv("JARVIS_INSIGHTS_VOICE", "false")
    monkeypatch.setattr(ins, "_emit_gui", lambda i: None)
    # No debe intentar hablar; si lo hiciera sin tools.voice no pasa nada, pero
    # comprobamos que simplemente no lanza.
    ins._deliver({"kind": "x", "text": "y"})


def test_start_daemon_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_INSIGHTS_ENABLED", "false")
    ins.INSIGHT_THREAD = None
    ins.start_insights_daemon()
    assert ins.INSIGHT_THREAD is None


def test_stop_daemon_sets_event():
    ins.stop_event.clear()
    ins.stop_insights_daemon()
    assert ins.stop_event.is_set()
    ins.stop_event.clear()
