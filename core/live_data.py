"""
core/live_data.py — APIs de datos del mundo en vivo (legal y gratuito).

Conecta a Jarvis con datos reales y actuales usando APIs públicas SIN clave:
  - Finanzas cripto  → CoinGecko
  - Sismos           → USGS (United States Geological Survey)
  - Tech-news        → Hacker News (Algolia)

Cada dato se expone (a) por voz de forma directa y (b) como una FUENTE del Motor
de Fusión con relevancia por tema (`live_source`), de modo que el motor de
fusión y el investigador ganan datos del mundo automáticamente, sin ruido (sólo
consulta lo que la pregunta menciona).

Los parsers de cada payload son funciones PURAS y testeables; las llamadas HTTP
se aíslan y degradan con gracia (devuelven None si fallan o no hay red).
"""
import json
import logging
import unicodedata
import re
import urllib.request

logger = logging.getLogger(__name__)

_CRYPTO_IDS = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "cardano": "cardano", "ada": "cardano",
    "solana": "solana", "sol": "solana",
    "dogecoin": "dogecoin", "doge": "dogecoin",
}

# Nombres de empresa -> símbolo de Stooq (bolsa, API gratuita sin clave).
_STOCK_TICKERS = {
    "apple": "aapl.us", "aapl": "aapl.us",
    "microsoft": "msft.us", "msft": "msft.us",
    "google": "googl.us", "alphabet": "googl.us", "googl": "googl.us",
    "amazon": "amzn.us", "amzn": "amzn.us",
    "tesla": "tsla.us", "tsla": "tsla.us",
    "nvidia": "nvda.us", "nvda": "nvda.us",
    "meta": "meta.us", "facebook": "meta.us",
    "netflix": "nflx.us", "nflx": "nflx.us",
}
_STOCK_NAMES = {"aapl.us": "Apple", "msft.us": "Microsoft", "googl.us": "Alphabet",
                "amzn.us": "Amazon", "tsla.us": "Tesla", "nvda.us": "NVIDIA",
                "meta.us": "Meta", "nflx.us": "Netflix"}


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ----------------------------------------------------------------------------
# Parsers (puros)
# ----------------------------------------------------------------------------
def parse_crypto(data: dict) -> str:
    """Resumen de precios cripto a partir del payload de CoinGecko (puro)."""
    nombres = {"bitcoin": "Bitcoin", "ethereum": "Ethereum", "cardano": "Cardano",
               "solana": "Solana", "dogecoin": "Dogecoin"}
    parts = []
    for coin, info in (data or {}).items():
        if not isinstance(info, dict) or "usd" not in info:
            continue
        price = info["usd"]
        change = info.get("usd_24h_change")
        nombre = nombres.get(coin, coin.capitalize())
        trozo = f"{nombre}: {price:,.0f} USD".replace(",", ".")
        if change is not None:
            signo = "+" if change >= 0 else ""
            trozo += f" ({signo}{change:.1f}% 24h)"
        parts.append(trozo)
    return "; ".join(parts) if parts else ""


def parse_earthquakes(geojson: dict, limit: int = 5) -> str:
    """Resumen de sismos a partir del GeoJSON de USGS (puro)."""
    features = (geojson or {}).get("features", [])
    quakes = []
    for f in features:
        props = f.get("properties", {}) or {}
        mag = props.get("mag")
        place = props.get("place")
        if mag is None or not place:
            continue
        quakes.append((mag, place))
    if not quakes:
        return ""
    quakes.sort(key=lambda q: q[0], reverse=True)
    top = quakes[:limit]
    items = "; ".join(f"M{mag:.1f} {place}" for mag, place in top)
    return f"{len(quakes)} sismos recientes. Mayores: {items}"


def parse_hn(data: dict, limit: int = 5) -> str:
    """Resumen de portada de Hacker News a partir del payload de Algolia (puro)."""
    hits = (data or {}).get("hits", [])
    titles = []
    for h in hits:
        title = (h.get("title") or "").strip()
        if not title:
            continue
        points = h.get("points")
        titles.append(f"«{title}»" + (f" ({points} pts)" if points else ""))
        if len(titles) >= limit:
            break
    return "Portada de Hacker News: " + "; ".join(titles) if titles else ""


def parse_stock_csv(csv_text: str):
    """Cotización a partir del CSV de Stooq. {symbol, price, change_pct} o None (puro).

    Cabecera: Symbol,Date,Time,Open,High,Low,Close,Volume. La variación es
    intradía (cierre vs apertura)."""
    if not csv_text or not csv_text.strip():
        return None
    lines = [l for l in csv_text.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    fields = lines[1].split(",")
    if len(fields) < 7:
        return None
    try:
        open_p = float(fields[3])
        close_p = float(fields[6])
    except (ValueError, IndexError):
        return None
    change = ((close_p - open_p) / open_p * 100) if open_p else 0.0
    return {"symbol": fields[0], "price": close_p, "change_pct": change}


def format_stock(info: dict) -> str:
    """Frase de cotización de una acción (puro)."""
    if not info:
        return ""
    name = _STOCK_NAMES.get(info["symbol"].lower(),
                            info["symbol"].replace(".US", "").replace(".us", "").upper())
    chg = info["change_pct"]
    signo = "+" if chg >= 0 else ""
    return f"{name}: {info['price']:.2f} USD ({signo}{chg:.1f}% en la sesión)"


def ticker_in_query(query: str):
    """Símbolo de Stooq para la empresa mencionada en la pregunta, o None (puro)."""
    tokens = set(re.findall(r"[a-z]+", _normalize(query)))
    for name, sym in _STOCK_TICKERS.items():
        if name in tokens:
            return sym
    return None


def detect_topic(query: str):
    """Tema de datos en vivo relevante para una pregunta, o None (puro)."""
    q = _normalize(query)
    # Bolsa primero (una empresa concreta o mención al mercado), porque "precio
    # de"/"cotización" son genéricos y si no los robaría el caso cripto.
    if ticker_in_query(query) or any(k in q for k in ["bolsa", "accion", "acciones", "nasdaq"]):
        return "stock"
    if any(k in q for k in ["bitcoin", "btc", "ethereum", "eth", "cripto", "crypto",
                            "solana", "dogecoin", "cardano"]):
        return "crypto"
    if any(k in q for k in ["terremoto", "sismo", "seismo", "earthquake", "temblor"]):
        return "earthquakes"
    if any(k in q for k in ["hacker news", "noticias de tecnologia", "tech news",
                            "noticias tech", "portada de hacker"]):
        return "news"
    if "precio de" in q or "cotizacion" in q:  # genérico sin más -> cripto por defecto
        return "crypto"
    return None


def coins_in_query(query: str):
    """IDs de CoinGecko mencionados en la pregunta (puro). Por defecto BTC y ETH."""
    q = _normalize(query)
    found = []
    for alias, cid in _CRYPTO_IDS.items():
        if alias in q and cid not in found:
            found.append(cid)
    return found or ["bitcoin", "ethereum"]


# ----------------------------------------------------------------------------
# HTTP (aislado)
# ----------------------------------------------------------------------------
def _http_json(url: str, timeout: float = 8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.debug(f"[LiveData] Fallo al consultar {url[:60]}…: {e}")
        return None


def _http_text(url: str, timeout: float = 8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception as e:
        logger.debug(f"[LiveData] Fallo al consultar {url[:60]}…: {e}")
        return None


def fetch_stock_raw(symbol: str):
    """Cotización cruda de Stooq (bolsa, sin clave). {symbol,price,change_pct} o None."""
    url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
    return parse_stock_csv(_http_text(url))


def get_stock(symbol: str) -> str:
    return format_stock(fetch_stock_raw(symbol))


def fetch_crypto_raw(coins=None) -> dict:
    """Payload crudo de CoinGecko (dict por moneda), {} si falla."""
    coins = coins or ["bitcoin", "ethereum"]
    ids = ",".join(coins)
    url = (f"https://api.coingecko.com/api/v3/simple/price?ids={ids}"
           "&vs_currencies=usd&include_24hr_change=true")
    return _http_json(url) or {}


def fetch_earthquakes_raw() -> dict:
    """GeoJSON crudo de USGS (sismos M≥4.5 último día), {} si falla."""
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
    return _http_json(url) or {}


def get_crypto(coins=None) -> str:
    return parse_crypto(fetch_crypto_raw(coins))


def get_earthquakes() -> str:
    return parse_earthquakes(fetch_earthquakes_raw())


def get_tech_news() -> str:
    url = "https://hn.algolia.com/api/v1/search?tags=front_page"
    data = _http_json(url)
    return parse_hn(data) if data else ""


# ----------------------------------------------------------------------------
# Integración con el Motor de Fusión
# ----------------------------------------------------------------------------
def live_source(query: str):
    """Fuente de datos en vivo con relevancia por tema (para el motor de fusión)."""
    topic = detect_topic(query)
    if topic == "stock":
        return get_stock(ticker_in_query(query) or "^spx") or None
    if topic == "crypto":
        return get_crypto(coins_in_query(query)) or None
    if topic == "earthquakes":
        return get_earthquakes() or None
    if topic == "news":
        return get_tech_news() or None
    return None
