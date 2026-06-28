"""Tests de core/wellbeing.py — Lectura de estado/ánimo del usuario."""
import core.wellbeing as wb


def _signals(hour=14, recent_errors=0, work_minutes=0, tests_failing=False):
    return {"hour": hour, "recent_errors": recent_errors,
            "work_minutes": work_minutes, "tests_failing": tests_failing}


# ---------------------------------------------------------------- compute_stress
def test_stress_calm_baseline():
    assert wb.compute_stress(_signals()) == 0


def test_stress_late_hour():
    assert wb.compute_stress(_signals(hour=2)) == 25
    assert wb.compute_stress(_signals(hour=23)) == 25


def test_stress_errors_capped():
    assert wb.compute_stress(_signals(recent_errors=2)) == 24
    assert wb.compute_stress(_signals(recent_errors=10)) == 40  # tope


def test_stress_work_tiers():
    assert wb.compute_stress(_signals(work_minutes=100)) == 15
    assert wb.compute_stress(_signals(work_minutes=200)) == 30


def test_stress_tests_failing():
    assert wb.compute_stress(_signals(tests_failing=True)) == 15


def test_stress_combined_and_clamped():
    s = _signals(hour=3, recent_errors=10, work_minutes=200, tests_failing=True)
    # 25 + 40 + 30 + 15 = 110 -> clamp 100.
    assert wb.compute_stress(s) == 100


def test_stress_handles_none_hour():
    assert wb.compute_stress({"hour": None, "recent_errors": 0}) == 0


# ---------------------------------------------------------------- stress_level
def test_stress_level_bands():
    assert wb.stress_level(0) == "sereno"
    assert wb.stress_level(24) == "sereno"
    assert wb.stress_level(25) == "concentrado"
    assert wb.stress_level(49) == "concentrado"
    assert wb.stress_level(50) == "tenso"
    assert wb.stress_level(74) == "tenso"
    assert wb.stress_level(75) == "agotado"
    assert wb.stress_level(100) == "agotado"


# ---------------------------------------------------------------- advice / intervene
def test_advice_for():
    assert "sereno" in wb.advice_for("sereno")
    assert "pausa" in wb.advice_for("tenso")
    assert "descansar" in wb.advice_for("agotado")
    assert wb.advice_for("desconocido") == ""


def test_should_intervene():
    assert wb.should_intervene("tenso") is True
    assert wb.should_intervene("agotado") is True
    assert wb.should_intervene("sereno") is False
    assert wb.should_intervene("concentrado") is False


# ---------------------------------------------------------------- build_status_report
def test_report_calm_no_factors():
    out = wb.build_status_report(_signals())
    assert "sereno" in out
    assert "Pesa" not in out  # sin factores cuando estás bien


def test_report_strained_lists_factors():
    s = _signals(hour=2, recent_errors=3, work_minutes=120, tests_failing=True)
    out = wb.build_status_report(s)
    assert "Pesa" in out
    assert "la hora" in out
    assert "los errores recientes" in out
    assert "el rato sin pausa" in out
    assert "los tests en rojo" in out


def test_report_handles_none_hour_safely():
    # hour=None no debe romper ni añadir el factor "la hora".
    out = wb.build_status_report({"hour": None, "recent_errors": 4, "work_minutes": 200,
                                  "tests_failing": True})
    assert "la hora" not in out
    assert isinstance(out, str)


def test_report_concentrated_no_factor_list():
    # Nivel 'concentrado' no lista factores (sólo tenso/agotado).
    s = _signals(work_minutes=100)  # score 15 -> sereno; subimos un poco
    s = _signals(recent_errors=2, work_minutes=100)  # 24+15=39 -> concentrado
    out = wb.build_status_report(s)
    assert "concentrado" in out
    assert "Pesa" not in out


# ---------------------------------------------------------------- run_once (proactivo)
def test_run_once_silent_when_calm(monkeypatch):
    monkeypatch.setattr(wb, "_gather_signals", lambda: _signals())
    delivered = []
    monkeypatch.setattr(wb, "_deliver", lambda m: delivered.append(m))
    wb._last_advice = 0
    wb.run_once()
    assert delivered == []


def test_run_once_intervenes_when_strained(monkeypatch):
    monkeypatch.setattr(wb, "_gather_signals",
                        lambda: _signals(hour=2, recent_errors=4, work_minutes=200))
    delivered = []
    monkeypatch.setattr(wb, "_deliver", lambda m: delivered.append(m))
    wb._last_advice = 0
    monkeypatch.setenv("JARVIS_WELLBEING_COOLDOWN", "3600")
    wb.run_once()
    assert len(delivered) == 1


def test_run_once_respects_cooldown(monkeypatch):
    monkeypatch.setattr(wb, "_gather_signals",
                        lambda: _signals(hour=2, recent_errors=4, work_minutes=200))
    delivered = []
    monkeypatch.setattr(wb, "_deliver", lambda m: delivered.append(m))
    import time
    wb._last_advice = time.time()  # acabamos de avisar
    monkeypatch.setenv("JARVIS_WELLBEING_COOLDOWN", "3600")
    wb.run_once()
    assert delivered == []  # dentro del enfriamiento


# ---------------------------------------------------------------- daemon
def test_start_daemon_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_WELLBEING_ENABLED", "false")
    wb.WELLBEING_THREAD = None
    wb.start_wellbeing_daemon()
    assert wb.WELLBEING_THREAD is None


def test_stop_daemon_sets_event():
    wb.stop_event.clear()
    wb.stop_wellbeing_daemon()
    assert wb.stop_event.is_set()
    wb.stop_event.clear()
