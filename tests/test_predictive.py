"""Tests de core/predictive.py — Mantenimiento Predictivo."""
import math

import core.predictive as pr


# ---------------------------------------------------------------- linear_slope
def test_linear_slope_positive():
    # y = 2x
    assert math.isclose(pr.linear_slope([(0, 0), (1, 2), (2, 4)]), 2.0)


def test_linear_slope_flat():
    assert pr.linear_slope([(0, 5), (1, 5), (2, 5)]) == 0.0


def test_linear_slope_insufficient():
    assert pr.linear_slope([(0, 1)]) is None
    assert pr.linear_slope([]) is None


def test_linear_slope_same_x():
    assert pr.linear_slope([(1, 0), (1, 5)]) is None


# ---------------------------------------------------------------- slope_per_day
def test_slope_per_day():
    # disco sube 5 puntos en 1 día (86400 s).
    samples = [{"ts": 0, "disk": 50}, {"ts": 86400, "disk": 55}]
    assert math.isclose(pr.slope_per_day(samples, "disk"), 5.0)


def test_slope_per_day_ignores_missing_key():
    samples = [{"ts": 0, "disk": 50}, {"ts": 86400}]  # falta disk en la 2ª
    assert pr.slope_per_day(samples, "disk") is None  # solo 1 punto válido


# ---------------------------------------------------------------- days_to_threshold
def test_days_to_threshold():
    # de 80 a 92 subiendo 4/día -> 3 días.
    assert math.isclose(pr.days_to_threshold(80, 92, 4.0), 3.0)


def test_days_to_threshold_not_rising():
    assert pr.days_to_threshold(80, 92, 0.0) is None
    assert pr.days_to_threshold(80, 92, -1.0) is None
    assert pr.days_to_threshold(80, 92, None) is None


def test_days_to_threshold_already_there():
    assert pr.days_to_threshold(95, 92, 1.0) == 0.0


# ---------------------------------------------------------------- humanize_days
def test_humanize_days():
    assert pr.humanize_days(None) == "sin horizonte previsible"
    assert pr.humanize_days(0.5) == "menos de un día"
    assert pr.humanize_days(1) == "1 día"
    assert pr.humanize_days(3) == "3 días"
    assert pr.humanize_days(20) == "unas 2 semanas"
    assert "meses" in pr.humanize_days(90)


# ---------------------------------------------------------------- predict_metric
def test_predict_metric():
    samples = [{"ts": 0, "disk": 80}, {"ts": 86400, "disk": 84}]  # +4/día
    out = pr.predict_metric(samples, "disk", current=84, threshold=92)
    assert math.isclose(out["slope"], 4.0)
    assert math.isclose(out["days"], 2.0)  # de 84 a 92 a 4/día


# ---------------------------------------------------------------- build_report
def _rising_samples(per_day, start=70, n=5):
    return [{"ts": i * 86400, "disk": start + per_day * i, "ram": 40} for i in range(n)]


def test_build_report_insufficient():
    assert "suficiente histórico" in pr.build_report([{"ts": 0, "disk": 50}], 50, 40)


def test_build_report_disk_warning():
    samples = _rising_samples(5)  # disco +5/día desde 70
    out = pr.build_report(samples, current_disk=90, current_ram=40)
    assert "el disco se llenará en" in out


def test_build_report_disk_stable():
    samples = [{"ts": i * 86400, "disk": 50, "ram": 40} for i in range(5)]
    out = pr.build_report(samples, 50, 40)
    assert "estable" in out


def test_build_report_includes_deps():
    samples = _rising_samples(0.1)
    out = pr.build_report(samples, 60, 40, dep_aging=3)
    assert "3 dependencia(s) envejeciendo" in out


# ---------------------------------------------------------------- critical_disk_warning
def test_critical_warning_fires():
    samples = _rising_samples(5)  # llega a 92 pronto
    warn = pr.critical_disk_warning(samples, current_disk=88, horizon_days=7)
    assert warn is not None
    assert "se llenará en" in warn


def test_critical_warning_silent_when_far():
    samples = _rising_samples(0.05)  # crece lentísimo
    assert pr.critical_disk_warning(samples, current_disk=60, horizon_days=7) is None


def test_critical_warning_insufficient():
    assert pr.critical_disk_warning([{"ts": 0, "disk": 50}], 50) is None


# ---------------------------------------------------------------- persistencia
def test_record_and_load(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "SAMPLES_FILE", tmp_path / "s.jsonl")
    pr.record_sample({"ts": 1, "disk": 50, "ram": 40})
    loaded = pr.load_samples()
    assert len(loaded) == 1
    assert loaded[0]["disk"] == 50


def test_load_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "SAMPLES_FILE", tmp_path / "no.jsonl")
    assert pr.load_samples() == []


# ---------------------------------------------------------------- run_once / daemon
def test_run_once_warns(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "SAMPLES_FILE", tmp_path / "s.jsonl")
    # Sembrar histórico ascendente y una lectura actual cercana al umbral.
    for s in _rising_samples(5, start=70, n=4):
        pr.record_sample(s)
    monkeypatch.setattr(pr, "_current_metrics", lambda: {"ts": 4 * 86400, "disk": 90, "ram": 40})
    notified = []
    monkeypatch.setattr(pr, "_notify", lambda m: notified.append(m))
    pr._last_warn = 0
    monkeypatch.setenv("JARVIS_PREDICTIVE_COOLDOWN", "0")
    pr.run_once()
    assert any("disco" in m for m in notified)


def test_start_daemon_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_PREDICTIVE_ENABLED", "false")
    pr.PREDICTIVE_THREAD = None
    pr.start_predictive_daemon()
    assert pr.PREDICTIVE_THREAD is None


def test_stop_daemon_sets_event():
    pr.stop_event.clear()
    pr.stop_predictive_daemon()
    assert pr.stop_event.is_set()
    pr.stop_event.clear()
