"""Tests de core/world_model.py — Cerebro de Estado Central."""
import core.world_model as wm


def _state(**over):
    base = {
        "system": {"ram": 40.0, "cpu": 12.0, "uptime_seconds": 3700},
        "services": {"running": 12, "stopped": 0, "disabled": 5},
        "threat": {"level": "green", "reasons": []},
        "project": {"is_repo": True, "repo_name": "jarvis", "branch": "main", "dirty_count": 3},
        "productivity": {"top": "Proyecto: jarvis", "total_seconds": 5400},
        "network": {"devices": 4, "unknown": 1},
        "watches": {"count": 2, "labels": ["fichero a.py", "puerto 80"]},
        "usage": {"calls": 14},
    }
    base.update(over)
    return base


# ---------------------------------------------------------------- _fmt_uptime
def test_fmt_uptime():
    assert wm._fmt_uptime(3700) == "1h 01m"
    assert wm._fmt_uptime(300) == "5m"
    assert wm._fmt_uptime("bad") == "0m"
    assert wm._fmt_uptime(-5) == "0m"


# ---------------------------------------------------------------- overall_status
def test_overall_status_nominal():
    assert wm.overall_status(_state()) == "nominal"


def test_overall_status_critical_threat():
    assert wm.overall_status(_state(threat={"level": "red", "reasons": []})) == "critical"


def test_overall_status_critical_ram():
    assert wm.overall_status(_state(system={"ram": 95})) == "critical"


def test_overall_status_advisory_amber():
    assert wm.overall_status(_state(threat={"level": "amber", "reasons": ["x"]})) == "advisory"


def test_overall_status_advisory_stopped_service():
    assert wm.overall_status(_state(services={"running": 10, "stopped": 2})) == "advisory"


def test_overall_status_handles_bad_ram():
    assert wm.overall_status(_state(system={"ram": None})) == "nominal"


# ---------------------------------------------------------------- build_facts
def test_build_facts_includes_domains():
    facts = wm.build_facts(_state())
    joined = " | ".join(facts)
    assert "RAM del sistema al 40.0%" in joined
    assert "CPU al 12.0%" in joined
    assert "12 servicios activos" in joined
    assert "nivel de amenaza VERDE" in joined
    assert "proyecto jarvis" in joined and "rama main" in joined
    assert "3 cambios sin confirmar" in joined
    assert "foco de hoy: Proyecto: jarvis" in joined
    assert "4 dispositivos en red" in joined and "1 desconocidos" in joined
    assert "2 vigilancia(s) activa(s)" in joined
    assert "14 llamadas de IA hoy" in joined


def test_build_facts_threat_with_reasons():
    facts = wm.build_facts(_state(threat={"level": "red", "reasons": ["RAM crítica", "intrusos"]}))
    joined = " | ".join(facts)
    assert "nivel de amenaza ROJA" in joined
    assert "RAM crítica" in joined


def test_build_facts_omits_empty():
    minimal = {"system": {}, "services": {}, "threat": {"level": "green"},
               "project": {"is_repo": False}, "productivity": {}, "network": {},
               "watches": {}, "usage": {}}
    facts = wm.build_facts(minimal)
    # Sólo el hecho de amenaza verde sobrevive; nada de proyecto/red/etc.
    assert any("VERDE" in f for f in facts)
    assert not any("proyecto" in f for f in facts)
    assert not any("dispositivos" in f for f in facts)


def test_build_facts_clean_project():
    facts = wm.build_facts(_state(project={"is_repo": True, "repo_name": "x",
                                           "branch": "dev", "dirty_count": 0}))
    assert any("sin cambios pendientes" in f for f in facts)


def test_build_facts_services_with_stopped():
    facts = wm.build_facts(_state(services={"running": 8, "stopped": 3}))
    assert any("8 servicios activos (3 detenidos)" in f for f in facts)


# ---------------------------------------------------------------- build_context_block
def test_build_context_block():
    block = wm.build_context_block(_state())
    assert block.startswith("ESTADO GLOBAL DEL SISTEMA")
    assert block.endswith(".")
    assert "proyecto jarvis" in block


def test_build_context_block_empty():
    empty = {"system": {}, "services": {}, "threat": {}, "project": {"is_repo": False},
             "productivity": {}, "network": {}, "watches": {}, "usage": {}}
    # 'threat' sin level cae a green -> hay un hecho; forzamos vacío real:
    empty["threat"] = {"level": ""}
    block = wm.build_context_block(empty)
    # Con threat vacío, _LEVEL_WORD usa upper("") => sigue habiendo un hecho de amenaza.
    assert isinstance(block, str)


def test_build_context_block_truly_empty(monkeypatch):
    monkeypatch.setattr(wm, "build_facts", lambda s: [])
    assert wm.build_context_block({}) == ""


# ---------------------------------------------------------------- build_situation_report
def test_situation_report_nominal():
    out = wm.build_situation_report(_state())
    assert "Todos los sistemas nominales" in out
    assert out.endswith(".")


def test_situation_report_critical():
    out = wm.build_situation_report(_state(threat={"level": "red", "reasons": ["intrusos"]}))
    assert "situación crítica" in out


def test_situation_report_no_facts(monkeypatch):
    monkeypatch.setattr(wm, "build_facts", lambda s: [])
    assert "No dispongo de telemetría" in wm.build_situation_report({})


# ---------------------------------------------------------------- snapshot (caché)
def test_snapshot_uses_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(wm, "_gather_state", lambda: calls.append(1) or {"x": 1})
    wm._snapshot_cache["state"] = None
    wm._snapshot_cache["ts"] = 0.0
    first = wm.snapshot(max_age=100)
    second = wm.snapshot(max_age=100)
    assert first is second
    assert len(calls) == 1  # la segunda vez salió de caché


def test_snapshot_refreshes_when_stale(monkeypatch):
    calls = []
    monkeypatch.setattr(wm, "_gather_state", lambda: calls.append(1) or {"n": len(calls)})
    wm._snapshot_cache["state"] = None
    wm._snapshot_cache["ts"] = 0.0
    wm.snapshot(max_age=0)  # siempre obsoleto
    wm.snapshot(max_age=0)
    assert len(calls) == 2


# ---------------------------------------------------------------- get_* (integración)
def test_get_context_block_safe(monkeypatch):
    monkeypatch.setattr(wm, "snapshot", lambda: _state())
    assert "ESTADO GLOBAL" in wm.get_context_block()


def test_get_situation_report_safe(monkeypatch):
    monkeypatch.setattr(wm, "snapshot", lambda: _state())
    assert "Informe de situación" in wm.get_situation_report()
