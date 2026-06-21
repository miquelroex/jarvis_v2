import sys
import os
import logging
import time
import webbrowser

from dotenv import load_dotenv
import speech_recognition as sr
import threading
from gui.app import update_state
from datetime import datetime
from pathlib import Path

# voice tool doesn't use standard @tool because it's called directly by main
from tools.voice import speak
from core.router import smart_route
from core.llm_factory import get_llm
from core.model_logging import log_model_usage
from core.agent_manager import get_executor, init_agent, clear_conversation_memory


load_dotenv()

MIC_INDEX = None
TRIGGER_WORD = "jarvis"
CONVERSATION_TIMEOUT = 10

logging.basicConfig(level=logging.INFO)
recognizer = sr.Recognizer()
# Configuraciones de reconocimiento de voz (ASR / STT)
recognizer.pause_threshold = float(os.getenv("JARVIS_ASR_PAUSE_THRESHOLD", "0.8"))
recognizer.dynamic_energy_threshold = os.getenv("JARVIS_ASR_DYNAMIC_THRESHOLD", "True").lower() == "true"
recognizer.energy_threshold = float(os.getenv("JARVIS_ASR_ENERGY_THRESHOLD", "300.0"))
mic = sr.Microphone()

# Initialize LLM
default_model = os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v4-pro")


# Funciones auxiliares de escucha
def _clean_trigger_word(text):
    """Elimina la wake word y puntuación del texto transcrito."""
    cleaned = text.lower().replace(TRIGGER_WORD.lower(), "").strip()
    for p in [",", ".", "¿", "?", "!", "¡"]:
        cleaned = cleaned.replace(p, "").strip()
    return cleaned

def listen_for_wake_word(source):
    logging.info("🎤 Listening for wake word...")
    from tools.voice import wait_while_speaking
    wait_while_speaking()
    audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
    # Wake word detection siempre usa Google (rápido y ligero)
    transcript = recognizer.recognize_google(audio, language="es-ES")
    logging.info(f"🗣 Heard: {transcript}")

    if TRIGGER_WORD.lower() in transcript.lower():
        logging.info(f"🗣 Triggered by: {transcript}")
        cleaned_command = _clean_trigger_word(transcript)
        if len(cleaned_command) > 2:
            # Re-transcribir con Whisper para mayor precisión del comando
            stt_engine = os.getenv("JARVIS_STT_ENGINE", "whisper").lower()
            if stt_engine == "whisper":
                try:
                    from core.whisper_stt import transcribe_audio
                    whisper_text = transcribe_audio(audio)
                    whisper_cmd = _clean_trigger_word(whisper_text)
                    if len(whisper_cmd) > 2:
                        return whisper_cmd, whisper_text, False
                    logging.warning("⚠️ Whisper inline transcription too short, using Google.")
                except Exception as e:
                    logging.warning(f"⚠️ Whisper inline re-transcription failed: {e}")
            return cleaned_command, transcript, False
        else:
            return None, None, True
    else:
        logging.debug("Wake word not detected, continuing...")
        return None, None, False

def listen_for_next_command(source):
    logging.info("🎤 Listening for next command...")
    from tools.voice import wait_while_speaking
    wait_while_speaking()
    audio = recognizer.listen(source, timeout=10, phrase_time_limit=30)

    stt_engine = os.getenv("JARVIS_STT_ENGINE", "whisper").lower()
    if stt_engine == "whisper":
        from core.whisper_stt import transcribe_audio
        transcript = transcribe_audio(audio)
    else:
        transcript = recognizer.recognize_google(audio, language="es-ES")

    logging.info(f"📥 Command: {transcript}")
    return transcript, transcript

def process_command(command_to_execute, transcript_for_ui):
  update_state("thinking", transcript=transcript_for_ui, model="")

  route_result = smart_route(command_to_execute)

  if route_result:
    content = route_result["content"]
    logging.info(f"Route handled directly: {route_result['type']} -> {content}")
    # Determinar qué modelo/procesador se usó
    route_type = route_result.get("type", "")
    if route_type == "fast_command":
        model_display = "Comando Local"
    elif "gemini" in route_type:
        model_display = os.getenv("JARVIS_MODEL_GEMINI", "gemini-3.5-flash")
    elif "pro" in route_type:
        model_display = os.getenv("JARVIS_MODEL_PRO", "moonshotai/kimi-k2.6")
    elif "gpt" in route_type:
        model_display = os.getenv("JARVIS_MODEL_GPT", "openai/gpt-5.4-mini")
    elif "code" in route_type:
        model_display = os.getenv("JARVIS_MODEL_CODE", "qwen/qwen3-coder")
    elif "reasoning" in route_type:
        model_display = os.getenv("JARVIS_MODEL_THINK", "qwen/qwen3.7-plus")
    else:
        model_display = "Procesador Interno"
    update_state("speaking", response=content, model=model_display)
  else:
    logging.info("Sending command to agent...")
    prompt_tokens = 0
    completion_tokens = 0
    from langchain_community.callbacks import get_openai_callback
    try:
        with get_openai_callback() as cb:
            response = get_executor().invoke({"input": command_to_execute})
            prompt_tokens = cb.prompt_tokens
            completion_tokens = cb.completion_tokens
        content = response["output"]
    except Exception as e:
        log_model_usage(
            tool_name="main_model",
            model_name=default_model,
            prompt=command_to_execute,
            prompt_tokens=0,
            completion_tokens=0,
            provider="openrouter"
        )
        raise
        
    logging.info(f"Agent responded: {content}")
    log_model_usage(
        tool_name="main_model",
        model_name=default_model,
        prompt=command_to_execute,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider="openrouter"
    )
    update_state("speaking", response=content)

  print("Jarvis:", content)
  speak(content)
  update_state("idle")

# Main interaction loop
def write():
    conversation_mode = False
    last_interaction_time = None
    system_status = "AWAKE" if "--awake" in sys.argv else "SLEEPING"
    browser_opened = False

    # Adquirir lock de instancia única
    from core.instance_lock import acquire_instance_lock, release_instance_lock
    if not acquire_instance_lock():
        print("\n❌ Error: Ya hay una instancia de Jarvis en ejecución.")
        print("   Si crees que es un error, elimina logs/jarvis.lock manualmente.")
        sys.exit(1)

    try:
        # Inicializar el agente central
        init_agent()
        # Arrancar servicios de segundo plano de forma centralizada
        from core.services import start_all_services
        start_all_services()

        # Healthcheck de arranque: resumen de estado (tools, servicios, claves, SQLite).
        # Nunca debe abortar el arranque, por eso va en try/except.
        try:
            from core.healthcheck import run_healthcheck, summarize_healthcheck, persist_healthcheck
            health_report = run_healthcheck()
            logging.info(f"[Healthcheck] {summarize_healthcheck(health_report)}")
            persist_healthcheck(health_report)
            if health_report.get("status") != "healthy":
                logging.warning(f"[Healthcheck] Estado de arranque no óptimo: {health_report.get('status')}")
        except Exception as e:
            logging.warning(f"[Healthcheck] No se pudo completar el healthcheck de arranque: {e}")

        if system_status == "AWAKE":
            print("Abriendo http://localhost:5000 en tu navegador...")
            time.sleep(2)  # Dar tiempo a que Flask arranque
            webbrowser.open("http://localhost:5000")
            browser_opened = True

            # Secuencia de arranque "Suit Up" con telemetría animada
            skip_suitup = "--skip-suitup" in sys.argv or os.getenv("JARVIS_SKIP_SUITUP", "false").lower() in ("true", "1", "yes")
            if not skip_suitup:
                try:
                    from gui.app import socketio as gui_socketio
                    from core.suit_up import run_suit_up_sequence
                    time.sleep(1.5)  # Dar tiempo extra al navegador para conectar al socket
                    run_suit_up_sequence(gui_socketio, delay_multiplier=1.0)
                except Exception as e:
                    logging.warning(f"[Main] Error en secuencia Suit Up, continuando: {e}")

            update_state("idle")
            # Saludo de arranque dinámico con telemetría
            from core.startup import generate_startup_greeting
            speak(generate_startup_greeting(), disable_vad=True)
        else:
            time.sleep(2)
            update_state("offline")
            print("Jarvis iniciado en modo VIGILANTE (Dormido). Di 'despierta' para activar.")

        # Calibrar ruido ambiental una sola vez al inicio si es posible
        logging.info("🎤 Calibrando ruido de fondo del micrófono (1 segundo)...")
        try:
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=1.0)
            logging.info(f"✅ Calibración completada. Umbral de energía base: {recognizer.energy_threshold:.2f}")
        except Exception as e:
            logging.warning(f"⚠️ No se pudo realizar la calibración inicial de ruido: {e}")

        while True:
            try:
                with mic as source:
                    while True:
                        try:
                            command_to_execute = None
                            transcript_for_ui = None
                            
                            if system_status == "SLEEPING":
                                logging.info("💤 Jarvis is sleeping. Listening for 'despierta'...")
                                from tools.voice import wait_while_speaking
                                wait_while_speaking()
                                audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
                                transcript = recognizer.recognize_google(audio, language="es-ES").lower()
                                logging.info(f"🗣 Heard in sleep: {transcript}")
                                
                                if "despierta" in transcript:
                                    logging.info("🌞 Waking up!")
                                    system_status = "AWAKE"
                                    if not browser_opened:
                                        print("Abriendo http://localhost:5000 en tu navegador...")
                                        webbrowser.open("http://localhost:5000")
                                        browser_opened = True
                                    update_state("idle")
                                    from core.startup import generate_wake_greeting
                                    speak(generate_wake_greeting(), disable_vad=True)
                                continue

                            if not conversation_mode:
                                cmd, trans, needs_conversation = listen_for_wake_word(source)
                                if needs_conversation:
                                    speak("Sí señor?")
                                    conversation_mode = True
                                    last_interaction_time = time.time()
                                    update_state("listening", model="")
                                elif cmd:
                                    command_to_execute = cmd
                                    transcript_for_ui = trans
                            else:
                                update_state("listening", model="")
                                command_to_execute, transcript_for_ui = listen_for_next_command(source)

                            if command_to_execute:
                                lower_cmd = command_to_execute.lower()
                                if "apágate" in lower_cmd or "apagate" in lower_cmd or "vete a dormir" in lower_cmd or "desactívate" in lower_cmd or "adiós" in lower_cmd or "adios" in lower_cmd or "gracias" in lower_cmd or "salir" in lower_cmd:
                                    if "apágate" in lower_cmd or "apagate" in lower_cmd or "vete a dormir" in lower_cmd or "desactívate" in lower_cmd:
                                        speak("Protocolo de reposo activado. Cerrando sistemas.")
                                        update_state("offline")
                                        system_status = "SLEEPING"
                                    else:
                                        if "gracias" in lower_cmd:
                                            speak("De nada, señor. Siempre a su servicio.")
                                        else:
                                            speak("Entendido. Saliendo del modo conversación.")
                                        update_state("idle")
                                    conversation_mode = False
                                    time.sleep(1)
                                    continue

                                process_command(command_to_execute, transcript_for_ui)
                                last_interaction_time = time.time()
                                if not conversation_mode:
                                    conversation_mode = False
                                
                        except sr.WaitTimeoutError:
                            logging.warning("⚠️ Timeout waiting for audio.")
                            if (
                                conversation_mode
                                and time.time() - last_interaction_time > CONVERSATION_TIMEOUT
                            ):
                                logging.info("⌛ No input. Returning to wake word mode.")
                                conversation_mode = False
                                clear_conversation_memory()
                                update_state("idle")

                        except sr.UnknownValueError:
                            logging.warning("⚠️ Could not understand audio.")
                            if (
                                conversation_mode
                                and time.time() - last_interaction_time > CONVERSATION_TIMEOUT
                            ):
                                logging.info("⌛ Noise but no valid words. Returning to wake word mode.")
                                conversation_mode = False
                                clear_conversation_memory()
                                update_state("idle")

                        except Exception as e:
                            logging.error(f"❌ Error: {e}")
                            time.sleep(1)
                            # Rompemos el bucle interno para que vuelva a inicializar el microfono
                            break

            except Exception as e:
                logging.error(f"❌ Fallo al inicializar el micrófono: {e}")
                time.sleep(2)

    except Exception as e:
        logging.critical(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logging.info("[Main] Finalizando ejecución y deteniendo servicios en segundo plano...")
        try:
            from core.services import stop_all_services
            stop_all_services()
        except Exception as se:
            logging.error(f"❌ Error al detener servicios de segundo plano: {se}")
        try:
            release_instance_lock()
        except Exception as le:
            logging.error(f"❌ Error al liberar lock de instancia: {le}")

if __name__ == "__main__":
    write() 