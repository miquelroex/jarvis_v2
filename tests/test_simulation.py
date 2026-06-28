"""Tests de core/simulation.py — Simulaciones y Cálculos al Vuelo."""
import core.simulation as sim


# ---------------------------------------------------------------- success_probability
def test_probability_all_ok():
    factors = [{"name": "a", "ok": True, "weight": 2}, {"name": "b", "ok": True, "weight": 3}]
    assert sim.success_probability(factors) == 100


def test_probability_none_ok():
    factors = [{"name": "a", "ok": False, "weight": 2}, {"name": "b", "ok": False, "weight": 3}]
    assert sim.success_probability(factors) == 0


def test_probability_weighted():
    # peso satisfecho 4 de 5 -> 80%.
    factors = [{"name": "a", "ok": True, "weight": 4}, {"name": "b", "ok": False, "weight": 1}]
    assert sim.success_probability(factors) == 80


def test_probability_empty_is_uncertain():
    assert sim.success_probability([]) == 50
    assert sim.success_probability(None) == 50


def test_probability_zero_weight():
    assert sim.success_probability([{"name": "a", "ok": True, "weight": 0}]) == 50


def test_probability_default_weight():
    # sin weight -> 1 cada uno; 1 de 2 ok -> 50.
    assert sim.success_probability([{"name": "a", "ok": True}, {"name": "b", "ok": False}]) == 50


# ---------------------------------------------------------------- verdict
def test_verdict_bands():
    assert sim.verdict(90) == "muy favorable"
    assert sim.verdict(70) == "favorable"
    assert sim.verdict(50) == "incierto"
    assert sim.verdict(30) == "desfavorable"
    assert sim.verdict(10) == "muy desfavorable"


# ---------------------------------------------------------------- format_simulation
def test_format_includes_prob_and_verdict():
    factors = [{"name": "tests en verde", "ok": True, "weight": 4}]
    out = sim.format_simulation("el despliegue", 100, factors)
    assert "para el despliegue" in out
    assert "91%" not in out and "100%" in out
    assert "muy favorable" in out


def test_format_lists_failed_factors():
    factors = [{"name": "tests en verde", "ok": False, "weight": 4},
               {"name": "memoria holgada", "ok": True, "weight": 2}]
    out = sim.format_simulation("", 33, factors)
    assert "En contra: tests en verde" in out
    assert "memoria holgada" not in out.split("En contra:")[1]  # las ok no salen


def test_format_no_action():
    out = sim.format_simulation("", 80, [{"name": "x", "ok": True, "weight": 1}])
    assert "Simulación completada, señor" in out
    assert "para " not in out.split(",")[0]


# ---------------------------------------------------------------- simulate (integración)
def test_simulate_full(monkeypatch):
    monkeypatch.setattr(sim, "_gather_factors",
                        lambda: [{"name": "tests en verde", "ok": True, "weight": 4},
                                 {"name": "memoria holgada", "ok": True, "weight": 2}])
    out = sim.simulate("el despliegue")
    assert "100%" in out
    assert "para el despliegue" in out


def test_gather_factors_all_good(monkeypatch):
    import core.world_model as wm
    monkeypatch.setattr(wm, "snapshot", lambda: {"system": {"ram": 50},
                                                 "threat": {"level": "green"},
                                                 "project": {"dirty_count": 0}})
    monkeypatch.setattr(sim, "_check_smoke_tests", lambda: True)
    names = {f["name"]: f["ok"] for f in sim._gather_factors()}
    assert names["memoria holgada"] is True       # ram 50 < 85
    assert names["amenaza controlada"] is True     # green
    assert names["árbol git limpio"] is True       # dirty 0
    assert names["tests en verde"] is True


def test_gather_factors_all_bad(monkeypatch):
    import core.world_model as wm
    monkeypatch.setattr(wm, "snapshot", lambda: {"system": {"ram": 95},
                                                 "threat": {"level": "red"},
                                                 "project": {"dirty_count": 5}})
    monkeypatch.setattr(sim, "_check_smoke_tests", lambda: False)
    names = {f["name"]: f["ok"] for f in sim._gather_factors()}
    assert names["memoria holgada"] is False       # 95 >= 85
    assert names["amenaza controlada"] is False     # red
    assert names["árbol git limpio"] is False       # dirty 5
    assert names["tests en verde"] is False


def test_simulate_with_failures(monkeypatch):
    monkeypatch.setattr(sim, "_gather_factors",
                        lambda: [{"name": "tests en verde", "ok": False, "weight": 4},
                                 {"name": "amenaza controlada", "ok": True, "weight": 2}])
    out = sim.simulate("")
    assert "33%" in out  # 2 de 6
    assert "En contra: tests en verde" in out
