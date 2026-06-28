"""Tests de core/intrusion.py — Contra-intrusión (defensa del equipo)."""
import core.intrusion as it


# ---------------------------------------------------------------- find_suspicious
def test_find_suspicious_matches_patterns():
    names = ["chrome.exe", "mimikatz.exe", "code.exe", "PsExec64.exe"]
    out = it.find_suspicious(names)
    assert "mimikatz.exe" in out
    assert "PsExec64.exe" in out
    assert "chrome.exe" not in out


def test_find_suspicious_case_insensitive():
    assert it.find_suspicious(["MIMIKATZ.EXE"]) == ["MIMIKATZ.EXE"]


def test_find_suspicious_custom_patterns():
    assert it.find_suspicious(["evilbot"], patterns=["evil"]) == ["evilbot"]


def test_find_suspicious_empty():
    assert it.find_suspicious([]) == []
    assert it.find_suspicious(None) == []


# ---------------------------------------------------------------- new_suspicious
def test_new_suspicious_only_new():
    prev = ["chrome.exe", "mimikatz.exe"]
    curr = ["chrome.exe", "mimikatz.exe", "ncat.exe"]
    # mimikatz ya estaba; sólo ncat es nuevo.
    assert it.new_suspicious(prev, curr) == ["ncat.exe"]


def test_new_suspicious_none_new():
    assert it.new_suspicious(["mimikatz.exe"], ["mimikatz.exe", "chrome.exe"]) == []


# ---------------------------------------------------------------- failed_login_spike
def test_failed_login_spike_above_threshold():
    assert it.failed_login_spike(2, 7, threshold=3) == 5


def test_failed_login_spike_below_threshold():
    assert it.failed_login_spike(2, 4, threshold=3) == 0


def test_failed_login_spike_handles_none():
    assert it.failed_login_spike(None, 5, threshold=3) == 5


# ---------------------------------------------------------------- detect_events
def test_detect_events_new_process():
    prev = {"process_names": ["chrome.exe"], "failed_logins": 0}
    curr = {"process_names": ["chrome.exe", "mimikatz.exe"], "failed_logins": 0}
    events = it.detect_events(prev, curr)
    assert len(events) == 1
    assert events[0]["kind"] == "process"
    assert events[0]["severity"] == "high"


def test_detect_events_login_spike():
    prev = {"process_names": [], "failed_logins": 1}
    curr = {"process_names": [], "failed_logins": 6}
    events = it.detect_events(prev, curr, login_threshold=3)
    assert any(e["kind"] == "logins" and e["detail"] == 5 for e in events)


def test_detect_events_no_prev_flags_present_suspicious():
    # Sin baseline, alerta de los sospechosos ya presentes.
    curr = {"process_names": ["mimikatz.exe"], "failed_logins": 0}
    events = it.detect_events(None, curr)
    assert len(events) == 1
    assert events[0]["detail"] == "mimikatz.exe"


def test_detect_events_quiet():
    prev = {"process_names": ["chrome.exe"], "failed_logins": 0}
    curr = {"process_names": ["chrome.exe"], "failed_logins": 0}
    assert it.detect_events(prev, curr) == []


# ---------------------------------------------------------------- describe_event
def test_describe_event_process():
    out = it.describe_event({"kind": "process", "detail": "mimikatz.exe"})
    assert "potencialmente hostil" in out
    assert "mimikatz.exe" in out


def test_describe_event_logins():
    out = it.describe_event({"kind": "logins", "detail": 5})
    assert "5 intentos de acceso fallidos" in out


# ---------------------------------------------------------------- build_scan_report
def test_scan_report_suspicious():
    curr = {"process_names": ["chrome.exe", "ncat.exe"], "failed_logins": 0, "external_conns": 3}
    out = it.build_scan_report(curr)
    assert "potencialmente hostiles" in out
    assert "ncat.exe" in out


def test_scan_report_failed_logins():
    curr = {"process_names": ["chrome.exe"], "failed_logins": 8, "external_conns": 0}
    out = it.build_scan_report(curr, login_threshold=5)
    assert "8 accesos fallidos" in out


def test_scan_report_clear_with_external():
    curr = {"process_names": ["chrome.exe"], "failed_logins": 0, "external_conns": 4}
    out = it.build_scan_report(curr)
    assert "Perímetro asegurado" in out
    assert "4 conexiones salientes" in out


def test_scan_report_clear_no_external():
    curr = {"process_names": ["chrome.exe"], "failed_logins": 0, "external_conns": 0}
    out = it.build_scan_report(curr)
    assert "Perímetro asegurado" in out
    assert "conexiones" not in out


# ---------------------------------------------------------------- run_once / scan_now
def test_scan_now(monkeypatch):
    monkeypatch.setattr(it, "_gather", lambda: {"process_names": ["mimikatz.exe"],
                                                "failed_logins": 0, "external_conns": 0})
    assert "potencialmente hostiles" in it.scan_now()


def test_run_once_notifies_on_new_threat(monkeypatch):
    seq = iter([
        {"process_names": ["chrome.exe"], "failed_logins": 0, "external_conns": 0},
        {"process_names": ["chrome.exe", "mimikatz.exe"], "failed_logins": 0, "external_conns": 0},
    ])
    monkeypatch.setattr(it, "_gather", lambda: next(seq))
    notified = []
    monkeypatch.setattr(it, "_notify", lambda m: notified.append(m))
    it._prev = None
    it._last_alert.clear()
    it.run_once()  # baseline (mimikatz no presente)
    it.run_once()  # aparece mimikatz -> alerta
    assert any("mimikatz" in m for m in notified)


# ---------------------------------------------------------------- daemon
def test_start_daemon_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_INTRUSION_ENABLED", "false")
    it.INTRUSION_THREAD = None
    it.start_intrusion_daemon()
    assert it.INTRUSION_THREAD is None


def test_stop_daemon_sets_event():
    it.stop_event.clear()
    it.stop_intrusion_daemon()
    assert it.stop_event.is_set()
    it.stop_event.clear()
