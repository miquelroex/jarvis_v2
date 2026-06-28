"""Tests de core/desktop.py — App de Escritorio (lógica de modo/config pura)."""
import core.desktop as desk


# ---------------------------------------------------------------- desktop_enabled
def test_desktop_enabled_env(monkeypatch):
    monkeypatch.setattr(desk.sys, "argv", ["main.py"])
    monkeypatch.setenv("JARVIS_DESKTOP", "true")
    assert desk.desktop_enabled() is True


def test_desktop_enabled_argv(monkeypatch):
    monkeypatch.delenv("JARVIS_DESKTOP", raising=False)
    monkeypatch.setattr(desk.sys, "argv", ["main.py", "--desktop"])
    assert desk.desktop_enabled() is True


def test_desktop_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JARVIS_DESKTOP", raising=False)
    monkeypatch.setattr(desk.sys, "argv", ["main.py"])
    assert desk.desktop_enabled() is False


# ---------------------------------------------------------------- window_config
def test_window_config_defaults(monkeypatch):
    for v in ["JARVIS_DESKTOP_TITLE", "JARVIS_DESKTOP_WIDTH", "JARVIS_DESKTOP_HEIGHT",
              "JARVIS_DESKTOP_FULLSCREEN"]:
        monkeypatch.delenv(v, raising=False)
    cfg = desk.window_config()
    assert cfg["title"] == "J.A.R.V.I.S."
    assert cfg["width"] == 1280
    assert cfg["height"] == 800
    assert cfg["fullscreen"] is False


def test_window_config_overrides(monkeypatch):
    monkeypatch.setenv("JARVIS_DESKTOP_TITLE", "Mi Jarvis")
    monkeypatch.setenv("JARVIS_DESKTOP_WIDTH", "1920")
    monkeypatch.setenv("JARVIS_DESKTOP_HEIGHT", "1080")
    monkeypatch.setenv("JARVIS_DESKTOP_FULLSCREEN", "true")
    cfg = desk.window_config()
    assert cfg == {"title": "Mi Jarvis", "width": 1920, "height": 1080, "fullscreen": True}


def test_window_config_bad_int_falls_back(monkeypatch):
    monkeypatch.setenv("JARVIS_DESKTOP_WIDTH", "no-numero")
    assert desk.window_config()["width"] == 1280  # cae al default


# ---------------------------------------------------------------- use_desktop
def test_use_desktop_disabled(monkeypatch):
    monkeypatch.setattr(desk, "desktop_enabled", lambda: False)
    monkeypatch.setattr(desk, "is_available", lambda: True)
    assert desk.use_desktop() is False


def test_use_desktop_enabled_but_unavailable(monkeypatch):
    # Pedido pero sin pywebview -> False (fallback al navegador).
    monkeypatch.setattr(desk, "desktop_enabled", lambda: True)
    monkeypatch.setattr(desk, "is_available", lambda: False)
    assert desk.use_desktop() is False


def test_use_desktop_enabled_and_available(monkeypatch):
    monkeypatch.setattr(desk, "desktop_enabled", lambda: True)
    monkeypatch.setattr(desk, "is_available", lambda: True)
    assert desk.use_desktop() is True


def test_is_available_returns_bool():
    assert isinstance(desk.is_available(), bool)
