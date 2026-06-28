"""Tests de core/presence.py — Detección de Presencia por Webcam."""
import core.presence as pr


# ---------------------------------------------------------------- parse_person_count
def test_parse_plain_json():
    assert pr.parse_person_count('{"people": 2}') == 2


def test_parse_strips_fences():
    assert pr.parse_person_count('```json\n{"people": 0}\n```') == 0


def test_parse_embedded_json():
    assert pr.parse_person_count('Veo esto: {"people": 3} en la imagen') == 3


def test_parse_bare_number_fallback():
    assert pr.parse_person_count("hay 1 persona") == 1


def test_parse_clamps_negative_to_zero():
    assert pr.parse_person_count('{"people": -5}') == 0


def test_parse_unknown():
    assert pr.parse_person_count("") == -1
    assert pr.parse_person_count("no lo sé") == -1
    assert pr.parse_person_count('{"people": "muchas"}') == -1


# ---------------------------------------------------------------- event_phrase
def test_event_phrase():
    assert pr.event_phrase("arrival") == "Bienvenido, señor."
    assert "alguien más" in pr.event_phrase("companion")
    assert pr.event_phrase("desconocido") == ""


# ---------------------------------------------------------------- PresenceMonitor
def test_monitor_arrival_after_confirm():
    m = pr.PresenceMonitor(confirm=2)
    assert m.observe(1) == []         # 1ª lectura (sin confirmar)
    assert m.observe(1) == ["arrival"]  # 2ª igual -> confirmado


def test_monitor_no_event_when_stable():
    m = pr.PresenceMonitor(confirm=1)
    m.observe(1)
    assert m.observe(1) == []  # mismo estado: nada


def test_monitor_departure():
    m = pr.PresenceMonitor(confirm=1)
    m.observe(1)              # arrival
    assert m.observe(0) == ["departure"]


def test_monitor_companion():
    m = pr.PresenceMonitor(confirm=1)
    m.observe(1)                       # tú
    assert m.observe(2) == ["companion"]  # entra alguien


def test_monitor_alone_again():
    m = pr.PresenceMonitor(confirm=1)
    m.observe(2)                    # dos personas (companion desde 0? -> arrival+companion)
    assert m.observe(1) == ["alone"]


def test_monitor_arrival_with_two_at_once():
    # De vacío a 2 personas: llega alguien Y hay compañía.
    m = pr.PresenceMonitor(confirm=1)
    events = m.observe(2)
    assert "arrival" in events
    assert "companion" in events


def test_monitor_debounce_resets_on_flicker():
    m = pr.PresenceMonitor(confirm=2)
    assert m.observe(1) == []   # pending=1 (n=1)
    assert m.observe(2) == []   # flicker: pending=2 (n=1), no confirma
    assert m.observe(2) == ["arrival", "companion"]  # 2 confirmado desde 0


def test_monitor_ignores_unknown_reading():
    m = pr.PresenceMonitor(confirm=1)
    m.observe(1)                 # arrival
    assert m.observe(-1) == []   # lectura fallida: no cambia nada
    assert m.count == 1


# ---------------------------------------------------------------- get_presence_status
def test_status_no_camera(monkeypatch):
    monkeypatch.setattr(pr, "_observe_once", lambda: -1)
    assert "No puedo ver la webcam" in pr.get_presence_status()


def test_status_nobody(monkeypatch):
    monkeypatch.setattr(pr, "_observe_once", lambda: 0)
    assert "No veo a nadie" in pr.get_presence_status()


def test_status_just_you(monkeypatch):
    monkeypatch.setattr(pr, "_observe_once", lambda: 1)
    assert "Le veo a usted" in pr.get_presence_status()


def test_status_several(monkeypatch):
    monkeypatch.setattr(pr, "_observe_once", lambda: 3)
    assert "3 personas" in pr.get_presence_status()


# ---------------------------------------------------------------- daemon gating
def test_start_daemon_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_PRESENCE_ENABLED", "false")
    pr.PRESENCE_THREAD = None
    pr.start_presence_daemon()
    assert pr.PRESENCE_THREAD is None


def test_stop_daemon_sets_event():
    pr.stop_event.clear()
    pr.stop_presence_daemon()
    assert pr.stop_event.is_set()
    pr.stop_event.clear()
