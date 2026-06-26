"""Tests de core/watchpost.py — "Jarvis, vigila esto" (Puesto de Vigilancia)."""
import core.watchpost as wp


def setup_function(_):
    with wp._lock:
        wp.WATCHES.clear()


# ---------------------------------------------------------------- parse_watch_request
def test_parse_file():
    assert wp.parse_watch_request("vigila el fichero config.py") == {"kind": "file", "target": "config.py"}


def test_parse_archivo_alias():
    assert wp.parse_watch_request("vigila el archivo datos.json") == {"kind": "file", "target": "datos.json"}


def test_parse_process():
    assert wp.parse_watch_request("vigila el proceso chrome") == {"kind": "process", "target": "chrome"}


def test_parse_port():
    assert wp.parse_watch_request("vigila el puerto 8080") == {"kind": "port", "target": "8080"}


def test_parse_port_extracts_digits():
    assert wp.parse_watch_request("vigila el puerto numero 5000 ahora") == {"kind": "port", "target": "5000"}


def test_parse_none_when_unclear():
    assert wp.parse_watch_request("vigila esto") is None
    assert wp.parse_watch_request("hola que tal") is None


def test_parse_port_without_number_is_none():
    assert wp.parse_watch_request("vigila el puerto abierto") is None


# ---------------------------------------------------------------- make_label
def test_make_label():
    assert wp.make_label("file", "x.py") == "fichero x.py"
    assert wp.make_label("process", "chrome") == "proceso chrome"
    assert wp.make_label("port", "80") == "puerto 80"


# ---------------------------------------------------------------- state_changed
def test_state_changed_file_mtime():
    old = {"exists": True, "mtime": 1, "size": 10}
    new = {"exists": True, "mtime": 2, "size": 10}
    assert wp.state_changed("file", old, new) is True


def test_state_changed_no_change():
    s = {"exists": True, "mtime": 1, "size": 10}
    assert wp.state_changed("file", s, dict(s)) is False


def test_state_changed_port():
    assert wp.state_changed("port", {"open": False}, {"open": True}) is True
    assert wp.state_changed("port", {"open": True}, {"open": True}) is False


def test_state_changed_none_safe():
    assert wp.state_changed("file", None, {"exists": True}) is False
    assert wp.state_changed("file", {"exists": True}, None) is False


# ---------------------------------------------------------------- describe_change
def test_describe_file_modified():
    out = wp.describe_change("fichero x.py", "file",
                             {"exists": True}, {"exists": True})
    assert "modificarse" in out


def test_describe_file_deleted():
    out = wp.describe_change("fichero x.py", "file",
                             {"exists": True}, {"exists": False})
    assert "desaparecido" in out


def test_describe_file_appeared():
    out = wp.describe_change("fichero x.py", "file",
                             {"exists": False}, {"exists": True})
    assert "aparecer" in out


def test_describe_process_stopped():
    out = wp.describe_change("proceso chrome", "process",
                             {"running": True, "count": 1}, {"running": False, "count": 0})
    assert "detenido" in out


def test_describe_process_started():
    out = wp.describe_change("proceso chrome", "process",
                             {"running": False, "count": 0}, {"running": True, "count": 2})
    assert "arrancar" in out


def test_describe_process_count_change():
    # Ambos en marcha pero cambia el número de instancias.
    out = wp.describe_change("proceso chrome", "process",
                             {"running": True, "count": 1}, {"running": True, "count": 3})
    assert "instancia" in out
    assert "3" in out


def test_describe_port_open_close():
    assert "abrirse" in wp.describe_change("puerto 80", "port", {"open": False}, {"open": True})
    assert "cerrado" in wp.describe_change("puerto 80", "port", {"open": True}, {"open": False})


# ---------------------------------------------------------------- _probe (sondas reales)
def test_probe_file_exists_and_missing(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hola", encoding="utf-8")
    st = wp._probe("file", str(f))
    assert st["exists"] is True
    assert st["size"] == 4
    missing = wp._probe("file", str(tmp_path / "no_existe.txt"))
    assert missing["exists"] is False
    assert missing["size"] is None


def test_probe_port_closed_and_invalid():
    # Puerto 1 prácticamente seguro cerrado en localhost.
    assert wp._probe("port", "1")["open"] is False
    # Target no numérico -> open False (rama ValueError).
    assert wp._probe("port", "abc")["open"] is False


def test_probe_process_no_match():
    st = wp._probe("process", "proceso_que_no_existe_xyz_123")
    assert st["running"] is False
    assert st["count"] == 0


def test_probe_process_match_self():
    # El propio intérprete de los tests es un proceso "python".
    st = wp._probe("process", "python")
    assert st["count"] >= 1
    assert st["running"] is True


# ---------------------------------------------------------------- format_watch_list
def test_format_watch_list_empty():
    assert "No tengo nada" in wp.format_watch_list([])


def test_format_watch_list_items():
    out = wp.format_watch_list([{"label": "fichero a.py"}, {"label": "puerto 80"}])
    assert "2 vigilancia" in out
    assert "fichero a.py" in out
    assert "puerto 80" in out


# ---------------------------------------------------------------- registro (add/remove/list)
def test_add_and_list_watch(monkeypatch):
    monkeypatch.setattr(wp, "_probe", lambda k, t: {"exists": True})
    w = wp.add_watch("file", "x.py")
    assert w["label"] == "fichero x.py"
    assert len(wp.list_watches()) == 1


def test_remove_watch(monkeypatch):
    monkeypatch.setattr(wp, "_probe", lambda k, t: {"exists": True})
    wp.add_watch("file", "config.py")
    wp.add_watch("process", "chrome")
    n = wp.remove_watch("config")
    assert n == 1
    assert len(wp.list_watches()) == 1


def test_remove_watch_no_match(monkeypatch):
    monkeypatch.setattr(wp, "_probe", lambda k, t: {"exists": True})
    wp.add_watch("file", "config.py")
    assert wp.remove_watch("inexistente") == 0


# ---------------------------------------------------------------- start_watch_command
def test_start_watch_command_unclear():
    out = wp.start_watch_command("vigila esto")
    assert "¿Qué desea que vigile" in out


def test_start_watch_command_registers(monkeypatch):
    monkeypatch.setattr(wp, "_probe", lambda k, t: {"exists": True})
    monkeypatch.setattr(wp, "_ensure_daemon", lambda: None)
    out = wp.start_watch_command("vigila el fichero config.py")
    assert "Vigilaré el fichero config.py" in out
    assert len(wp.list_watches()) == 1


# ---------------------------------------------------------------- _poll_once
def test_poll_once_notifies_on_change(monkeypatch):
    states = iter([{"exists": True, "mtime": 1, "size": 1},   # estado inicial (add)
                   {"exists": True, "mtime": 2, "size": 1}])  # primer sondeo
    monkeypatch.setattr(wp, "_probe", lambda k, t: next(states))
    wp.add_watch("file", "x.py")
    notified = []
    monkeypatch.setattr(wp, "_notify", lambda msg: notified.append(msg))
    wp._poll_once()
    assert len(notified) == 1
    assert "modificarse" in notified[0]


def test_poll_once_silent_when_stable(monkeypatch):
    monkeypatch.setattr(wp, "_probe", lambda k, t: {"exists": True, "mtime": 1, "size": 1})
    wp.add_watch("file", "x.py")
    notified = []
    monkeypatch.setattr(wp, "_notify", lambda msg: notified.append(msg))
    wp._poll_once()
    assert notified == []
