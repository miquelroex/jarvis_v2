import os
import uuid
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

def is_speaking() -> bool:
    """Retorna True si Jarvis está reproduciendo voz o sintetizándola."""
    global _speaking_active
    try:
        mixer_busy = pygame.mixer.get_init() and pygame.mixer.music.get_busy()
    except Exception:
        mixer_busy = False
    return _speaking_active or mixer_busy

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

async def _generate_edge_tts(text: str, file_path: str):
    """Genera audio con Edge-TTS."""
    communicate = edge_tts.Communicate(text, "es-ES-AlvaroNeural")
    await communicate.save(file_path)

def _speak_thread(text: str, disable_vad: bool = False):
    """Bucle de ejecución asíncrono para la síntesis y reproducción de voz."""
    global _speaking_active
    _speaking_active = True
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = str(TEMP_DIR / f"speech_{uuid.uuid4().hex}.mp3")

        eleven_key = os.getenv("ELEVENLABS_API_KEY")
        eleven_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "LlZr3QuzbW4WrPjgATHG")

        # CAPA 1: ElevenLabs (Voz Premium)
        if eleven_key:
            try:
                client = ElevenLabs(api_key=eleven_key)
                audio_gen = client.text_to_speech.convert(
                    text=text,
                    voice_id=eleven_voice_id,
                    model_id="eleven_multilingual_v2"
                )
                with open(temp_file, "wb") as f:
                    for chunk in audio_gen:
                        if chunk:
                            f.write(chunk)
                
                if _play_audio(temp_file, disable_vad):
                    return
            except Exception as e:
                logging.warning(f"⚠️ ElevenLabs falló ({e}). Usando Capa 2 (Edge-TTS)...")

        # CAPA 2: Edge-TTS (Voz Neural Gratuita)
        try:
            asyncio.run(_generate_edge_tts(text, temp_file))
            if _play_audio(temp_file, disable_vad):
                return
        except Exception as e:
            logging.warning(f"⚠️ Edge-TTS falló ({e}). Usando Capa 3 (pyttsx3 Offline)...")

        # CAPA 3: Fallback Offline pyttsx3
        _speak_backup(text)
    finally:
        _speaking_active = False

def stop_speak() -> None:
    """Detiene la reproducción actual de voz de manera inmediata."""
    try:
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            logging.info("🔇 Voz de Jarvis interrumpida.")
    except Exception as e:
        logging.error(f"Error al detener la voz: {e}")

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

def speak(text: str, disable_vad: bool = False) -> None:
    """
    Sintetiza y reproduce el texto por voz de forma no bloqueante (asíncrona).
    Orden de prioridad: ElevenLabs -> Edge-TTS -> pyttsx3
    """
    # Evitar llamadas vacías
    if not text or not text.strip():
        return
        
    threading.Thread(target=_speak_thread, args=(text, disable_vad), daemon=True).start()
