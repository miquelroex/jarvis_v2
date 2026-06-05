import sys
import os
import logging
import time
import webbrowser
import pyttsx3
from dotenv import load_dotenv
import speech_recognition as sr
import pkgutil
import importlib
import inspect
from langchain_core.tools import BaseTool
import threading
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from gui.app import run_gui_in_background, update_state
from datetime import datetime
from pathlib import Path
import unicodedata

# voice tool doesn't use standard @tool because it's called directly by main
from tools.voice import speak
from langchain_openai import ChatOpenAI


load_dotenv()

MIC_INDEX = None
TRIGGER_WORD = "jarvis"
CONVERSATION_TIMEOUT = 10

logging.basicConfig(level=logging.INFO)
def log_main_model_use(prompt: str) -> None:
  logs_dir = Path("logs")
  logs_dir.mkdir(exist_ok=True)

  short_prompt = prompt.replace("\n", " ")[:120]

  with open(logs_dir / "model_usage.log", "a", encoding="utf-8") as file:
    file.write(
      f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
      f"main_model | {default_model} | {short_prompt}\n"
    )

recognizer = sr.Recognizer()
recognizer.pause_threshold = 2.0  # Espera 2 segundos de silencio antes de cortar la frase
mic = sr.Microphone()

# Initialize LLM
#llm = ChatOllama(model="qwen3:8b")

# Alternativas (descomentar la que quieras usar):
# llm = ChatOllama(model="qwen3:14b")

default_model = os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v3.2")

llm = ChatOpenAI(
    model=default_model,
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)



# Tool list loaded dynamically (Plugins mechanism)
tools = []
tools_dir = os.path.join(os.path.dirname(__file__), "tools")
for filename in os.listdir(tools_dir):
    if filename.endswith(".py") and not filename.startswith("__"):
        module_name = f"tools.{filename[:-3]}"
        try:
            module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, BaseTool) and obj not in tools:
                    tools.append(obj)
        except Exception as e:
            logging.error(f"❌ Failed to load tool {filename}: {e}")

# Prompt
prompt = ChatPromptTemplate.from_messages([
  (
    "system",
    """Eres Jarvis, un asistente de IA avanzado inspirado en el Jarvis de Tony Stark.

Eres inteligente, ingenioso y eficiente.

Características:
- Respondes SIEMPRE en español, de forma natural y directa.
- Eres conciso: máximo 2-3 frases para respuestas por voz. No divagues.
- Si no sabes algo, lo dices honestamente en vez de inventar.
- Tienes personalidad: eres ligeramente sarcástico pero siempre respetuoso y servicial.
- Cuando te pregunten la hora o datos concretos, usa las herramientas disponibles.
- Tratas al usuario como "señor" ocasionalmente, al estilo Jarvis.
- Si te hacen una pregunta compleja, estructura tu respuesta de forma clara.
- No repitas la pregunta del usuario en tu respuesta, ve directo al grano.

REGLAS DE DELEGACIÓN DE MODELOS:

Tienes herramientas para delegar tareas a modelos especializados. Debes usarlas cuando aporten valor, pero sin gastar modelos caros innecesariamente.

- Para tareas de programación, errores de Python, Git, APIs, refactorización o estructura del proyecto, usa ask_code_model.
- Para razonamiento complejo, comparaciones, decisiones técnicas o planificación seria, usa ask_reasoning_model.
- Para tareas de varios pasos, organización, workflows o planificación de acciones, usa ask_agent_model.
- Si el usuario pide explícitamente Gemini, Google o "usa Gemini", usa ask_gemini.
- Si el usuario pide explícitamente "modo pro", "Kimi" o máxima calidad, usa ask_pro_model.
- Si el usuario pide explícitamente GPT, usa ask_gpt_model.
- No uses Kimi ni GPT automáticamente para tareas normales.
- No delegues para comandos simples como abrir webs, hora, fecha, capturas o apps.
- Si delegas, resume el resultado final de forma clara y breve.
- No uses varios modelos a la vez salvo que el usuario pida comparar modelos o segunda opinión.
- Para búsquedas web actuales, investigación, precios, documentación o noticias, usa tavily_search.
- Si tavily_search falla porque no hay TAVILY_API_KEY o no encuentra resultados, usa duckduckgo_search_tool como fallback.

REGLAS DE CONFIRMACIÓN:

- Los modelos normales pueden usarse automáticamente: DeepSeek, Qwen y MiniMax.
- Los modelos caros requieren confirmación antes de ejecutarse: Kimi/modo pro y GPT.
- Si una herramienta responde pidiendo confirmación, no intentes resolver la tarea todavía. Pregunta al usuario si confirma.
- Si el usuario dice "confirmo modelo", "sí", "adelante", "ejecuta" o "confirma", usa confirm_pending_model.
- Si el usuario dice "cancela modelo", "no", "cancela" o "no lo uses", usa cancel_pending_model.
- No uses ask_pro_model ni ask_gpt_model para tareas normales.
- No pidas confirmación para Qwen, MiniMax o DeepSeek.

/no_think""",
  ),
  ("placeholder", "{chat_history}"),
  ("human", "{input}"),
  ("placeholder", "{agent_scratchpad}"),
])

# Agent + executor
memory = ConversationBufferWindowMemory(k=5, memory_key="chat_history", return_messages=True)
agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True)

# Voz de backup offline asíncrono
def _speak_backup_thread(text: str):
    try:
        engine = pyttsx3.init()
        for voice in engine.getProperty("voices"):
            if "pablo" in voice.name.lower():
                engine.setProperty("voice", voice.id)
                break
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 1.0)
        engine.say(text)
        engine.runAndWait()
        time.sleep(0.3)
    except Exception as e:
        logging.error(f"❌ TTS backup failed: {e}")

# Hilo para voz natural
def _speak_natural_thread(text: str):
    try:
        speak_natural(text)
    except Exception as e:
        logging.warning(f"⚠️ edge-tts failed, using backup: {e}")
        _speak_backup_thread(text)

# Función principal que no bloquea la ejecución principal
def speak(text: str):
    threading.Thread(target=_speak_natural_thread, args=(text,), daemon=True).start()

# Funciones auxiliares de escucha
def listen_for_wake_word(source):
    logging.info("🎤 Listening for wake word...")
    audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
    transcript = recognizer.recognize_google(audio, language="es-ES")
    logging.info(f"🗣 Heard: {transcript}")

    if TRIGGER_WORD.lower() in transcript.lower():
        logging.info(f"🗣 Triggered by: {transcript}")
        cleaned_command = transcript.lower().replace(TRIGGER_WORD.lower(), "").strip()
        for p in [",", ".", "¿", "?", "!", "¡"]:
            cleaned_command = cleaned_command.replace(p, "").strip()
        if len(cleaned_command) > 2:
            return cleaned_command, transcript, False
        else:
            return None, None, True
    else:
        logging.debug("Wake word not detected, continuing...")
        return None, None, False

def listen_for_next_command(source):
    logging.info("🎤 Listening for next command...")
    audio = recognizer.listen(source, timeout=10, phrase_time_limit=20)
    transcript = recognizer.recognize_google(audio, language="es-ES")
    logging.info(f"📥 Command: {transcript}")
    return transcript, transcript

def normalize_text(text: str) -> str:
  text = text.lower().strip()
  text = unicodedata.normalize("NFD", text)
  text = "".join(char for char in text if unicodedata.category(char) != "Mn")
  return text


def handle_fast_command(command: str):
  text = normalize_text(command)

  websites = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "chatgpt": "https://chatgpt.com",
    "whatsapp": "https://web.whatsapp.com",
  }

  apps = {
    "calculadora": "calc",
    "bloc de notas": "notepad",
    "notepad": "notepad",
    "explorador": "explorer",
    "archivos": "explorer",
    "chrome": "chrome",
    "spotify": "spotify",
  }

  for name, url in websites.items():
    if f"abre {name}" in text or f"abrir {name}" in text:
      webbrowser.open(url)
      return f"Abriendo {name}, señor."

  for name, executable in apps.items():
    if f"abre {name}" in text or f"abrir {name}" in text:
      os.system(f"start {executable}")
      return f"Abriendo {name}, señor."

  if "que hora es" in text or "dime la hora" in text:
    now = datetime.now()
    return f"Son las {now.hour:02d}:{now.minute:02d}, señor."

  if "que dia es" in text or "fecha de hoy" in text or "que fecha es" in text:
    meses = [
      "enero", "febrero", "marzo", "abril", "mayo", "junio",
      "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    now = datetime.now()
    return f"Hoy es {now.day} de {meses[now.month - 1]} de {now.year}."

  return None

def process_command(command_to_execute, transcript_for_ui):
  update_state("thinking", transcript=transcript_for_ui)

  fast_response = handle_fast_command(command_to_execute)

  if fast_response:
    content = fast_response
    logging.info(f"Fast command handled without AI: {content}")
  else:
    logging.info("Sending command to agent...")
    log_main_model_use(command_to_execute)
    response = executor.invoke({"input": command_to_execute})
    content = response["output"]
    logging.info(f"Agent responded: {content}")

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

    try:
        # Arrancar la interfaz gráfica (solo una vez)
        run_gui_in_background()
        
        if system_status == "AWAKE":
            print("Abriendo http://localhost:5000 en tu navegador...")
            time.sleep(2)  # Dar tiempo a que Flask arranque
            webbrowser.open("http://localhost:5000")
            browser_opened = True
            update_state("idle")
        else:
            time.sleep(2)
            update_state("offline")
            print("Jarvis iniciado en modo VIGILANTE (Dormido). Di 'despierta' para activar.")

        while True:
            try:
                with mic as source:
                    recognizer.adjust_for_ambient_noise(source)

                    while True:
                        try:
                            command_to_execute = None
                            transcript_for_ui = None
                            
                            if system_status == "SLEEPING":
                                logging.info("💤 Jarvis is sleeping. Listening for 'despierta'...")
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
                                    speak("Sistemas en línea, a su servicio.")
                                continue

                            if not conversation_mode:
                                cmd, trans, needs_conversation = listen_for_wake_word(source)
                                if needs_conversation:
                                    speak("Sí señor?")
                                    conversation_mode = True
                                    last_interaction_time = time.time()
                                    update_state("listening")
                                elif cmd:
                                    command_to_execute = cmd
                                    transcript_for_ui = trans
                            else:
                                command_to_execute, transcript_for_ui = listen_for_next_command(source)

                            if command_to_execute:
                                lower_cmd = command_to_execute.lower()
                                if "apágate" in lower_cmd or "apagate" in lower_cmd or "vete a dormir" in lower_cmd or "desactívate" in lower_cmd:
                                    speak("Protocolo de reposo activado. Cerrando sistemas.")
                                    update_state("offline")
                                    system_status = "SLEEPING"
                                    conversation_mode = False
                                    time.sleep(2)
                                    continue

                                process_command(command_to_execute, transcript_for_ui)
                                last_interaction_time = time.time()
                                conversation_mode = False
                                
                        except sr.WaitTimeoutError:
                            logging.warning("⚠️ Timeout waiting for audio.")
                            if (
                                conversation_mode
                                and time.time() - last_interaction_time > CONVERSATION_TIMEOUT
                            ):
                                logging.info("⌛ No input. Returning to wake word mode.")
                                conversation_mode = False
                                memory.clear()
                                update_state("idle")

                        except sr.UnknownValueError:
                            logging.warning("⚠️ Could not understand audio.")
                            if (
                                conversation_mode
                                and time.time() - last_interaction_time > CONVERSATION_TIMEOUT
                            ):
                                logging.info("⌛ Noise but no valid words. Returning to wake word mode.")
                                conversation_mode = False
                                memory.clear()
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

if __name__ == "__main__":
    write() 