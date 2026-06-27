"""Tests de core/initiative.py — Iniciativa Ejecutora (proactividad con criterio)."""
import core.initiative as ini


def _state(ram=40, threat="green", unknown=0, running=12, dirty=3, reasons=None):
    return {
        "system": {"ram": ram},
        "threat": {"level": threat, "reasons": reasons or []},
        "network": {"unknown": unknown},
        "services": {"running": running},
        "project": {"dirty_count": dirty},
    }


def setup_function(_):
    ini._last_fired.clear()
    ini._prev_state = None


# ---------------------------------------------------------------- detect_initiatives
def test_no_prev_no_initiatives():
    assert ini.detect_initiatives(None, _state()) == []
    assert ini.detect_initiatives({}, _state()) == []


def test_ram_critical_crossing():
    out = ini.detect_initiatives(_state(ram=70), _state(ram=92))
    ids = [i["id"] for i in out]
    assert "ram_critical" in ids
    ram_init = next(i for i in out if i["id"] == "ram_critical")
    assert ram_init["risk"] == ini.RISK_SAFE
    assert ram_init["action"] == "free_memory"


def test_ram_no_fire_if_already_critical():
    # Ya estaba crítica antes: no es un cruce nuevo.
    out = ini.detect_initiatives(_state(ram=95), _state(ram=96))
    assert "ram_critical" not in [i["id"] for i in out]


def test_threat_escalation():
    out = ini.detect_initiatives(_state(threat="green"),
                                 _state(threat="red", reasons=["intrusos", "RAM"]))
    t = next(i for i in out if i["id"] == "threat_up")
    assert t["risk"] == ini.RISK_INFO
    assert "ROJA".lower() in t["message"].lower() or "RED" in t["message"]
    assert "intrusos" in t["message"]


def test_threat_no_fire_on_deescalation():
    out = ini.detect_initiatives(_state(threat="red"), _state(threat="green"))
    assert "threat_up" not in [i["id"] for i in out]


def test_net_intruder():
    out = ini.detect_initiatives(_state(unknown=0), _state(unknown=1))
    assert "net_intruder" in [i["id"] for i in out]


def test_service_down():
    out = ini.detect_initiatives(_state(running=12), _state(running=10))
    assert "service_down" in [i["id"] for i in out]


def test_dirty_commit_crossing():
    out = ini.detect_initiatives(_state(dirty=10), _state(dirty=30))
    d = next(i for i in out if i["id"] == "dirty_commit")
    assert "30 cambios" in d["message"]


def test_dirty_no_fire_below_threshold():
    out = ini.detect_initiatives(_state(dirty=5), _state(dirty=20))
    assert "dirty_commit" not in [i["id"] for i in out]


def test_multiple_initiatives_at_once():
    out = ini.detect_initiatives(_state(ram=70, threat="green", unknown=0),
                                 _state(ram=95, threat="amber", unknown=2))
    ids = {i["id"] for i in out}
    assert {"ram_critical", "threat_up", "net_intruder"} <= ids


# ---------------------------------------------------------------- decide_response
def test_decide_off_skips():
    assert ini.decide_response({"risk": ini.RISK_INFO}, "off") == "skip"
    assert ini.decide_response({"risk": ini.RISK_SAFE, "action": "x"}, "off") == "skip"


def test_decide_notify_announces_everything():
    assert ini.decide_response({"risk": ini.RISK_SAFE, "action": "x"}, "notify") == "announce"
    assert ini.decide_response({"risk": ini.RISK_INFO}, "notify") == "announce"


def test_decide_act_executes_safe():
    assert ini.decide_response({"risk": ini.RISK_SAFE, "action": "free_memory"}, "act") == "execute"


def test_decide_act_safe_without_action_announces():
    assert ini.decide_response({"risk": ini.RISK_SAFE}, "act") == "announce"


def test_decide_act_info_announces():
    assert ini.decide_response({"risk": ini.RISK_INFO}, "act") == "announce"


def test_decide_act_risky_asks():
    assert ini.decide_response({"risk": ini.RISK_RISKY}, "act") == "ask"


# ---------------------------------------------------------------- format_action_announcement
def test_format_action_announcement():
    out = ini.format_action_announcement({"message": "RAM alta."}, "Liberados 10 objetos.")
    assert "Me he tomado la libertad" in out
    assert "RAM alta." in out
    assert "Liberados 10 objetos." in out


# ---------------------------------------------------------------- _cooldown_ok
def test_cooldown_blocks_repeats():
    assert ini._cooldown_ok("x", now=1000, cooldown=600) is True
    assert ini._cooldown_ok("x", now=1100, cooldown=600) is False   # dentro del cooldown
    assert ini._cooldown_ok("x", now=2000, cooldown=600) is True    # ya pasó


# ---------------------------------------------------------------- run_once (integración)
def test_run_once_notify_announces(monkeypatch):
    states = iter([_state(ram=70), _state(ram=95)])
    monkeypatch.setattr(ini, "_prev_state", None, raising=False)
    # Primer ciclo establece la línea base; segundo detecta el cruce.
    import core.world_model as wm
    monkeypatch.setattr(wm, "snapshot", lambda: next(states))
    announced = []
    monkeypatch.setattr(ini, "_announce", lambda m: announced.append(m))
    monkeypatch.setattr(ini, "_execute", lambda i: announced.append("EXEC:" + i["id"]))
    ini.run_once(level="notify")  # baseline (prev None -> nada)
    ini.run_once(level="notify")  # detecta ram_critical -> announce (no execute en notify)
    assert any("RAM" in m for m in announced)
    assert not any(m.startswith("EXEC") for m in announced)


def test_run_once_act_executes_safe(monkeypatch):
    states = iter([_state(ram=70), _state(ram=95)])
    import core.world_model as wm
    monkeypatch.setattr(wm, "snapshot", lambda: next(states))
    executed = []
    monkeypatch.setattr(ini, "_execute", lambda i: executed.append(i["id"]))
    monkeypatch.setattr(ini, "_announce", lambda m: None)
    ini.run_once(level="act")
    ini.run_once(level="act")
    assert "ram_critical" in executed


def test_run_once_cooldown_prevents_repeat(monkeypatch):
    import core.world_model as wm
    # Mundo siempre "recién cruzado" para forzar la iniciativa cada ciclo.
    seq = iter([_state(ram=70), _state(ram=95), _state(ram=70), _state(ram=95)])
    monkeypatch.setattr(wm, "snapshot", lambda: next(seq))
    count = []
    monkeypatch.setattr(ini, "_announce", lambda m: count.append(m))
    ini.run_once(level="notify")  # baseline
    ini.run_once(level="notify")  # dispara
    ini.run_once(level="notify")  # baseline de nuevo
    ini.run_once(level="notify")  # dispararía, pero cooldown lo bloquea
    assert len(count) == 1


# ---------------------------------------------------------------- daemon gating
def test_start_daemon_off(monkeypatch):
    monkeypatch.setenv("JARVIS_INITIATIVE_LEVEL", "off")
    ini.INITIATIVE_THREAD = None
    ini.start_initiative_daemon()
    assert ini.INITIATIVE_THREAD is None


def test_stop_daemon_sets_event():
    ini.stop_event.clear()
    ini.stop_initiative_daemon()
    assert ini.stop_event.is_set()
    ini.stop_event.clear()
