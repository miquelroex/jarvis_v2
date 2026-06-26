"""Tests de core/reticle_scan.py — "Escanea esto" (Análisis con Retícula)."""
import json

import core.reticle_scan as rs


# ---------------------------------------------------------------- parse_detections
def test_parse_plain_json_object():
    raw = json.dumps({"detections": [
        {"label": "Traceback", "kind": "error", "box": [10, 20, 100, 200]},
    ]})
    out = rs.parse_detections(raw)
    assert len(out) == 1
    assert out[0]["label"] == "Traceback"
    assert out[0]["kind"] == "error"
    assert out[0]["box"] == [10, 20, 100, 200]


def test_parse_strips_markdown_fences():
    raw = '```json\n{"detections": [{"label": "VSCode", "kind": "window", "box": [0,0,500,500]}]}\n```'
    out = rs.parse_detections(raw)
    assert out and out[0]["label"] == "VSCode"


def test_parse_accepts_bare_list():
    raw = json.dumps([{"label": "x", "kind": "text", "box": [1, 1, 50, 50]}])
    assert len(rs.parse_detections(raw)) == 1


def test_parse_extracts_embedded_json():
    raw = 'Aquí tienes: {"detections": [{"label": "y", "kind": "code", "box": [2,2,40,40]}]} fin'
    out = rs.parse_detections(raw)
    assert out and out[0]["kind"] == "code"


def test_parse_empty_and_garbage():
    assert rs.parse_detections("") == []
    assert rs.parse_detections("no soy json") == []
    assert rs.parse_detections(None) == []


def test_parse_skips_bad_boxes():
    raw = json.dumps({"detections": [
        {"label": "ok", "kind": "text", "box": [0, 0, 10, 10]},
        {"label": "sin box", "kind": "text"},
        {"label": "box corta", "kind": "text", "box": [1, 2]},
        {"label": "invertida", "kind": "text", "box": [100, 100, 10, 10]},
        {"label": "no num", "kind": "text", "box": ["a", "b", "c", "d"]},
    ]})
    out = rs.parse_detections(raw)
    assert len(out) == 1
    assert out[0]["label"] == "ok"


def test_parse_skips_partially_invalid_box():
    # Sólo la dimensión vertical es inválida (ymax<=ymin); la horizontal es válida.
    raw = json.dumps([{"label": "x", "kind": "text", "box": [100, 0, 10, 50]}])
    assert rs.parse_detections(raw) == []


def test_parse_unknown_kind_becomes_object():
    raw = json.dumps([{"label": "z", "kind": "alienigena", "box": [0, 0, 5, 5]}])
    assert rs.parse_detections(raw)[0]["kind"] == "object"


def test_parse_clamps_coordinates():
    raw = json.dumps([{"label": "z", "kind": "text", "box": [-50, -10, 5000, 1200]}])
    out = rs.parse_detections(raw)
    assert out[0]["box"] == [0, 0, 1000, 1000]


def test_parse_default_label():
    raw = json.dumps([{"kind": "text", "box": [0, 0, 5, 5]}])
    assert rs.parse_detections(raw)[0]["label"] == "elemento"


# ---------------------------------------------------------------- to_reticles
def test_to_reticles_scales_to_pixels():
    dets = [{"label": "a", "kind": "text", "box": [0, 0, 500, 500]}]
    out = rs.to_reticles(dets, width=1000, height=2000)
    assert out[0]["x"] == 0 and out[0]["y"] == 0
    assert out[0]["w"] == 500   # 500/1000 * 1000
    assert out[0]["h"] == 1000  # 500/1000 * 2000


def test_to_reticles_orders_errors_first():
    dets = [
        {"label": "win", "kind": "window", "box": [0, 0, 100, 100]},
        {"label": "err", "kind": "error", "box": [0, 0, 100, 100]},
    ]
    out = rs.to_reticles(dets, 1000, 1000)
    assert out[0]["label"] == "err"


def test_to_reticles_respects_max_n():
    dets = [{"label": str(i), "kind": "object", "box": [0, 0, 10, 10]} for i in range(20)]
    assert len(rs.to_reticles(dets, 1000, 1000, max_n=3)) == 3


def test_to_reticles_invalid_dimensions():
    dets = [{"label": "a", "kind": "text", "box": [0, 0, 5, 5]}]
    assert rs.to_reticles(dets, 0, 0) == []


def test_to_reticles_drops_zero_area_after_scaling():
    # Box minúscula que al escalar a una pantalla pequeña da 0 px de ancho.
    dets = [{"label": "a", "kind": "text", "box": [0, 0, 1000, 1]}]
    out = rs.to_reticles(dets, width=10, height=1000)
    assert out == []  # w = 1/1000*10 = 0


def test_to_reticles_drops_zero_height_only():
    # Ancho válido pero alto que escala a 0 px (sólo una condición del or).
    dets = [{"label": "a", "kind": "text", "box": [0, 0, 1, 1000]}]
    out = rs.to_reticles(dets, width=1000, height=10)
    assert out == []  # h = 1/1000*10 = 0, w = 1000


# ---------------------------------------------------------------- build_narration
def test_build_narration_empty():
    assert "No he detectado nada" in rs.build_narration([])


def test_build_narration_error_prefix():
    dets = [
        {"label": "ZeroDivisionError", "kind": "error", "box": [0, 0, 10, 10]},
        {"label": "Chrome", "kind": "window", "box": [0, 0, 10, 10]},
    ]
    out = rs.build_narration(dets)
    assert out.startswith("Identificado: ZeroDivisionError. Analizando…")
    assert "2 elementos" in out


def test_build_narration_singular():
    dets = [{"label": "Notepad", "kind": "window", "box": [0, 0, 10, 10]}]
    out = rs.build_narration(dets)
    assert "1 elemento:" in out
    assert "Notepad" in out
    assert not out.startswith("Identificado:")


# ---------------------------------------------------------------- scan_screen (orquestación)
def test_scan_screen_capture_fails(monkeypatch):
    monkeypatch.setattr(rs, "_capture_screen", lambda path=rs.SCREENSHOT_PATH: (False, 0, 0))
    assert "No he podido capturar" in rs.scan_screen()


def test_scan_screen_no_api_key(monkeypatch):
    monkeypatch.setattr(rs, "_capture_screen", lambda path=rs.SCREENSHOT_PATH: (True, 1920, 1080))
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert "GOOGLE_API_KEY" in rs.scan_screen()


def test_scan_screen_full_flow(monkeypatch):
    monkeypatch.setattr(rs, "_capture_screen", lambda path=rs.SCREENSHOT_PATH: (True, 1000, 1000))
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")
    monkeypatch.setattr(rs, "_detect", lambda path: json.dumps(
        {"detections": [{"label": "TypeError", "kind": "error", "box": [0, 0, 100, 100]}]}))
    launched = []
    monkeypatch.setattr(rs, "_launch_overlay", lambda reticles: launched.append(reticles))
    out = rs.scan_screen()
    assert "Identificado: TypeError" in out
    assert launched and launched[0][0]["label"] == "TypeError"
