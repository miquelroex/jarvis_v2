"""
Módulo de Speech-to-Text basado en faster-whisper.

Características:
- Carga lazy del modelo (no carga al importar ni al arrancar Jarvis)
- Cacheo de un único modelo en memoria (thread-safe)
- Cambio dinámico de modelo vía JARVIS_WHISPER_MODEL en .env
- Fallback automático a Google Web Speech API
- Logging de latencia, modelo usado y engine usado

Configuración vía .env:
    JARVIS_STT_ENGINE        = whisper | google
    JARVIS_WHISPER_MODEL     = small | medium | large-v3  (default: small)
    JARVIS_WHISPER_DEVICE    = auto | cpu | cuda          (default: auto)
    JARVIS_WHISPER_LANGUAGE  = es                         (default: es)
    JARVIS_WHISPER_PROMPT    = contexto inicial para Whisper
"""

import io
import os
import time
import logging
import threading
from typing import Optional

import speech_recognition as sr

logger = logging.getLogger(__name__)

# ─── Importar faster-whisper de forma segura ─────────────────────
try:
    from faster_whisper import WhisperModel as _WhisperModelClass
except ImportError:
    _WhisperModelClass = None

# ─── Cacheo de modelo (module-level, thread-safe) ────────────────
_model = None
_model_name: Optional[str] = None
_model_lock = threading.Lock()


def _get_model():
    """Carga lazy y cacheo del modelo Whisper. Thread-safe.

    Si JARVIS_WHISPER_MODEL cambia en .env respecto al modelo
    cacheado, se descarga el anterior y se carga el nuevo.

    Returns:
        Instancia de WhisperModel lista para transcribir.

    Raises:
        ImportError: Si faster-whisper no está instalado.
    """
    global _model, _model_name

    if _WhisperModelClass is None:
        raise ImportError(
            "faster-whisper no está instalado. "
            "Instala con: pip install faster-whisper"
        )

    target_model = os.getenv("JARVIS_WHISPER_MODEL", "small")

    with _model_lock:
        # Devolver modelo cacheado si coincide
        if _model is not None and _model_name == target_model:
            return _model

        # Descargar modelo anterior si se está cambiando
        if _model is not None:
            logger.info(
                f"[Whisper] Descargando modelo '{_model_name}' "
                f"para cargar '{target_model}'..."
            )
            _model = None
            _model_name = None

        # Determinar dispositivo y tipo de cómputo
        device = os.getenv("JARVIS_WHISPER_DEVICE", "auto")
        compute_type = os.getenv("JARVIS_WHISPER_COMPUTE_TYPE", "")

        if not compute_type:
            if device == "cpu":
                compute_type = "int8"
            else:
                # Para "cuda" y "auto", float16 es óptimo
                compute_type = "float16"

        logger.info(
            f"[Whisper] Cargando modelo '{target_model}' "
            f"(device={device}, compute_type={compute_type})..."
        )
        load_start = time.time()

        _model = _WhisperModelClass(
            target_model,
            device=device,
            compute_type=compute_type,
        )
        _model_name = target_model

        load_elapsed = time.time() - load_start
        logger.info(
            f"[Whisper] ✅ Modelo '{target_model}' cargado en "
            f"{load_elapsed:.2f}s (device={device}, compute={compute_type})"
        )

        return _model


def transcribe_audio(audio: sr.AudioData, google_fallback: bool = True) -> str:
    """Transcribe audio usando Whisper, con fallback opcional a Google.

    Args:
        audio: AudioData de SpeechRecognition (capturado del micrófono).
        google_fallback: Si True, usa Google Web Speech API cuando
            Whisper falla o devuelve texto vacío.

    Returns:
        Texto transcrito.

    Raises:
        Exception: Si Whisper falla y google_fallback es False.
    """
    engine_used = "whisper"
    model_used = os.getenv("JARVIS_WHISPER_MODEL", "small")

    try:
        start = time.time()

        # Convertir AudioData de SpeechRecognition → WAV → BytesIO
        wav_data = audio.get_wav_data()
        audio_stream = io.BytesIO(wav_data)

        model = _get_model()

        language = os.getenv("JARVIS_WHISPER_LANGUAGE", "es")
        initial_prompt = os.getenv(
            "JARVIS_WHISPER_PROMPT",
            "Jarvis, abre el navegador, busca en Google, ejecuta el "
            "comando, qué hora es, pon música, apágate, desactívate, "
            "cuánto cuesta, busca información, dime el tiempo, programa, "
            "envía un mensaje, enciende las luces, crea un archivo"
        )

        segments, info = model.transcribe(
            audio_stream,
            language=language,
            initial_prompt=initial_prompt,
            beam_size=5,
            vad_filter=True,
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()

        elapsed = time.time() - start
        logger.info(
            f"[STT] ✅ engine={engine_used} | model={model_used} | "
            f"latency={elapsed:.2f}s | text=\"{text}\""
        )

        if not text:
            raise ValueError("Whisper devolvió texto vacío")

        return text

    except Exception as e:
        logger.warning(
            f"[Whisper] ⚠️ Error en transcripción "
            f"({type(e).__name__}: {e}). "
            f"{'Usando fallback Google...' if google_fallback else 'Sin fallback.'}"
        )

        if google_fallback:
            return _google_transcribe(audio)
        raise


def _google_transcribe(audio: sr.AudioData) -> str:
    """Transcribe audio usando Google Web Speech API (fallback).

    Args:
        audio: AudioData de SpeechRecognition.

    Returns:
        Texto transcrito por Google.
    """
    start = time.time()

    recognizer = sr.Recognizer()
    text = recognizer.recognize_google(audio, language="es-ES")

    elapsed = time.time() - start
    logger.info(
        f"[STT] ✅ engine=google | model=web_speech_api | "
        f"latency={elapsed:.2f}s | text=\"{text}\""
    )

    return text


def unload_model() -> None:
    """Descarga explícitamente el modelo cacheado para liberar VRAM/RAM."""
    global _model, _model_name
    with _model_lock:
        if _model is not None:
            logger.info(f"[Whisper] Descargando modelo '{_model_name}' de memoria.")
            _model = None
            _model_name = None
        else:
            logger.info("[Whisper] No hay modelo cargado.")


def get_model_info() -> dict:
    """Retorna información sobre el modelo actualmente cargado/configurado."""
    return {
        "loaded": _model is not None,
        "model_name": _model_name,
        "configured_model": os.getenv("JARVIS_WHISPER_MODEL", "small"),
        "configured_engine": os.getenv("JARVIS_STT_ENGINE", "whisper"),
        "device": os.getenv("JARVIS_WHISPER_DEVICE", "auto"),
    }
