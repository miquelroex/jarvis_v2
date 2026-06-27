"""Tests de core/world_watch.py — Vigilancia Proactiva del Mundo."""
import core.world_watch as ww


def setup_function(_):
    with ww._lock:
        ww.WATCHES.clear()


# ---------------------------------------------------------------- parse_watch_request
def test_parse_crypto_by_name():
    assert ww.parse_watch_request("vigila el bitcoin") == {"kind": "crypto", "coin": "bitcoin"}
    assert ww.parse_watch_request("avísame si cambia ethereum") == {"kind": "crypto", "coin": "ethereum"}


def test_parse_crypto_by_alias_word():
    assert ww.parse_watch_request("vigila btc") == {"kind": "crypto", "coin": "bitcoin"}
    assert ww.parse_watch_request("sigue sol")["coin"] == "solana"


def test_parse_crypto_generic():
    assert ww.parse_watch_request("vigila la cripto") == {"kind": "crypto", "coin": "bitcoin"}


def test_parse_earthquake():
    assert ww.parse_watch_request("avísame de terremotos") == {"kind": "earthquake"}
    assert ww.parse_watch_request("vigila los sismos") == {"kind": "earthquake"}


def test_parse_stock():
    assert ww.parse_watch_request("vigila la acción de apple") == {"kind": "stock", "symbol": "aapl.us"}
    assert ww.parse_watch_request("avísame si tesla se mueve") == {"kind": "stock", "symbol": "tsla.us"}


def test_add_stock_watch(monkeypatch):
    monkeypatch.setattr(ww, "_stock_price", lambda s: 204.0)
    w = ww.add_stock_watch("aapl.us", threshold=3)
    assert w["kind"] == "stock"
    assert w["name"] == "Apple"
    assert w["last_price"] == 204.0


def test_poll_stock_alerts(monkeypatch):
    monkeypatch.setattr(ww, "_stock_price", lambda s: 220.0)
    notified = []
    monkeypatch.setattr(ww, "_notify", lambda m: notified.append(m))
    watch = {"kind": "stock", "symbol": "aapl.us", "name": "Apple",
             "threshold": 3, "last_price": 200.0}
    ww._poll_stock(watch)
    assert len(notified) == 1
    assert "subido un 10.0%" in notified[0]


def test_start_watch_command_stock(monkeypatch):
    monkeypatch.setattr(ww, "_stock_price", lambda s: 204.0)
    monkeypatch.setattr(ww, "_ensure_daemon", lambda: None)
    out = ww.start_watch_command("vigila la acción de apple")
    assert "Vigilaré la acción de Apple" in out


def test_parse_no_false_positive_on_substrings():
    # 'sol' en 'consola', 'ada' en 'nada' NO deben activar cripto.
    assert ww.parse_watch_request("vigila la consola") is None
    assert ww.parse_watch_request("no vigiles nada") is None


def test_parse_none_for_files():
    # Petición de fichero -> None (la maneja el Puesto de Vigilancia).
    assert ww.parse_watch_request("vigila el fichero config.py") is None


# ---------------------------------------------------------------- crypto_pct_change / should_alert
def test_crypto_pct_change():
    assert ww.crypto_pct_change(100, 110) == 10.0
    assert ww.crypto_pct_change(100, 95) == -5.0
    assert ww.crypto_pct_change(0, 100) == 0.0  # baseline 0 protegido


def test_should_alert_crypto():
    assert ww.should_alert_crypto(100, 106, 5) is True   # +6% >= 5
    assert ww.should_alert_crypto(100, 96, 5) is False   # -4% < 5
    assert ww.should_alert_crypto(100, 103, 5) is False  # +3% < 5
    assert ww.should_alert_crypto(100, 105, 5) is True   # -exacto en el umbral


def test_should_alert_crypto_negative_crosses():
    assert ww.should_alert_crypto(100, 94, 5) is True    # -6% >= 5


# ---------------------------------------------------------------- describe_crypto_alert
def test_describe_crypto_alert_up():
    out = ww.describe_crypto_alert("Bitcoin", 40000, 44000)
    assert "Bitcoin ha subido un 10.0%" in out
    assert "44.000 USD" in out


def test_describe_crypto_alert_down():
    out = ww.describe_crypto_alert("Ethereum", 2000, 1800)
    assert "ha caído un 10.0%" in out


# ---------------------------------------------------------------- new_significant_quakes
def _quake(qid, mag, place="cerca de algún sitio"):
    return {"id": qid, "properties": {"mag": mag, "place": place}}


def test_new_significant_quakes_filters_seen_and_mag():
    features = [_quake("a", 6.0), _quake("b", 4.0), _quake("c", 5.5)]
    out = ww.new_significant_quakes(seen_ids={"a"}, features=features, min_mag=5.0)
    ids = [q["id"] for q in out]
    assert ids == ["c"]  # 'a' ya visto, 'b' magnitud baja


def test_new_significant_quakes_skips_incomplete():
    features = [{"id": "x", "properties": {"mag": None, "place": "p"}},
                {"id": "y", "properties": {"mag": 6.0}}]  # sin place
    assert ww.new_significant_quakes(set(), features, 5.0) == []


def test_new_significant_quakes_empty():
    assert ww.new_significant_quakes(set(), [], 5.0) == []


def test_describe_quake_alert():
    out = ww.describe_quake_alert({"id": "x", "mag": 6.3, "place": "100km al sur de Lima"})
    assert "magnitud 6.3" in out
    assert "100km al sur de Lima" in out


# ---------------------------------------------------------------- format_watch_list
def test_format_watch_list_empty():
    assert "No vigilo nada del mundo" in ww.format_watch_list([])


def test_format_watch_list_items():
    out = ww.format_watch_list([{"kind": "crypto", "name": "Bitcoin"},
                                {"kind": "earthquake", "min_mag": 5}])
    assert "Bitcoin" in out
    assert "terremotos (M≥5)" in out


# ---------------------------------------------------------------- registro
def test_add_crypto_watch(monkeypatch):
    monkeypatch.setattr(ww, "_coin_price", lambda c: 45000.0)
    w = ww.add_crypto_watch("bitcoin", threshold=5)
    assert w["name"] == "Bitcoin"
    assert w["last_price"] == 45000.0
    assert len(ww.list_watches()) == 1


def test_add_quake_watch_seeds_seen(monkeypatch):
    monkeypatch.setattr(ww, "_quake_features", lambda: [_quake("a", 6.0), _quake("b", 5.0)])
    w = ww.add_quake_watch(min_mag=5)
    assert w["seen_ids"] == {"a", "b"}  # los actuales no vuelven a avisar


def test_remove_world_watches(monkeypatch):
    monkeypatch.setattr(ww, "_coin_price", lambda c: 1.0)
    ww.add_crypto_watch("bitcoin")
    assert ww.remove_world_watches() == 1
    assert ww.list_watches() == []


# ---------------------------------------------------------------- start_watch_command
def test_start_watch_command_crypto(monkeypatch):
    monkeypatch.setattr(ww, "_coin_price", lambda c: 45000.0)
    monkeypatch.setattr(ww, "_ensure_daemon", lambda: None)
    out = ww.start_watch_command("vigila el bitcoin")
    assert "Vigilaré Bitcoin" in out


def test_start_watch_command_quake(monkeypatch):
    monkeypatch.setattr(ww, "_quake_features", lambda: [])
    monkeypatch.setattr(ww, "_ensure_daemon", lambda: None)
    out = ww.start_watch_command("avísame de terremotos")
    assert "actividad sísmica" in out


def test_start_watch_command_returns_none_for_non_world():
    # No es un tema del mundo -> None (lo maneja otro comando).
    assert ww.start_watch_command("vigila el fichero x.py") is None


# ---------------------------------------------------------------- _poll_crypto
def test_poll_crypto_alerts_on_threshold(monkeypatch):
    monkeypatch.setattr(ww, "_coin_price", lambda c: 110.0)
    notified = []
    monkeypatch.setattr(ww, "_notify", lambda m: notified.append(m))
    watch = {"kind": "crypto", "coin": "bitcoin", "name": "Bitcoin",
             "threshold": 5, "last_price": 100.0}
    ww._poll_crypto(watch)
    assert len(notified) == 1
    assert "subido un 10.0%" in notified[0]
    assert watch["last_price"] == 110.0  # referencia actualizada tras avisar


def test_poll_crypto_silent_below_threshold(monkeypatch):
    monkeypatch.setattr(ww, "_coin_price", lambda c: 102.0)
    notified = []
    monkeypatch.setattr(ww, "_notify", lambda m: notified.append(m))
    watch = {"kind": "crypto", "coin": "bitcoin", "name": "Bitcoin",
             "threshold": 5, "last_price": 100.0}
    ww._poll_crypto(watch)
    assert notified == []
    assert watch["last_price"] == 100.0  # sin cambios


def test_poll_crypto_seeds_first_reading(monkeypatch):
    monkeypatch.setattr(ww, "_coin_price", lambda c: 200.0)
    monkeypatch.setattr(ww, "_notify", lambda m: None)
    watch = {"kind": "crypto", "coin": "bitcoin", "name": "Bitcoin",
             "threshold": 5, "last_price": None}
    ww._poll_crypto(watch)
    assert watch["last_price"] == 200.0


# ---------------------------------------------------------------- _poll_quake
def test_poll_quake_alerts_new(monkeypatch):
    monkeypatch.setattr(ww, "_quake_features",
                        lambda: [_quake("a", 6.0), _quake("b", 4.0)])
    notified = []
    monkeypatch.setattr(ww, "_notify", lambda m: notified.append(m))
    watch = {"kind": "earthquake", "min_mag": 5.0, "seen_ids": set()}
    ww._poll_quake(watch)
    assert len(notified) == 1
    assert "magnitud 6.0" in notified[0]
    # Tras sondear, todos los vistos quedan registrados (también el menor).
    assert watch["seen_ids"] == {"a", "b"}


def test_poll_quake_no_repeat(monkeypatch):
    monkeypatch.setattr(ww, "_quake_features", lambda: [_quake("a", 6.0)])
    notified = []
    monkeypatch.setattr(ww, "_notify", lambda m: notified.append(m))
    watch = {"kind": "earthquake", "min_mag": 5.0, "seen_ids": {"a"}}
    ww._poll_quake(watch)
    assert notified == []


# ---------------------------------------------------------------- daemon
def test_stop_daemon_sets_event():
    ww.stop_event.clear()
    ww.stop_world_watch_daemon()
    assert ww.stop_event.is_set()
    ww.stop_event.clear()
