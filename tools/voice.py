import os
import uuid
import queue
import asyncio
import threading
import time
import logging
from pathlib import Path
import win32api

import edge_tts
import pygame
import pyttsx3
from elevenlabs.client import ElevenLabs

# Configuración del directorio temporal para audios
TEMP_DIR = Path("logs/audio_temp")

_speaking_active = False
# Cola de locuciones pendientes. Un único worker la consume en orden, de modo
# que varias llamadas concurrentes a speak() (saludo de arranque + daemons de
# fondo) se reproducen una tras otra y nunca se solapan.
_speech_queue = queue.Queue()

def is_speaking() -> bool:
    """Retorna True si Jarvis está reproduciendo voz, sintetizándola o tiene
    locuciones pendientes en la cola."""
    global _speaking_active
    try:
        mixer_busy = pygame.mixer.get_init() and pygame.mixer.music.get_busy()
    except Exception:
        mixer_busy = False
    return _speaking_active or mixer_busy or not _speech_queue.empty()

def wait_while_speaking() -> None:
    """Bloquea el hilo actual hasta que Jarvis termine de hablar."""
    while is_speaking():
        time.sleep(0.1)

def _speak_backup(text: str):
    """Capa 3: Motor offline pyttsx3."""
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        for voice in voices:
            if "pablo" in voice.name.lower() or "spanish" in voice.name.lower() or "español" in voice.name.lower():
                engine.setProperty("voice", voice.id)
                break
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 1.0)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logging.error(f"❌ Fallo crítico en el motor offline pyttsx3: {e}")

def _vad_monitor_thread():
    """Hilo de segundo plano para Detección Activa de Habla Local (VAD).
    
    Analiza la energía RMS del micrófono y detiene la voz si detecta voz del usuario.
    """
    import pyaudio
    import numpy as np
    
    p = pyaudio.PyAudio()
    stream = None
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
    except Exception as e:
        logging.error(f"[VAD] No se pudo acceder al micrófono para VAD: {e}")
        p.terminate()
        return

    # 1. FASE DE CALIBRACIÓN (0.3 segundos)
    # Medimos la energía máxima mientras suena el audio de Jarvis (para rechazo de eco)
    baseline_energies = []
    for _ in range(6):
        # Si la reproducción ya terminó, salimos del VAD
        if not pygame.mixer.get_init() or not pygame.mixer.music.get_busy():
            break
        try:
            data = stream.read(1024, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
            baseline_energies.append(rms)
        except Exception:
            pass
        time.sleep(0.05)

    max_baseline = max(baseline_energies) if baseline_energies else 150.0
    # Umbral dinámico parametrizable: 3.0x el valor máximo calibrado con un límite mínimo de 700.0 por defecto
    multiplier = float(os.getenv("JARVIS_VAD_MULTIPLIER", "3.0"))
    min_threshold = float(os.getenv("JARVIS_VAD_MIN_THRESHOLD", "700.0"))
    threshold = max(max_baseline * multiplier, min_threshold)
    logging.info(f"[VAD] Calibrado. Umbral dinámico establecido en: {threshold:.2f} (multiplicador={multiplier}, min={min_threshold})")

    consecutive_frames = 0
    req_frames = int(os.getenv("JARVIS_VAD_CONSECUTIVE_FRAMES", "4"))

    # 2. BUCLE DE MONITOREO ACTIVO
    while pygame.mixer.get_init() and pygame.mixer.music.get_busy():
        try:
            data = stream.read(1024, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
            
            if rms > threshold:
                consecutive_frames += 1
                if consecutive_frames >= req_frames:
                    logging.info(f"[VAD] Interrupción de voz detectada (RMS: {rms:.2f} > {threshold:.2f} por {consecutive_frames} frames). Deteniendo voz...")
                    stop_speak()
                    break
            else:
                consecutive_frames = 0
        except Exception as e:
            logging.warning(f"[VAD] Error durante el monitoreo: {e}")
            break
        time.sleep(0.02)

    # 3. LIMPIEZA
    try:
        if stream:
            stream.stop_stream()
            stream.close()
    except Exception:
        pass
    p.terminate()

def _play_audio(file_path: str, disable_vad: bool = False) -> bool:
    """Reproduce el audio temporal con pygame y lo elimina de forma segura."""
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        
        # Lanzar monitoreo VAD si está activo en las configuraciones
        vad_enabled = os.getenv("JARVIS_VAD_ENABLED", "True").lower() == "true" and not disable_vad
        if vad_enabled:
            threading.Thread(target=_vad_monitor_thread, daemon=True).start()
        
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
            
        pygame.mixer.music.unload()
        
        # Eliminar de inmediato para no saturar disco
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception as e:
        logging.error(f"⚠️ Error en reproducción de audio pygame: {e}")
        # Intentar borrar el archivo si falló la reproducción
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        return False

async def _generate_edge_tts(text: str, file_path: str, rate: str = "+0%", pitch: str = "+0Hz"):
    """Genera audio con Edge-TTS.

    La voz se configura con JARVIS_EDGE_TTS_VOICE en .env.
    Voces recomendadas (más graves/formales): es-ES-AlvaroNeural, es-ES-PabloNeural
    rate/pitch ajustan el tono (voz adaptativa); ver core.voice_tone.
    """
    voice = os.getenv("JARVIS_EDGE_TTS_VOICE", "es-ES-AlvaroNeural")
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(file_path)

def synthesize_to_file(text: str, tone=None):
    """Sintetiza `text` a un fichero mp3 y devuelve su ruta (sin reproducir).

    Pensado para enviar la voz de Jarvis por canales externos (p.ej. Telegram).
    Orden de motores: ElevenLabs -> Edge-TTS. Devuelve None si ambos fallan.
    El tono (voz adaptativa) se infiere del texto si no se indica.
    """
    if not text or not text.strip():
        return None
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    out_file = str(TEMP_DIR / f"tts_{uuid.uuid4().hex}.mp3")

    try:
        from core.voice_tone import resolve_tone, get_edge_params
        tone = resolve_tone(text, tone)
        edge = get_edge_params(tone)
    except Exception:
        tone = "neutral"
        edge = {"rate": "+0%", "pitch": "+0Hz"}

    eleven_key = os.getenv("ELEVENLABS_API_KEY")
    eleven_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "LlZr3QuzbW4WrPjgATHG")

    # CAPA 1: ElevenLabs
    if eleven_key:
        try:
            client = ElevenLabs(api_key=eleven_key)
            convert_kwargs = dict(
                text=text, voice_id=eleven_voice_id, model_id="eleven_multilingual_v2")
            vs = _eleven_voice_settings(tone)
            if vs is not None:
                convert_kwargs["voice_settings"] = vs
            audio_gen = client.text_to_speech.convert(**convert_kwargs)
            with open(out_file, "wb") as f:
                for chunk in audio_gen:
                    if chunk:
                        f.write(chunk)
            if os.path.getsize(out_file) > 0:
                return out_file
        except Exception as e:
            logging.warning(f"⚠️ ElevenLabs (a fichero) falló ({e}). Probando Edge-TTS...")

    # CAPA 2: Edge-TTS
    try:
        asyncio.run(_generate_edge_tts(text, out_file, rate=edge["rate"], pitch=edge["pitch"]))
        if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
            return out_file
    except Exception as e:
        logging.warning(f"⚠️ Edge-TTS (a fichero) falló ({e}).")

    return None


def _play_with_core(file_path: str, disable_vad: bool):
    """Reproduce el audio y, en paralelo, alimenta el núcleo holográfico reactivo
    a la voz de la GUI (envolvente de amplitud). Best-effort: nunca rompe la voz."""
    try:
        from core.voice_core import start_voice_core
        start_voice_core(file_path)
    except Exception:
        pass
    try:
        return _play_audio(file_path, disable_vad)
    finally:
        try:
            from core.voice_core import stop_voice_core
            stop_voice_core()
        except Exception:
            pass


def _eleven_voice_settings(tone: str):
    """Construye un VoiceSettings de ElevenLabs según el tono. None si no se puede."""
    try:
        from elevenlabs import VoiceSettings
        from core.voice_tone import get_eleven_settings
        s = get_eleven_settings(tone)
        return VoiceSettings(
            stability=s["stability"],
            similarity_boost=0.75,
            style=s["style"],
            use_speaker_boost=True,
        )
    except Exception:
        return None


def _synthesize_and_play(text: str, disable_vad: bool = False, tone=None):
    """Sintetiza y reproduce una locución (bloquea hasta terminar).

    Orden de prioridad de motores: ElevenLabs -> Edge-TTS -> pyttsx3.
    El tono (voz adaptativa) ajusta rate/pitch (Edge) y stability/style
    (ElevenLabs); si no se indica, se infiere del texto. Ver core.voice_tone.
    Lo invoca el worker de voz; no gestiona _speaking_active (lo hace el worker).
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = str(TEMP_DIR / f"speech_{uuid.uuid4().hex}.mp3")

    # Resolver el tono (explícito o detectado del texto), best-effort.
    adaptive = os.getenv("JARVIS_VOICE_ADAPTIVE_ENABLED", "true").lower() in ("true", "1", "yes")
    try:
        from core.voice_tone import resolve_tone, get_edge_params
        tone = resolve_tone(text, tone) if adaptive else "neutral"
        edge = get_edge_params(tone)
    except Exception:
        tone = "neutral"
        edge = {"rate": "+0%", "pitch": "+0Hz"}

    eleven_key = os.getenv("ELEVENLABS_API_KEY")
    eleven_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "LlZr3QuzbW4WrPjgATHG")

    # CAPA 1: ElevenLabs (Voz Premium)
    if eleven_key:
        try:
            client = ElevenLabs(api_key=eleven_key)
            convert_kwargs = dict(
                text=text,
                voice_id=eleven_voice_id,
                model_id="eleven_multilingual_v2",
            )
            vs = _eleven_voice_settings(tone)
            if vs is not None:
                convert_kwargs["voice_settings"] = vs
            audio_gen = client.text_to_speech.convert(**convert_kwargs)
            with open(temp_file, "wb") as f:
                for chunk in audio_gen:
                    if chunk:
                        f.write(chunk)

            if _play_with_core(temp_file, disable_vad):
                return
        except Exception as e:
            logging.warning(f"⚠️ ElevenLabs falló ({e}). Usando Capa 2 (Edge-TTS)...")

    # CAPA 2: Edge-TTS (Voz Neural Gratuita)
    try:
        asyncio.run(_generate_edge_tts(text, temp_file, rate=edge["rate"], pitch=edge["pitch"]))
        if _play_with_core(temp_file, disable_vad):
            return
    except Exception as e:
        logging.warning(f"⚠️ Edge-TTS falló ({e}). Usando Capa 3 (pyttsx3 Offline)...")

    # CAPA 3: Fallback Offline pyttsx3
    _speak_backup(text)


def _speech_worker():
    """Hilo único que consume la cola de locuciones y las reproduce en orden,
    una tras otra, garantizando que nunca se solapen."""
    global _speaking_active
    while True:
        text, disable_vad, tone = _speech_queue.get()
        _speaking_active = True
        try:
            _synthesize_and_play(text, disable_vad, tone)
        except Exception as e:
            logging.error(f"⚠️ Error en el worker de voz: {e}")
        finally:
            _speaking_active = False
            _speech_queue.task_done()

def stop_speak() -> None:
    """Detiene la voz actual y descarta las locuciones pendientes en la cola.

    Pensado para el barge-in (VAD/ESC/mute): si el usuario interrumpe, Jarvis se
    calla del todo en vez de seguir con lo que tuviera encolado.
    """
    # 1. Vaciar la cola de locuciones pendientes
    while True:
        try:
            _speech_queue.get_nowait()
            _speech_queue.task_done()
        except queue.Empty:
            break

    # 2. Cortar la reproducción en curso
    try:
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            logging.info("🔇 Voz de Jarvis interrumpida.")
    except Exception as e:
        logging.error(f"Error al detener la voz: {e}")

    # 3. Detener el núcleo holográfico reactivo (GUI)
    try:
        from core.voice_core import stop_voice_core
        stop_voice_core()
    except Exception:
        pass

def _global_key_listener():
    """Monitorea la tecla ESC (0x1B) para detener la voz en Windows."""
    while True:
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                # 0x1B es la tecla ESC
                if win32api.GetAsyncKeyState(0x1B) & 0x8000:
                    stop_speak()
        except Exception:
            pass
        time.sleep(0.05)

# Arrancar el hilo de escucha global de teclado en Windows
threading.Thread(target=_global_key_listener, daemon=True).start()

# Arrancar el worker único que serializa la reproducción de voz
threading.Thread(target=_speech_worker, daemon=True).start()

def speak(text: str, disable_vad: bool = False, tone=None) -> None:
    """
    Encola el texto para reproducirlo por voz de forma no bloqueante.

    Las locuciones se reproducen una tras otra mediante un worker único, de modo
    que nunca se solapan aunque varias partes del sistema llamen a speak() a la vez.
    Orden de prioridad de motores: ElevenLabs -> Edge-TTS -> pyttsx3.

    tone: perfil de voz adaptativa (neutral/alert/calm/success/humor). Si es None,
    se infiere automáticamente del texto. Ver core.voice_tone.
    """
    # Evitar llamadas vacías
    if not text or not text.strip():
        return

    _speech_queue.put((text, disable_vad, tone))
