"""Tests de core/access_control.py — candado facial para acciones sensibles."""
import core.access_control as ac


# ---------------------------------------------------------------- is_sensitive
def test_is_sensitive_detects_destructive():
    assert ac.is_sensitive("borra todos los logs") is True
    assert ac.is_sensitive("desactiva el centinela") is True
    assert ac.is_sensitive("ejecuta el protocolo de limpieza") is True
    assert ac.is_sensitive("protocolo mark dos main.py: optimiza") is True


def test_is_sensitive_ignores_normal():
    assert ac.is_sensitive("qué hora es") is False
    assert ac.is_sensitive("abre el navegador") is False


def test_is_sensitive_accent_insensitive():
    assert ac.is_sensitive("PÚRGA la caché") is True  # 'purga'


def test_is_sensitive_custom_keywords():
    assert ac.is_sensitive("haz algo raro", keywords=["raro"]) is True
    assert ac.is_sensitive("haz algo raro", keywords=["otro"]) is False


# ---------------------------------------------------------------- decide_access
def test_decide_allow_authorized():
    decision, _ = ac.decide_access("señor", available=True, authorized=["señor"])
    assert decision == "allow"


def test_decide_deny_unknown():
    decision, reason = ac.decide_access("desconocido", available=True, authorized=["señor"])
    assert decision == "deny"
    assert reason == "desconocido"


def test_decide_deny_unauthorized_known():
    # Reconocido pero NO en la lista de autorizados.
    decision, _ = ac.decide_access("Ana", available=True, authorized=["señor"])
    assert decision == "deny"


def test_decide_case_insensitive_authorized():
    decision, _ = ac.decide_access("SEÑOR", available=True, authorized=["señor"])
    assert decision == "allow"


def test_decide_empty_identity_reason():
    # Identidad vacía -> deny con motivo 'desconocido' (no cadena vacía).
    decision, reason = ac.decide_access("", available=True, authorized=["señor"])
    assert decision == "deny"
    assert reason == "desconocido"


def test_decide_unavailable_fail_open():
    decision, _ = ac.decide_access("desconocido", available=False, authorized=["señor"], fail_open=True)
    assert decision == "allow"


def test_decide_unavailable_fail_closed():
    decision, _ = ac.decide_access("desconocido", available=False, authorized=["señor"], fail_open=False)
    assert decision == "deny"


# ---------------------------------------------------------------- access_phrase
def test_access_phrase_allow_named():
    assert "Identidad confirmada, señor" in ac.access_phrase("allow", "señor")


def test_access_phrase_allow_generic():
    assert ac.access_phrase("allow", "sin verificación facial") == "Acceso concedido, señor."


def test_access_phrase_deny():
    assert "Acceso denegado" in ac.access_phrase("deny", "desconocido")


# ---------------------------------------------------------------- authorized_names
def test_authorized_names_default(monkeypatch):
    monkeypatch.delenv("JARVIS_ACCESS_AUTHORIZED", raising=False)
    assert ac.authorized_names() == ["señor"]


def test_authorized_names_custom(monkeypatch):
    monkeypatch.setenv("JARVIS_ACCESS_AUTHORIZED", "señor, Ana , Tony")
    assert ac.authorized_names() == ["señor", "Ana", "Tony"]


# ---------------------------------------------------------------- maybe_block
def test_maybe_block_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_ACCESS_CONTROL_ENABLED", "false")
    assert ac.maybe_block("borra todo") is None


def test_maybe_block_not_sensitive(monkeypatch):
    monkeypatch.setenv("JARVIS_ACCESS_CONTROL_ENABLED", "true")
    assert ac.maybe_block("qué hora es") is None


def test_maybe_block_allows_authorized(monkeypatch):
    monkeypatch.setenv("JARVIS_ACCESS_CONTROL_ENABLED", "true")
    monkeypatch.setattr(ac, "_verify_identity", lambda: ("señor", True))
    assert ac.maybe_block("borra los logs") is None  # autorizado -> pasa


def test_maybe_block_denies_unknown(monkeypatch):
    monkeypatch.setenv("JARVIS_ACCESS_CONTROL_ENABLED", "true")
    monkeypatch.setattr(ac, "_verify_identity", lambda: ("desconocido", True))
    out = ac.maybe_block("borra los logs")
    assert out is not None
    assert "Acceso denegado" in out


def test_maybe_block_unavailable_fail_open(monkeypatch):
    monkeypatch.setenv("JARVIS_ACCESS_CONTROL_ENABLED", "true")
    monkeypatch.setenv("JARVIS_ACCESS_FAIL_OPEN", "true")
    monkeypatch.setattr(ac, "_verify_identity", lambda: ("desconocido", False))
    assert ac.maybe_block("borra los logs") is None  # sin cámara -> deja pasar


def test_maybe_block_unavailable_fail_closed(monkeypatch):
    monkeypatch.setenv("JARVIS_ACCESS_CONTROL_ENABLED", "true")
    monkeypatch.setenv("JARVIS_ACCESS_FAIL_OPEN", "false")
    monkeypatch.setattr(ac, "_verify_identity", lambda: ("desconocido", False))
    assert ac.maybe_block("borra los logs") is not None  # bloquea
