"""Tests de core/repair_guide.py — Diagnóstico con Guía de Reparación."""
import core.repair_guide as rg


def _state(ram=40, disk=50, stopped=0, threat="green", tests_failing=False, dirty=0):
    return {
        "system": {"ram": ram, "disk": disk},
        "services": {"stopped": stopped},
        "threat": {"level": threat},
        "tests_failing": tests_failing,
        "project": {"dirty_count": dirty},
    }


# ---------------------------------------------------------------- detect_problems
def test_detect_none_when_healthy():
    assert rg.detect_problems(_state()) == []


def test_detect_ram_high():
    assert "ram_high" in rg.detect_problems(_state(ram=90))


def test_detect_disk_low():
    assert "disk_low" in rg.detect_problems(_state(disk=95))


def test_detect_service_down():
    assert "service_down" in rg.detect_problems(_state(stopped=2))


def test_detect_threat_high():
    assert "threat_high" in rg.detect_problems(_state(threat="red"))
    assert "threat_high" in rg.detect_problems(_state(threat="violet"))


def test_detect_tests_failing():
    assert "tests_failing" in rg.detect_problems(_state(tests_failing=True))


def test_detect_dirty_repo():
    assert "dirty_repo" in rg.detect_problems(_state(dirty=30))
    assert "dirty_repo" not in rg.detect_problems(_state(dirty=10))


def test_detect_sorted_by_severity():
    # threat (3) debe ir antes que dirty (1).
    problems = rg.detect_problems(_state(threat="red", dirty=30))
    assert problems.index("threat_high") < problems.index("dirty_repo")


def test_detect_handles_bad_values():
    state = {"system": {"ram": None, "disk": "x"}}
    assert rg.detect_problems(state) == []


# ---------------------------------------------------------------- repair_guide / format
def test_repair_guide_known():
    g = rg.repair_guide("ram_high")
    assert g["title"] == "RAM al límite"
    assert len(g["steps"]) >= 2


def test_repair_guide_unknown():
    assert rg.repair_guide("inexistente") == {}


def test_format_guide():
    out = rg.format_guide("disk_low")
    assert "Espacio en disco bajo, señor" in out
    assert "1)" in out and "2)" in out


def test_format_guide_unknown_empty():
    assert rg.format_guide("nope") == ""


# ---------------------------------------------------------------- build_diagnosis
def test_build_diagnosis_healthy():
    assert "No detecto nada que reparar" in rg.build_diagnosis(_state())


def test_build_diagnosis_top_problems():
    state = _state(ram=92, threat="red", dirty=30)
    out = rg.build_diagnosis(state, top=2)
    # Los 2 más graves: threat (3) y ram (2). dirty (1) queda fuera.
    assert "Nivel de amenaza elevado" in out
    assert "RAM al límite" in out
    assert "cambios sin confirmar" not in out


def test_build_diagnosis_single():
    out = rg.build_diagnosis(_state(disk=95))
    assert "Espacio en disco bajo" in out


# ---------------------------------------------------------------- get_diagnosis (integración)
def test_get_diagnosis_safe(monkeypatch):
    monkeypatch.setattr(rg, "_gather_state", lambda: _state(ram=95))
    assert "RAM al límite" in rg.get_diagnosis()
