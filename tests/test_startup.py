"""Tests de core/startup.py — Saludo Contextual de arranque."""
import core.startup as st


# ---------------------------------------------------------------- build_contextual_greeting
def test_greeting_minimal():
    out = st.build_contextual_greeting("Buenos días")
    assert out == "Buenos días, señor. ¿En qué puedo servirle?"


def test_greeting_with_weather():
    out = st.build_contextual_greeting("Buenas tardes", weather="Despejado, 18°C.")
    assert "Despejado, 18°C." in out
    assert out.startswith("Buenas tardes, señor.")


def test_greeting_one_reminder():
    out = st.build_contextual_greeting("Buenos días", reminders=1)
    assert "Tiene un recordatorio pendiente para hoy." in out


def test_greeting_several_reminders():
    out = st.build_contextual_greeting("Buenos días", reminders=3)
    assert "Tiene 3 recordatorios pendientes para hoy." in out


def test_greeting_no_reminders():
    out = st.build_contextual_greeting("Buenos días", reminders=0)
    assert "recordatorio" not in out


def test_greeting_with_alerts():
    out = st.build_contextual_greeting("Buenas noches", alerts=["Detecto 2 dispositivos desconocidos."])
    assert "Detecto 2 dispositivos desconocidos." in out


def test_greeting_skips_empty_alerts():
    out = st.build_contextual_greeting("Buenos días", alerts=["", None, "Aviso real."])
    assert "Aviso real." in out
    # No deben colarse cadenas vacías como frases sueltas.
    assert "señor.  ¿" not in out


def test_greeting_full_order():
    out = st.build_contextual_greeting("Buenas tardes", weather="Lluvia, 12°C.",
                                       reminders=2, alerts=["Red con intrusos."])
    # Orden: saludo -> clima -> recordatorios -> alertas -> cierre.
    assert out.index("Lluvia") < out.index("recordatorios") < out.index("Red con intrusos") < out.index("¿En qué")


def test_greeting_always_ends_with_offer():
    assert st.build_contextual_greeting("Buenos días").endswith("¿En qué puedo servirle?")


# ---------------------------------------------------------------- dispatcher
def test_generate_uses_contextual_by_default(monkeypatch):
    monkeypatch.delenv("JARVIS_STARTUP_VERBOSE", raising=False)
    monkeypatch.setattr(st, "_get_greeting_by_time", lambda: "Buenos días")
    monkeypatch.setattr(st, "_get_weather", lambda: "Soleado, 20°C.")
    monkeypatch.setattr(st, "_get_pending_reminders", lambda: 1)
    monkeypatch.setattr(st, "_startup_alerts", lambda: [])
    out = st.generate_startup_greeting()
    assert "Soleado, 20°C." in out
    assert "recordatorio pendiente" in out
    # El contextual NO mete el volcado técnico.
    assert "megabytes" not in out
    assert "servicios activos" not in out


def test_generate_verbose_when_enabled(monkeypatch):
    monkeypatch.setenv("JARVIS_STARTUP_VERBOSE", "true")
    monkeypatch.setattr(st, "_get_greeting_by_time", lambda: "Buenas noches")
    # El verboso incluye la frase de sistemas en línea.
    out = st.generate_startup_greeting()
    assert "en línea y operativos" in out


def test_generate_contextual_survives_failures(monkeypatch):
    monkeypatch.delenv("JARVIS_STARTUP_VERBOSE", raising=False)
    monkeypatch.setattr(st, "_get_greeting_by_time", lambda: "Buenas tardes")
    monkeypatch.setattr(st, "_get_weather", lambda: None)  # sin clima configurado
    def boom():
        raise RuntimeError("x")
    monkeypatch.setattr(st, "_get_pending_reminders", boom)
    monkeypatch.setattr(st, "_startup_alerts", lambda: [])
    out = st.generate_startup_greeting()
    assert out.startswith("Buenas tardes, señor.")
    assert out.endswith("¿En qué puedo servirle?")
