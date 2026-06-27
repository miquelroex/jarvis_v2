"""Tests de core/live_data.py — APIs de datos del mundo en vivo."""
import core.live_data as ld


# ---------------------------------------------------------------- parse_crypto
def test_parse_crypto_basic():
    data = {"bitcoin": {"usd": 45000, "usd_24h_change": -2.34},
            "ethereum": {"usd": 2500, "usd_24h_change": 1.2}}
    out = ld.parse_crypto(data)
    assert "Bitcoin: 45.000 USD (-2.3% 24h)" in out
    assert "Ethereum: 2.500 USD (+1.2% 24h)" in out


def test_parse_crypto_positive_sign():
    out = ld.parse_crypto({"bitcoin": {"usd": 100, "usd_24h_change": 5.0}})
    assert "(+5.0% 24h)" in out


def test_parse_crypto_no_change():
    out = ld.parse_crypto({"bitcoin": {"usd": 100}})
    assert "Bitcoin: 100 USD" in out
    assert "24h" not in out


def test_parse_crypto_skips_malformed():
    data = {"bitcoin": {"usd": 100}, "x": "no-dict", "y": {"no_usd": 1}}
    out = ld.parse_crypto(data)
    assert "Bitcoin" in out
    assert "x" not in out and "y" not in out


def test_parse_crypto_empty():
    assert ld.parse_crypto({}) == ""
    assert ld.parse_crypto(None) == ""


# ---------------------------------------------------------------- parse_earthquakes
def test_parse_earthquakes_sorts_by_magnitude():
    geo = {"features": [
        {"properties": {"mag": 4.8, "place": "cerca de A"}},
        {"properties": {"mag": 6.1, "place": "cerca de B"}},
        {"properties": {"mag": 5.0, "place": "cerca de C"}},
    ]}
    out = ld.parse_earthquakes(geo)
    assert "3 sismos recientes" in out
    # El mayor (6.1) aparece primero.
    assert out.index("M6.1") < out.index("M5.0") < out.index("M4.8")


def test_parse_earthquakes_limit():
    geo = {"features": [{"properties": {"mag": float(i), "place": f"P{i}"}} for i in range(10)]}
    out = ld.parse_earthquakes(geo, limit=2)
    assert out.count("M") == 3  # "sismos" no tiene M; 2 items M.. + el "M" de nada... contamos items
    # Comprobación más robusta: sólo 2 lugares listados.
    assert "P9" in out and "P8" in out and "P7" not in out


def test_parse_earthquakes_skips_incomplete():
    geo = {"features": [
        {"properties": {"mag": 5.0, "place": "ok"}},
        {"properties": {"mag": None, "place": "sin mag"}},
        {"properties": {"mag": 4.9}},  # sin place
    ]}
    out = ld.parse_earthquakes(geo)
    assert "1 sismos recientes" in out
    assert "ok" in out


def test_parse_earthquakes_empty():
    assert ld.parse_earthquakes({"features": []}) == ""
    assert ld.parse_earthquakes(None) == ""


# ---------------------------------------------------------------- parse_hn
def test_parse_hn_basic():
    data = {"hits": [
        {"title": "Rust 2.0 lanzado", "points": 320},
        {"title": "Nuevo modelo de IA", "points": 150},
    ]}
    out = ld.parse_hn(data)
    assert "Portada de Hacker News" in out
    assert "«Rust 2.0 lanzado» (320 pts)" in out


def test_parse_hn_limit_and_skip_empty():
    data = {"hits": [{"title": ""}, {"title": "A"}, {"title": "B"}, {"title": "C"}]}
    out = ld.parse_hn(data, limit=2)
    assert "«A»" in out and "«B»" in out
    assert "«C»" not in out


def test_parse_hn_empty():
    assert ld.parse_hn({"hits": []}) == ""


# ---------------------------------------------------------------- detect_topic
def test_detect_topic_crypto():
    assert ld.detect_topic("¿cuál es el precio del bitcoin?") == "crypto"
    assert ld.detect_topic("cómo va la cripto hoy") == "crypto"


def test_detect_topic_earthquakes():
    assert ld.detect_topic("¿ha habido algún terremoto?") == "earthquakes"
    assert ld.detect_topic("últimos sismos") == "earthquakes"


def test_detect_topic_news():
    assert ld.detect_topic("dame las noticias de tecnología") == "news"
    assert ld.detect_topic("qué hay en hacker news") == "news"


def test_detect_topic_none():
    assert ld.detect_topic("¿qué tiempo hace?") is None
    assert ld.detect_topic("") is None


# ---------------------------------------------------------------- coins_in_query
def test_coins_in_query_detects_aliases():
    # El orden lo marca el registro de alias, no la query; comparamos como conjunto.
    assert set(ld.coins_in_query("precio de eth y btc")) == {"ethereum", "bitcoin"}


def test_coins_in_query_default():
    assert ld.coins_in_query("precio de la cripto") == ["bitcoin", "ethereum"]


def test_coins_in_query_dedupes():
    # 'bitcoin' y 'btc' mapean al mismo id: no se duplica.
    assert ld.coins_in_query("bitcoin btc") == ["bitcoin"]


# ---------------------------------------------------------------- live_source (relevancia)
def test_live_source_crypto(monkeypatch):
    monkeypatch.setattr(ld, "get_crypto", lambda coins: "Bitcoin: 1 USD")
    assert ld.live_source("precio del bitcoin") == "Bitcoin: 1 USD"


def test_live_source_earthquakes(monkeypatch):
    monkeypatch.setattr(ld, "get_earthquakes", lambda: "1 sismos")
    assert ld.live_source("últimos terremotos") == "1 sismos"


def test_live_source_news(monkeypatch):
    monkeypatch.setattr(ld, "get_tech_news", lambda: "Portada HN")
    assert ld.live_source("noticias de tecnología") == "Portada HN"


def test_live_source_irrelevant_returns_none():
    assert ld.live_source("¿qué tiempo hace en Madrid?") is None


def test_live_source_empty_result_is_none(monkeypatch):
    monkeypatch.setattr(ld, "get_crypto", lambda coins: "")
    assert ld.live_source("precio del bitcoin") is None


# ---------------------------------------------------------------- fetchers degradan con gracia
def test_get_crypto_handles_no_data(monkeypatch):
    monkeypatch.setattr(ld, "_http_json", lambda url, timeout=8: None)
    assert ld.get_crypto() == ""
