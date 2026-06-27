"""Tests de core/barge_in.py — lógica pura de interrupción por voz (full-duplex).

(El otro test_barge_in.py prueba la integración de audio con stop_speak; éste
cubre la máquina de estados pura, sin tocar el micrófono ni la reproducción.)
"""
import math

import core.barge_in as bi


# ---------------------------------------------------------------- rms_int16
def test_rms_of_silence():
    assert bi.rms_int16([0, 0, 0, 0]) == 0.0


def test_rms_of_constant():
    assert bi.rms_int16([100, 100, 100]) == 100.0


def test_rms_of_mixed():
    assert math.isclose(bi.rms_int16([3, -4]), math.sqrt((9 + 16) / 2))


def test_rms_empty():
    assert bi.rms_int16([]) == 0.0
    assert bi.rms_int16(None) == 0.0


# ---------------------------------------------------------------- compute_threshold
def test_compute_threshold_min_wins():
    # max(baselines)=200, *3 = 600, pero min=700 manda.
    assert bi.compute_threshold([100, 200, 150], multiplier=3.0, min_threshold=700.0) == 700.0


def test_compute_threshold_above_min():
    assert bi.compute_threshold([500], multiplier=3.0, min_threshold=700.0) == 1500.0


def test_compute_threshold_no_baselines():
    assert bi.compute_threshold([], multiplier=3.0, min_threshold=700.0) == 700.0


# ---------------------------------------------------------------- BargeInDetector
def test_detector_finalize_sets_threshold():
    d = bi.BargeInDetector(multiplier=2.0, min_threshold=100.0)
    d.calibrate(50)
    d.calibrate(80)
    assert d.finalize_calibration() == 160.0  # max(80)*2


def test_detector_requires_consecutive_frames():
    d = bi.BargeInDetector(multiplier=1.0, min_threshold=100.0, required_frames=3)
    d.finalize_calibration()  # threshold = 100
    assert d.feed(200) is False
    assert d.feed(200) is False
    assert d.feed(200) is True


def test_detector_resets_on_quiet_frame():
    d = bi.BargeInDetector(multiplier=1.0, min_threshold=100.0, required_frames=3)
    d.finalize_calibration()
    d.feed(200)
    d.feed(200)
    assert d.feed(50) is False    # silencio: reinicia el contador
    assert d.feed(200) is False
    assert d.feed(200) is False
    assert d.feed(200) is True


def test_detector_below_threshold_never_fires():
    d = bi.BargeInDetector(multiplier=1.0, min_threshold=500.0, required_frames=2)
    d.finalize_calibration()
    for _ in range(10):
        assert d.feed(400) is False


def test_detector_auto_finalizes_on_first_feed():
    d = bi.BargeInDetector(multiplier=1.0, min_threshold=100.0, required_frames=1)
    assert d.threshold is None
    assert d.feed(200) is True
    assert d.threshold == 100.0


def test_detector_required_frames_min_one():
    d = bi.BargeInDetector(required_frames=0)
    assert d.required_frames == 1


def test_detector_reset_keeps_threshold():
    d = bi.BargeInDetector(multiplier=1.0, min_threshold=100.0, required_frames=2)
    d.finalize_calibration()
    d.feed(200)
    d.reset()
    assert d.consecutive == 0
    assert d.threshold == 100.0
    assert d.feed(200) is False
    assert d.feed(200) is True


def test_detector_exact_threshold_does_not_fire():
    # rms > threshold es estricto: igualar el umbral NO dispara.
    d = bi.BargeInDetector(multiplier=1.0, min_threshold=100.0, required_frames=1)
    d.finalize_calibration()
    assert d.feed(100) is False
    assert d.feed(101) is True


# ---------------------------------------------------------------- señal de barge-in
def test_is_recent():
    assert bi.is_recent(ts=100, now=102, window=4) is True
    assert bi.is_recent(ts=100, now=105, window=4) is False  # fuera de ventana
    assert bi.is_recent(ts=0, now=1, window=4) is False      # sin señal


def test_signal_and_consume_barge_in():
    bi.signal_barge_in(now=1000)
    assert bi.consume_barge_in(now=1001, window=4) is True   # reciente -> True
    assert bi.consume_barge_in(now=1001, window=4) is False  # de un solo uso


def test_consume_barge_in_stale():
    bi.signal_barge_in(now=1000)
    assert bi.consume_barge_in(now=1010, window=4) is False  # demasiado viejo


def test_capture_mode_barge_in(monkeypatch):
    monkeypatch.setenv("JARVIS_BARGE_CAPTURE_PAUSE", "0.5")
    m = bi.capture_mode(True)
    assert m["settle"] is False
    assert m["pause_threshold"] == 0.5


def test_capture_mode_normal(monkeypatch):
    monkeypatch.setenv("JARVIS_ASR_PAUSE_THRESHOLD", "0.8")
    m = bi.capture_mode(False)
    assert m["settle"] is True
    assert m["pause_threshold"] == 0.8
