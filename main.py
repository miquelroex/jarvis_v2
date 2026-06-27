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
from core.conversation_flow import should_stay_conversational, conversation_timeout


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
    from core.barge_in import consume_barge_in, capture_mode
    wait_while_speaking()
    # Si acabas de interrumpir a Jarvis (barge-in), captura ya, con pausa corta y
    # sin recalibrar, para no perder el inicio de tu frase.
    mode = capture_mode(consume_barge_in())
    _old_pause = recognizer.pause_threshold
    try:
        recognizer.pause_threshold = mode["pause_threshold"]
        audio = recognizer.listen(source, timeout=10, phrase_time_limit=30)
    finally:
        recognizer.pause_threshold = _old_pause

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

  # Registrar el último comando para el HUD Overlay flotante (best-effort).
  try:
    from core.hud_overlay import set_last_command
    set_last_command(transcript_for_ui or command_to_execute)
  except Exception:
    pass

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
    _agent_start = time.time()
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
            provider="openrouter",
            latency_ms=int((time.time() - _agent_start) * 1000)
        )
        raise

    logging.info(f"Agent responded: {content}")
    log_model_usage(
        tool_name="main_model",
        model_name=default_model,
        prompt=command_to_execute,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider="openrouter",
        latency_ms=int((time.time() - _agent_start) * 1000)
    )
    update_state("speaking", response=content)

  print("Jarvis:", content)
  speak(content)
  update_state("idle")

def _run_startup_healthcheck():
    """Ejecuta el healthcheck de arranque (resumen de estado: tools, servicios,
    claves, SQLite). Nunca debe abortar el arranque, por eso va en try/except."""
    try:
        from core.healthcheck import run_healthcheck, summarize_healthcheck, persist_healthcheck
        health_report = run_healthcheck()
        logging.info(f"[Healthcheck] {summarize_healthcheck(health_report)}")
        persist_healthcheck(health_report)
        if health_report.get("status") != "healthy":
            logging.warning(f"[Healthcheck] Estado de arranque no óptimo: {health_report.get('status')}")
    except Exception as e:
        logging.warning(f"[Healthcheck] No se pudo completar el healthcheck de arranque: {e}")

def _bootstrap_core():
    """Bootstrap secuencial: inicializa el agente central, arranca los servicios
    de segundo plano y ejecuta el healthcheck de arranque."""
    init_agent()
    from core.services import start_all_services
    start_all_services()
    _run_startup_healthcheck()

def _calibrate_microphone():
    """Calibra el ruido ambiental del micrófono una sola vez al inicio."""
    logging.info("🎤 Calibrando ruido de fondo del micrófono (1 segundo)...")
    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
        logging.info(f"✅ Calibración completada. Umbral de energía base: {recognizer.energy_threshold:.2f}")
    except Exception as e:
        logging.warning(f"⚠️ No se pudo realizar la calibración inicial de ruido: {e}")

def _handle_awake_startup() -> bool:
    """Arranque en modo AWAKE: abre el navegador, ejecuta la secuencia Suit Up y
    da el saludo de arranque dinámico. Devuelve True (navegador abierto)."""
    print("Abriendo http://localhost:5000 en tu navegador...")
    time.sleep(2)  # Dar tiempo a que Flask arranque
    webbrowser.open("http://localhost:5000")

    # La secuencia de arranque "Suit Up" ya NO se lanza aquí: se dispara cuando el
    # navegador se conecta al socket (gui.app handle_connect). Así se reproduce de
    # forma fiable en cada carga/recarga y se evita la carrera del arranque que
    # dejaba la animación colgada en STANDBY si la pestaña no estaba lista a tiempo.

    update_state("idle")
    # Saludo de arranque dinámico con telemetría
    from core.startup import generate_startup_greeting
    speak(generate_startup_greeting(), disable_vad=True)

    # Briefing matutino al arrancar (clima, git, recordatorios), si está activado.
    # Se entrega por voz; va detrás del saludo en la cola de voz (no se solapan).
    try:
        if os.getenv("JARVIS_MORNING_BRIEFING_ON_STARTUP", "false").lower() in ("true", "1", "yes"):
            from core.morning_briefing import deliver_briefing
            deliver_briefing(channel="voice")
    except Exception as e:
        logging.warning(f"[Main] Error al entregar el briefing de arranque: {e}")

    return True

def _handle_sleeping_startup() -> None:
    """Arranque en modo SLEEPING (vigilante): estado offline y aviso por consola."""
    time.sleep(2)
    update_state("offline")
    print("Jarvis iniciado en modo VIGILANTE (Dormido). Di 'despierta' para activar.")

class _LoopState:
    """Estado mutable del bucle de interacción principal."""
    def __init__(self):
        self.conversation_mode = False
        self.last_interaction_time = None
        self.system_status = "AWAKE" if "--awake" in sys.argv else "SLEEPING"
        self.browser_opened = False

def _handle_sleep_mode(state: "_LoopState", source) -> None:
    """Modo vigilante (dormido): escucha la palabra 'despierta' y reactiva Jarvis."""
    logging.info("💤 Jarvis is sleeping. Listening for 'despierta'...")
    from tools.voice import wait_while_speaking
    wait_while_speaking()
    audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
    transcript = recognizer.recognize_google(audio, language="es-ES").lower()
    logging.info(f"🗣 Heard in sleep: {transcript}")

    if "despierta" in transcript:
        logging.info("🌞 Waking up!")
        state.system_status = "AWAKE"
        if not state.browser_opened:
            print("Abriendo http://localhost:5000 en tu navegador...")
            webbrowser.open("http://localhost:5000")
            state.browser_opened = True
        update_state("idle")
        from core.startup import generate_wake_greeting
        speak(generate_wake_greeting(), disable_vad=True)

def _handle_exit_phrases(state: "_LoopState", command_to_execute: str) -> bool:
    """Gestiona las frases de reposo/salida (apágate, gracias, adiós...).

    Devuelve True si manejó una frase de salida (el bucle debe continuar).
    """
    lower_cmd = command_to_execute.lower()
    exit_words = ("apágate", "apagate", "vete a dormir", "desactívate",
                  "adiós", "adios", "gracias", "salir")
    if not any(w in lower_cmd for w in exit_words):
        return False

    sleep_words = ("apágate", "apagate", "vete a dormir", "desactívate")
    if any(w in lower_cmd for w in sleep_words):
        speak("Protocolo de reposo activado. Cerrando sistemas.")
        update_state("offline")
        state.system_status = "SLEEPING"
    else:
        if "gracias" in lower_cmd:
            speak("De nada, señor. Siempre a su servicio.")
        else:
            speak("Entendido. Saliendo del modo conversación.")
        update_state("idle")
    state.conversation_mode = False
    time.sleep(1)
    return True

def _handle_conversation_timeout(state: "_LoopState", reason: str) -> None:
    """Si en modo conversación se supera el timeout sin entrada válida, vuelve al
    modo de palabra de activación (wake word)."""
    if state.conversation_mode and time.time() - state.last_interaction_time > conversation_timeout(CONVERSATION_TIMEOUT):
        logging.info(f"⌛ {reason}. Returning to wake word mode.")
        state.conversation_mode = False
        clear_conversation_memory()
        update_state("idle")

# Main interaction loop
def write():
    state = _LoopState()

    # Adquirir lock de instancia única
    from core.instance_lock import acquire_instance_lock, release_instance_lock
    if not acquire_instance_lock():
        print("\n❌ Error: Ya hay una instancia de Jarvis en ejecución.")
        print("   Si crees que es un error, elimina logs/jarvis.lock manualmente.")
        sys.exit(1)

    try:
        # Bootstrap: agente central + servicios de segundo plano + healthcheck.
        _bootstrap_core()

        if state.system_status == "AWAKE":
            state.browser_opened = _handle_awake_startup()
        else:
            _handle_sleeping_startup()

        # Calibrar ruido ambiental una sola vez al inicio si es posible
        _calibrate_microphone()

        while True:
            try:
                with mic as source:
                    while True:
                        try:
                            command_to_execute = None
                            transcript_for_ui = None

                            if state.system_status == "SLEEPING":
                                _handle_sleep_mode(state, source)
                                continue

                            if not state.conversation_mode:
                                cmd, trans, needs_conversation = listen_for_wake_word(source)
                                if needs_conversation:
                                    speak("Sí señor?")
                                    state.conversation_mode = True
                                    state.last_interaction_time = time.time()
                                    update_state("listening", model="")
                                elif cmd:
                                    command_to_execute = cmd
                                    transcript_for_ui = trans
                            else:
                                update_state("listening", model="")
                                command_to_execute, transcript_for_ui = listen_for_next_command(source)

                            if command_to_execute:
                                if _handle_exit_phrases(state, command_to_execute):
                                    continue
                                process_command(command_to_execute, transcript_for_ui)
                                state.last_interaction_time = time.time()
                                # Modo Conversación Continua: seguir escuchando sin
                                # repetir la palabra clave tras cualquier comando.
                                if should_stay_conversational(True):
                                    state.conversation_mode = True
                                    update_state("listening", model="")

                        except sr.WaitTimeoutError:
                            logging.warning("⚠️ Timeout waiting for audio.")
                            _handle_conversation_timeout(state, "No input")

                        except sr.UnknownValueError:
                            logging.warning("⚠️ Could not understand audio.")
                            _handle_conversation_timeout(state, "Noise but no valid words")

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