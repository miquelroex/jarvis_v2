"""
core/voice_core.py — Núcleo Holográfico reactivo a la voz.

Mientras Jarvis habla, calcula la envolvente de amplitud (RMS por ventana) del
audio sintetizado y la transmite por Socket.IO (evento 'voice_level', 0..1) para
que la esfera central de la GUI pulse en tiempo real con la voz (lip-sync por
energía). Emite 'voice_core_start' al empezar y 'voice_core_stop' al terminar.

No toca la reproducción de audio (sigue en tools/voice.py con pygame.mixer.music):
sólo lee las muestras del archivo ya sintetizado con pygame.Sound.get_raw() y un
hilo emite la envolvente sincronizada con el inicio de la reproducción. Todo es
best-effort: si algo falla, la voz se reproduce igual y la GUI usa un pulso
sintético de respaldo.

La lógica de cálculo (compute_envelope) es pura y testeable.
"""
import os
import sys
import logging
import threading

logger = logging.getLogger(__name__)

_stream_stop = threading.Event()
_stream_thread = None


def compute_envelope(samples, channels: int, sample_rate: int, fps: int = 30) -> list:
    """Envolvente de amplitud (0..1) por fotograma a partir de muestras int16.

    samples: numpy.ndarray int16 (posiblemente intercalado por canal).
    Devuelve una lista de floats en [0,1], uno por fotograma a `fps`.
    Función pura (sólo numpy)."""
    import numpy as np
    if samples is None or len(samples) == 0:
        return []
    data = np.asarray(samples, dtype=np.float32)
    # Mezclar a mono si viene intercalado por canales.
    if channels and channels > 1 and data.size >= channels:
        usable = (data.size // channels) * channels
        data = data[:usable].reshape(-1, channels).mean(axis=1)
    fps = max(1, int(fps))
    win = max(1, int(sample_rate / fps))
    n_frames = max(1, int(np.ceil(len(data) / win)))
    env = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        chunk = data[i * win:(i + 1) * win]
        if chunk.size:
            env[i] = float(np.sqrt(np.mean(chunk * chunk)))
    peak = float(env.max())
    if peak <= 1e-9:
        return [0.0] * n_frames
    env = env / peak                      # normalizar a 0..1
    env = np.power(env, 0.65)             # realzar (gamma) para que se note más
    return [round(float(x), 3) for x in env]


def _emit(event: str, payload=None):
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        if payload is None:
            mod.socketio.emit(event)
        else:
            mod.socketio.emit(event, payload)
    except Exception:
        pass


def _stream_envelope(envelope, fps: int):
    """Emite la envolvente fotograma a fotograma a `fps`, hasta agotarla o parar."""
    import time
    period = 1.0 / max(1, fps)
    for level in envelope:
        if _stream_stop.is_set():
            break
        _emit("voice_level", {"level": level})
        time.sleep(period)


def start_voice_core(file_path: str):
    """Calcula la envolvente del audio y arranca su emisión sincronizada.
    Best-effort: nunca lanza. Off-able con JARVIS_VOICE_CORE_ENABLED."""
    global _stream_thread
    if os.getenv("JARVIS_VOICE_CORE_ENABLED", "true").lower() not in ("true", "1", "yes"):
        return
    _emit("voice_core_start")
    fps = int(os.getenv("JARVIS_VOICE_CORE_FPS", "30"))
    envelope = []
    try:
        import pygame
        import numpy as np
        snd = pygame.mixer.Sound(file_path)
        raw = snd.get_raw()
        arr = np.frombuffer(raw, dtype=np.int16)
        init = pygame.mixer.get_init()  # (freq, size, channels)
        if init:
            rate, _size, channels = init
        else:
            rate, channels = 44100, 2
        envelope = compute_envelope(arr, channels, rate, fps=fps)
    except Exception as e:
        logger.debug(f"[VoiceCore] Envolvente no disponible ({e}); GUI usará pulso sintético.")
        return  # el frontend anima un pulso de respaldo entre start y stop

    _stream_stop.set()
    if _stream_thread is not None and _stream_thread.is_alive():
        _stream_thread.join(timeout=1)
    _stream_stop.clear()
    _stream_thread = threading.Thread(
        target=_stream_envelope, args=(envelope, fps), name="VoiceCoreStream", daemon=True)
    _stream_thread.start()


def stop_voice_core():
    """Detiene la emisión de la envolvente y avisa a la GUI. Best-effort."""
    _stream_stop.set()
    _emit("voice_core_stop")