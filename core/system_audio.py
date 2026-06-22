"""
core/system_audio.py — Control de volumen y multimedia del sistema (Windows).

- Volumen maestro y silencio: vía pycaw (Core Audio).
- Reproducción multimedia (play/pausa/siguiente/anterior): simulando las teclas
  multimedia con win32api, así controla Spotify y cualquier reproductor.

Imports perezosos (pycaw/win32api) para que el módulo sea ligero y testeable.
Las funciones de volumen devuelven -1 si el audio no está disponible.
"""
import logging

logger = logging.getLogger(__name__)

# Virtual-Key codes de las teclas multimedia.
_MEDIA_KEYS = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
}


def _get_endpoint():
    """Devuelve el control de volumen del dispositivo de salida por defecto (pycaw)."""
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_volume() -> int:
    """Volumen maestro actual en porcentaje (0-100), o -1 si no está disponible."""
    try:
        scalar = _get_endpoint().GetMasterVolumeLevelScalar()
        return int(round(scalar * 100))
    except Exception as e:
        logger.warning(f"[Audio] No se pudo leer el volumen: {e}")
        return -1


def set_volume(percent: int) -> int:
    """Fija el volumen maestro (se acota a 0-100). Subirlo desmutea. -1 si falla."""
    percent = max(0, min(100, int(percent)))
    try:
        ep = _get_endpoint()
        ep.SetMasterVolumeLevelScalar(percent / 100.0, None)
        if percent > 0:
            ep.SetMute(0, None)
        return percent
    except Exception as e:
        logger.warning(f"[Audio] No se pudo fijar el volumen: {e}")
        return -1


def change_volume(delta: int) -> int:
    """Sube/baja el volumen de forma relativa. -1 si no está disponible."""
    current = get_volume()
    if current < 0:
        return -1
    return set_volume(current + delta)


def set_mute(state: bool) -> bool:
    """Silencia (True) o reactiva (False) el sonido. Devuelve si tuvo éxito."""
    try:
        _get_endpoint().SetMute(1 if state else 0, None)
        return True
    except Exception as e:
        logger.warning(f"[Audio] No se pudo cambiar el silencio: {e}")
        return False


def is_muted() -> bool:
    """True si el sistema está silenciado."""
    try:
        return bool(_get_endpoint().GetMute())
    except Exception:
        return False


def media_action(action: str) -> bool:
    """Envía una tecla multimedia: play_pause | next | previous | stop."""
    vk = _MEDIA_KEYS.get(action)
    if vk is None:
        return False
    try:
        import win32api
        import win32con
        win32api.keybd_event(vk, 0, 0, 0)
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        logger.warning(f"[Audio] No se pudo enviar la tecla multimedia '{action}': {e}")
        return False
