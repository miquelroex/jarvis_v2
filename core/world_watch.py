"""
core/world_watch.py — Vigilancia Proactiva del Mundo.

Como el Puesto de Vigilancia (watchpost) pero apuntando al MUNDO en lugar de a
ficheros/procesos: registras qué seguir (una cripto, los terremotos) y un daemon
sondea los datos en vivo (core/live_data) y te avisa SIN que se lo pidas cuando
hay un cambio significativo: "Señor, Bitcoin acaba de caer un 5%" / "sismo de
magnitud 6 detectado".

Es la cara "datos del mundo" de la proactividad: complementa la Iniciativa
Ejecutora (que vigila el estado interno) con vigilancia de fuentes externas.

El parseo de la petición, el cálculo de variación, los umbrales de aviso y las
frases son funciones PURAS y testeables; las llamadas a las APIs (vía live_data)
y el daemon de sondeo se aíslan.
"""
import os
import re
import sys
import logging
import threading
import unicodedata

logger = logging.getLogger(__name__)

WATCHES = []  # crypto: {kind, coin, name, threshold, last_price}; quake: {kind, min_mag, seen_ids}
_lock = threading.Lock()
WATCH_THREAD = None
stop_event = threading.Event()

_COIN_NAMES = {"bitcoin": "Bitcoin", "ethereum": "Ethereum", "cardano": "Cardano",
               "solana": "Solana", "dogecoin": "Dogecoin"}


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ----------------------------------------------------------------------------
# Parseo de la petición (puro)
# ----------------------------------------------------------------------------
def parse_watch_request(text: str):
    """Interpreta "vigila el bitcoin" / "avísame de terremotos". {kind,...} o None. Puro."""
    from core.live_data import _CRYPTO_IDS
    q = _normalize(text)
    if any(k in q for k in ["terremoto", "sismo", "seismo", "temblor", "earthquake"]):
        return {"kind": "earthquake"}
    # Casar alias cripto por PALABRA COMPLETA (evita 'sol' en 'consola', 'ada' en 'nada').
    tokens = set(re.findall(r"[a-z]+", q))
    for alias, cid in _CRYPTO_IDS.items():
        if alias in tokens:
            return {"kind": "crypto", "coin": cid}
    if "cripto" in tokens or "crypto" in tokens:
        return {"kind": "crypto", "coin": "bitcoin"}
    return None


# ----------------------------------------------------------------------------
# Lógica de aviso (pura)
# ----------------------------------------------------------------------------
def crypto_pct_change(baseline: float, current: float) -> float:
    """Variación porcentual de baseline a current (puro). 0 si baseline es 0."""
    if not baseline:
        return 0.0
    return (current - baseline) / baseline * 100


def should_alert_crypto(baseline: float, current: float, threshold_pct: float) -> bool:
    """¿La variación supera el umbral? (puro)."""
    return abs(crypto_pct_change(baseline, current)) >= threshold_pct


def describe_crypto_alert(name: str, baseline: float, current: float) -> str:
    """Frase de aviso de variación de una cripto (puro)."""
    pct = crypto_pct_change(baseline, current)
    verbo = "subido" if pct >= 0 else "caído"
    precio = f"{current:,.0f}".replace(",", ".")
    return f"Señor, {name} ha {verbo} un {abs(pct):.1f}%: ahora {precio} USD."


def new_significant_quakes(seen_ids, features, min_mag: float):
    """Sismos nuevos (no vistos) con magnitud >= min_mag (puro)."""
    seen = set(seen_ids or [])
    out = []
    for f in features or []:
        qid = f.get("id")
        props = f.get("properties", {}) or {}
        mag = props.get("mag")
        place = props.get("place")
        if not qid or qid in seen or mag is None or place is None:
            continue
        if mag >= min_mag:
            out.append({"id": qid, "mag": mag, "place": place})
    return out


def describe_quake_alert(quake: dict) -> str:
    """Frase de aviso de un sismo (puro)."""
    return f"Señor, sismo de magnitud {quake['mag']:.1f} detectado: {quake['place']}."


def format_watch_list(watches) -> str:
    """Texto del listado de vigilancias del mundo activas (puro)."""
    if not watches:
        return "No vigilo nada del mundo ahora mismo, señor."
    etiquetas = []
    for w in watches:
        if w["kind"] == "crypto":
            etiquetas.append(w.get("name", w.get("coin", "cripto")))
        else:
            etiquetas.append(f"terremotos (M≥{w.get('min_mag', 5)})")
    return "Vigilo del mundo, señor: " + "; ".join(etiquetas) + "."


# ----------------------------------------------------------------------------
# Registro de vigilancias (aislado: lee precios/sismos iniciales)
# ----------------------------------------------------------------------------
def _quake_features():
    from core.live_data import fetch_earthquakes_raw
    return (fetch_earthquakes_raw() or {}).get("features", [])


def _coin_price(coin: str):
    from core.live_data import fetch_crypto_raw
    data = fetch_crypto_raw([coin])
    info = (data or {}).get(coin)
    if isinstance(info, dict):
        return info.get("usd")
    return None


def add_crypto_watch(coin: str, threshold: float = None) -> dict:
    if threshold is None:
        threshold = float(os.getenv("JARVIS_WORLDWATCH_CRYPTO_THRESHOLD", "5"))
    price = _coin_price(coin)
    watch = {"kind": "crypto", "coin": coin, "name": _COIN_NAMES.get(coin, coin.capitalize()),
             "threshold": threshold, "last_price": price}
    with _lock:
        WATCHES.append(watch)
    return watch


def add_quake_watch(min_mag: float = None) -> dict:
    if min_mag is None:
        min_mag = float(os.getenv("JARVIS_WORLDWATCH_QUAKE_MAG", "5"))
    # Sembrar con los sismos ya existentes para avisar sólo de los NUEVOS.
    seen = {f.get("id") for f in _quake_features() if f.get("id")}
    watch = {"kind": "earthquake", "min_mag": min_mag, "seen_ids": seen}
    with _lock:
        WATCHES.append(watch)
    return watch


def remove_world_watches() -> int:
    with _lock:
        n = len(WATCHES)
        WATCHES.clear()
        return n


def list_watches():
    with _lock:
        return list(WATCHES)


def start_watch_command(text: str) -> str:
    """Procesa "vigila el bitcoin / avísame de terremotos" y registra la vigilancia."""
    req = parse_watch_request(text)
    if not req:
        return None  # no es una vigilancia del mundo; el llamador sigue con otros comandos
    if req["kind"] == "crypto":
        w = add_crypto_watch(req["coin"])
        _ensure_daemon()
        precio = (f" (ahora {w['last_price']:,.0f} USD)".replace(",", ".")
                  if w["last_price"] else "")
        return f"Vigilaré {w['name']}, señor{precio}. Le avisaré ante un cambio relevante."
    w = add_quake_watch()
    _ensure_daemon()
    return (f"Vigilaré la actividad sísmica, señor. Le avisaré de cualquier sismo "
            f"de magnitud {w['min_mag']:.0f} o superior.")


# ----------------------------------------------------------------------------
# Daemon de sondeo (aislado)
# ----------------------------------------------------------------------------
def _notify(message: str):
    mod = sys.modules.get("gui.app")
    if mod is not None:
        try:
            mod.socketio.emit("watch_alert", {"text": message})
        except Exception:
            pass
    try:
        from tools.voice import speak
        speak(message, disable_vad=True)
    except Exception:
        pass


def _poll_crypto(watch):
    price = _coin_price(watch["coin"])
    if price is None:
        return
    baseline = watch.get("last_price")
    if baseline and should_alert_crypto(baseline, price, watch["threshold"]):
        _notify(describe_crypto_alert(watch["name"], baseline, price))
        watch["last_price"] = price  # nueva referencia tras avisar
    elif baseline is None:
        watch["last_price"] = price  # primera lectura: fijar referencia


def _poll_quake(watch):
    features = _quake_features()
    nuevos = new_significant_quakes(watch.get("seen_ids", set()), features, watch["min_mag"])
    for q in nuevos:
        _notify(describe_quake_alert(q))
    # Marcar TODOS los vistos (también los menores) para no repetir.
    watch.setdefault("seen_ids", set()).update(f.get("id") for f in features if f.get("id"))


def _poll_once():
    for watch in list_watches():
        try:
            if watch["kind"] == "crypto":
                _poll_crypto(watch)
            else:
                _poll_quake(watch)
        except Exception as e:
            logger.debug(f"[WorldWatch] Error sondeando {watch.get('kind')}: {e}")


def _watch_loop():
    while not stop_event.is_set():
        interval = int(os.getenv("JARVIS_WORLDWATCH_INTERVAL", "300"))
        if stop_event.wait(timeout=interval):
            break
        _poll_once()


def _ensure_daemon():
    global WATCH_THREAD
    if WATCH_THREAD is not None and WATCH_THREAD.is_alive():
        return
    stop_event.clear()
    WATCH_THREAD = threading.Thread(target=_watch_loop, name="WorldWatchDaemon", daemon=True)
    WATCH_THREAD.start()
    logging.info("[WorldWatch] Vigilancia del mundo iniciada.")


def start_world_watch_daemon():
    """Arranca el daemon si está habilitado (JARVIS_WORLDWATCH_ENABLED, off por defecto).
    Aun desactivado, las vigilancias añadidas por voz arrancan el daemon bajo demanda."""
    if os.getenv("JARVIS_WORLDWATCH_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[WorldWatch] Desactivado en .env (se activa bajo demanda por voz).")
        return
    _ensure_daemon()


def stop_world_watch_daemon():
    """Detiene el daemon de vigilancia del mundo."""
    stop_event.set()
