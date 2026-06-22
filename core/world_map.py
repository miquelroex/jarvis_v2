"""
core/world_map.py — Mapa/globo 3D del mundo (Mapbox).

Permite a Jarvis abrir un globo 3D en la GUI y "volar" a lugares por voz:
geocodifica un nombre de lugar a coordenadas (Mapbox Geocoding) y emite el
evento al frontend, que anima el vuelo con map.flyTo().

Módulo ligero (stdlib). Requiere MAPBOX_TOKEN para geocodificar.
"""
import os
import sys
import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

# Zoom por defecto al volar a un lugar (ciudad).
DEFAULT_FLY_ZOOM = float(os.getenv("JARVIS_MAP_FLY_ZOOM", "9"))


def get_mapbox_token() -> str:
    """Token público de Mapbox (pk....) desde el entorno, o cadena vacía."""
    return os.getenv("MAPBOX_TOKEN", "").strip()


def geocode(place: str) -> dict:
    """Convierte un nombre de lugar en coordenadas vía Mapbox Geocoding.

    Returns {"lng", "lat", "name"} o None si no hay token, el lugar está vacío
    o no se encuentra.
    """
    place = (place or "").strip()
    if not place:
        return None
    token = get_mapbox_token()
    if not token:
        logger.info("[WorldMap] Sin MAPBOX_TOKEN; no se puede geocodificar.")
        return None
    url = (
        "https://api.mapbox.com/geocoding/v5/mapbox.places/"
        + urllib.parse.quote(place)
        + ".json?"
        + urllib.parse.urlencode({"access_token": token, "limit": 1, "language": "es"})
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        features = data.get("features", [])
        if not features:
            return None
        center = features[0].get("center")  # [lng, lat]
        if not center or len(center) < 2:
            return None
        return {
            "lng": center[0],
            "lat": center[1],
            "name": features[0].get("place_name", place),
            "zoom": DEFAULT_FLY_ZOOM,
        }
    except Exception as e:
        logger.warning(f"[WorldMap] Error al geocodificar '{place}': {e}")
        return None


def _emit(event: str, payload: dict = None) -> bool:
    """Emite un evento a la GUI SOLO si gui.app ya está cargado (no la importa)."""
    mod = sys.modules.get("gui.app")
    if mod is None:
        return False
    try:
        mod.socketio.emit(event, payload or {})
        return True
    except Exception:
        return False


def open_map() -> bool:
    """Pide a la GUI abrir el globo 3D."""
    return _emit("map_open")


def close_map() -> bool:
    """Pide a la GUI cerrar el globo 3D."""
    return _emit("map_close")


def fly_to(place: str) -> dict:
    """Geocodifica un lugar y pide a la GUI volar hasta él. Devuelve la ubicación
    o None si no se pudo geocodificar."""
    location = geocode(place)
    if location is None:
        return None
    _emit("map_flyto", location)
    return location