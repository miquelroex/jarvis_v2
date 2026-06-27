"""
core/barge_in.py — Lógica de interrupción por voz (barge-in) para full-duplex.

Para que Jarvis se sienta conversacional, mientras HABLA sigue escuchando: si
detecta que empiezas a hablar, corta su propia voz al instante y te cede el
turno. La decisión (calibrar el ruido de fondo + eco, fijar un umbral dinámico y
disparar sólo tras varios frames seguidos por encima) vivía enterrada en el hilo
de audio de tools/voice.py, sin tests.

Aquí se extrae a una máquina de estados PURA y testeable: el hilo sólo lee el
micrófono (RMS por frame) y delega la decisión. Así el comportamiento full-duplex
es afinable y verificable sin tocar el audio real.
"""
import os
import math
import time

# Señal de barge-in: el hilo de audio la marca al cortar la voz; la siguiente
# escucha la consume para capturar de inmediato (el usuario YA está hablando),
# sin recalibrar y con una pausa corta — así no se pierde su turno.
_last_barge_in = 0.0


def signal_barge_in(now: float = None):
    """Marca que acaba de ocurrir una interrupción por voz (llamada desde el VAD)."""
    global _last_barge_in
    _last_barge_in = now if now is not None else time.time()


def is_recent(ts: float, now: float, window: float) -> bool:
    """¿El timestamp `ts` cae dentro de `window` segundos antes de `now`? (puro)."""
    return ts > 0 and (now - ts) <= window


def consume_barge_in(now: float = None, window: float = 4.0) -> bool:
    """Consume la señal de barge-in si es reciente (de un solo uso). Devuelve bool."""
    global _last_barge_in
    now = now if now is not None else time.time()
    if is_recent(_last_barge_in, now, window):
        _last_barge_in = 0.0
        return True
    return False


def capture_mode(barge_in_pending: bool) -> dict:
    """Parámetros de captura según haya o no un barge-in pendiente (puro).

    Con barge-in: no recalibrar (settle=False) y pausa corta, para enganchar al
    usuario que ya habla. Sin él: comportamiento normal."""
    if barge_in_pending:
        return {"settle": False,
                "pause_threshold": float(os.getenv("JARVIS_BARGE_CAPTURE_PAUSE", "0.5"))}
    return {"settle": True,
            "pause_threshold": float(os.getenv("JARVIS_ASR_PAUSE_THRESHOLD", "0.8"))}


def rms_int16(samples) -> float:
    """Energía RMS de una secuencia de muestras PCM int16 (puro, sin numpy)."""
    n = 0
    acc = 0.0
    for s in samples or []:
        acc += float(s) * float(s)
        n += 1
    if n == 0:
        return 0.0
    return math.sqrt(acc / n)


def compute_threshold(baselines, multiplier: float, min_threshold: float) -> float:
    """Umbral dinámico de interrupción a partir de la calibración (puro).

    Toma la energía máxima medida mientras Jarvis hablaba (rechazo de eco), la
    multiplica y nunca baja del mínimo configurado."""
    base = max(baselines) if baselines else 0.0
    return max(base * multiplier, min_threshold)


class BargeInDetector:
    """Máquina de estados de barge-in: se calibra y luego decide la interrupción.

    Uso: calibrate(rms) varias veces → finalize_calibration() → feed(rms) por
    frame; feed devuelve True cuando hay que cortar la voz de Jarvis."""

    def __init__(self, multiplier: float = 3.0, min_threshold: float = 700.0,
                 required_frames: int = 4):
        self.multiplier = multiplier
        self.min_threshold = min_threshold
        self.required_frames = max(1, required_frames)
        self.baselines = []
        self.threshold = None
        self.consecutive = 0

    def calibrate(self, rms: float):
        """Acumula una muestra de calibración (ruido/eco mientras Jarvis habla)."""
        self.baselines.append(rms)

    def finalize_calibration(self) -> float:
        """Fija el umbral a partir de las muestras de calibración. Idempotente."""
        self.threshold = compute_threshold(self.baselines, self.multiplier, self.min_threshold)
        return self.threshold

    def feed(self, rms: float) -> bool:
        """Procesa un frame; devuelve True cuando se decide interrumpir.

        Requiere `required_frames` frames CONSECUTIVOS por encima del umbral
        (evita disparos por picos puntuales/golpes)."""
        if self.threshold is None:
            self.finalize_calibration()
        if rms > self.threshold:
            self.consecutive += 1
            if self.consecutive >= self.required_frames:
                return True
        else:
            self.consecutive = 0
        return False

    def reset(self):
        """Reinicia el contador de frames (no la calibración)."""
        self.consecutive = 0
