import os
import logging
import threading
import time
import telebot
from tools.screenshot import take_screenshot
from tools.terminal import execute_cmd, is_command_safe
from core.router import smart_route
from core.agent_manager import get_executor
from core.model_logging import log_model_usage
from gui.app import update_state

bot = None
bot_thread = None
stop_event = threading.Event()

def send_mfa_request(mfa_type: str, details: dict) -> None:
    """
    Inicia el envío de la solicitud MFA en un hilo secundario para evitar bloquear el flujo principal.
    """
    threading.Thread(
        target=_send_mfa_request_sync,
        args=(mfa_type, details),
        daemon=True
    ).start()

def _send_mfa_request_sync(mfa_type: str, details: dict) -> None:
    global bot
    if not bot:
        logging.info("[Telegram] Bot not initialized. Skipping MFA push notification.")
        return
        
    authorized_user = os.getenv("TELEGRAM_USER_ID")
    if not authorized_user or not authorized_user.strip():
        logging.warning("[Telegram] Cannot send MFA: TELEGRAM_USER_ID not configured.")
        return
        
    chat_id = authorized_user.strip()
    
    try:
        import html
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup()
        
        if mfa_type == "command":
            command = details.get("command", "")
            text = (
                "🔒 <b>MFA: Confirmación de Comando</b>\n\n"
                "Se ha solicitado la ejecución de un comando en la terminal:\n"
                f"<pre><code class=\"language-bash\">{html.escape(command)}</code></pre>\n"
                "¿Desea autorizar esta acción?"
            )
            markup.add(
                InlineKeyboardButton("✅ Aprobar", callback_data="mfa_approve_command"),
                InlineKeyboardButton("❌ Cancelar", callback_data="mfa_cancel_command")
            )
        elif mfa_type == "model":
            model_name = details.get("model_name", "")
            prompt = details.get("prompt", "")
            truncated_prompt = prompt[:200] + "..." if len(prompt) > 200 else prompt
            text = (
                "💰 <b>MFA: Uso de Modelo Costoso</b>\n\n"
                f"Se ha solicitado usar el modelo:\n<code>{html.escape(model_name)}</code>\n\n"
                f"<b>Prompt</b>:\n<i>{html.escape(truncated_prompt)}</i>\n\n"
                "¿Desea autorizar esta acción?"
            )
            markup.add(
                InlineKeyboardButton("✅ Aprobar", callback_data="mfa_approve_model"),
                InlineKeyboardButton("❌ Cancelar", callback_data="mfa_cancel_model")
            )
        else:
            logging.error(f"[Telegram] Unknown MFA type: {mfa_type}")
            return

        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        logging.info(f"[Telegram] MFA prompt sent for {mfa_type}.")
    except Exception as e:
        logging.error(f"[Telegram] Error sending MFA push notification: {e}")

def start_telegram_bot():
    global bot, bot_thread
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    authorized_user = os.getenv("TELEGRAM_USER_ID")
    
    if not token or not token.strip():
        logging.info("[Telegram] Bot token not found or empty in .env. Remote control bot disabled.")
        return
        
    if bot_thread is not None and bot_thread.is_alive():
        logging.info("[Telegram] Bot already running.")
        return
        
    logging.info("[Telegram] Initializing remote control bot...")
    stop_event.clear()
    
    try:
        # Usar ThreadedSender para evitar bloqueos
        bot = telebot.TeleBot(token, threaded=True)
    except Exception as e:
        logging.error(f"[Telegram] Failed to initialize bot: {e}")
        return
    
    def is_authorized(message):
        user_id = str(message.from_user.id)
        if not authorized_user or not authorized_user.strip():
            logging.warning(f"[Telegram] Blocked request from {user_id}: TELEGRAM_USER_ID is not configured in .env.")
            bot.reply_to(message, f"❌ Bot no autorizado. Configura tu `TELEGRAM_USER_ID` en el archivo `.env` de Jarvis. Tu ID de Telegram actual es: `{user_id}`", parse_mode="Markdown")
            return False
            
        if user_id != authorized_user.strip():
            logging.warning(f"[Telegram] Security Alert: Unauthorized access attempt from user ID {user_id} ({message.from_user.username or 'unknown'})")
            bot.reply_to(message, "❌ No tienes autorización para controlar este sistema Jarvis.")
            return False
            
        return True

    # Comandos
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        if not is_authorized(message):
            return
        bot.reply_to(message, "🤖 ¡Hola señor! Soy Jarvis, su bot de control remoto. Listo para recibir comandos locales y de lenguaje natural.")

    @bot.message_handler(commands=['help'])
    def handle_help(message):
        if not is_authorized(message):
            return
            
        help_text = (
            "🤖 *Comandos de Control de Jarvis*:\n\n"
            "📱 `/status` - Obtener carga de CPU, RAM y estado del sistema\n"
            "📸 `/screenshot` - Capturar el escritorio actual\n"
            "🔊 `/say <texto>` - Reproducir voz localmente por los altavoces\n"
            "💻 `/cmd <comando>` - Ejecutar comando seguro en la terminal\n"
            "🔑 `/trust <mac> <nombre>` - Confiar en un dispositivo de la red\n\n"
            "También puedes enviar cualquier instrucción en lenguaje natural y Jarvis la procesará con IA."
        )
        bot.reply_to(message, help_text, parse_mode="Markdown")

    @bot.message_handler(commands=['status'])
    def handle_status(message):
        if not is_authorized(message):
            return
            
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            uptime_sec = time.time() - psutil.boot_time()
            uptime_h = int(uptime_sec // 3600)
            uptime_m = int((uptime_sec % 3600) // 60)
            
            status_text = (
                f"🖥 *Estado del Servidor Jarvis*:\n\n"
                f"🔋 *CPU*: {cpu}%\n"
                f"🧠 *RAM*: {ram}%\n"
                f"⏱ *Uptime*: {uptime_h}h {uptime_m}m\n"
                f"🔊 *VAD Habilitado*: {os.getenv('JARVIS_VAD_ENABLED', 'True')}\n"
                f"🔒 *Modo Seguro*: {os.getenv('JARVIS_SAFE_MODE', 'True')}"
            )
        except Exception as e:
            status_text = f"🖥 *Jarvis Activo*\n\n(Error al obtener telemetría: {str(e)})"
            
        bot.reply_to(message, status_text, parse_mode="Markdown")

    @bot.message_handler(commands=['screenshot'])
    def handle_screenshot(message):
        if not is_authorized(message):
            return
            
        try:
            bot.send_chat_action(message.chat.id, 'upload_photo')
            take_screenshot()
            screenshot_path = "logs/latest_screenshot.png"
            if os.path.exists(screenshot_path):
                with open(screenshot_path, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption="🖥 Captura de pantalla actual.")
            else:
                bot.reply_to(message, "❌ No se pudo encontrar el archivo de captura en logs.")
        except Exception as e:
            bot.reply_to(message, f"❌ Error al capturar pantalla: {str(e)}")

    @bot.message_handler(commands=['say'])
    def handle_say(message):
        if not is_authorized(message):
            return
            
        text = message.text.replace("/say", "").strip()
        if not text:
            bot.reply_to(message, "Por favor, escribe lo que quieres decir. Ejemplo: `/say Hola señor`", parse_mode="Markdown")
            return
            
        from tools.voice import speak
        speak(text, disable_vad=True)
        bot.reply_to(message, f"🔊 Reproduciendo localmente: '{text}'")

    @bot.message_handler(commands=['cmd'])
    def handle_cmd(message):
        if not is_authorized(message):
            return
            
        cmd_text = message.text.replace("/cmd", "").strip()
        if not cmd_text:
            bot.reply_to(message, "Por favor, escribe el comando a ejecutar. Ejemplo: `/cmd git status`", parse_mode="Markdown")
            return
            
        if not is_command_safe(cmd_text):
            bot.reply_to(message, f"❌ Comando '{cmd_text}' bloqueado por políticas de seguridad de Jarvis.")
            return
            
        bot.send_chat_action(message.chat.id, 'typing')
        res = execute_cmd(cmd_text)
        bot.reply_to(message, f"```\n{res}\n```", parse_mode="Markdown")

    @bot.message_handler(commands=['trust'])
    def handle_trust(message):
        if not is_authorized(message):
            return
            
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Por favor, especifica la MAC y el nombre. Ejemplo: `/trust aa:bb:cc:dd:ee:ff Teléfono`", parse_mode="Markdown")
            return
            
        mac = parts[1].strip().lower().replace("-", ":")
        name = parts[2].strip()
        
        # Validar MAC
        if len(mac) != 17 or mac.count(":") != 5:
            bot.reply_to(message, "❌ Dirección MAC inválida. Debe tener formato `xx:xx:xx:xx:xx:xx`.")
            return
            
        try:
            from core.network_sentinel import trust_device
            trust_device(mac, name)
            bot.reply_to(message, f"✅ Dispositivo `{mac}` registrado con éxito como *{name}*.", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"❌ Error al registrar el dispositivo: {str(e)}")

    @bot.callback_query_handler(func=lambda call: True)
    def handle_mfa_callback(call):
        user_id = str(call.from_user.id)
        if not authorized_user or not authorized_user.strip():
            try:
                bot.answer_callback_query(call.id, "❌ Bot no configurado (falta USER ID).", show_alert=True)
            except Exception:
                pass
            return
            
        if user_id != authorized_user.strip():
            logging.warning(f"[Telegram] Security Alert: Unauthorized callback attempt from user ID {user_id} ({call.from_user.username or 'unknown'})")
            try:
                bot.answer_callback_query(call.id, "❌ No tienes autorización para confirmar esta acción.", show_alert=True)
            except Exception:
                pass
            return

        if call.data.startswith("mfa_approve_"):
            try:
                bot.answer_callback_query(call.id, "⚡ Procesando aprobación...")
            except Exception:
                pass
            
            # Editar mensaje original con una frase limpia en Markdown
            action_type = "Comando" if "command" in call.data else "Modelo"
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"⏳ *MFA: {action_type} aprobado. Procesando ejecución...*",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            
            from tools.model_delegate import confirm_pending_model
            try:
                result = confirm_pending_model.invoke("adelante")
                if len(result) > 3000:
                    result = result[:3000] + "\n...(salida truncada)..."
                
                import html
                final_text = (
                    f"✅ <b>MFA: {action_type} Aprobado</b>\n\n"
                    f"<b>Resultado de la ejecución</b>:\n<pre>{html.escape(result)}</pre>"
                )
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=final_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                import html
                try:
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=f"❌ <b>Error al procesar la aprobación</b>:\n{html.escape(str(e))}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                
        elif call.data.startswith("mfa_cancel_"):
            try:
                bot.answer_callback_query(call.id, "❌ Cancelando acción...")
            except Exception:
                pass
            
            from tools.model_delegate import cancel_pending_model
            try:
                result = cancel_pending_model.invoke("cancela")
                action_type = "Comando" if "command" in call.data else "Modelo"
                import html
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"❌ <b>MFA: {action_type} Cancelado</b>\n\n<i>{html.escape(result)}</i>",
                    parse_mode="HTML"
                )
            except Exception as e:
                import html
                try:
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=f"❌ <b>Error al procesar la cancelación</b>:\n{html.escape(str(e))}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

    @bot.message_handler(func=lambda msg: True)
    def handle_natural_language(message):
        if not is_authorized(message):
            return
            
        text = message.text.strip()
        if not text:
            return
            
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Sincronizar estado en la GUI
        update_state("thinking", transcript=f"[Telegram] {text}", model="")
        
        try:
            # 1. Intentar enrutamiento rápido o síncrono
            route_result = smart_route(text)
            if route_result:
                content = route_result["content"]
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
            else:
                # 2. Delegar al agente de LangChain
                default_model = os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v4-pro")
                log_model_usage("main_model", default_model, text)
                response = get_executor().invoke({"input": text})
                content = response["output"]
                model_display = default_model
                
            update_state("speaking", response=content, model=model_display)
            bot.reply_to(message, content)
            update_state("idle")
        except Exception as e:
            update_state("idle")
            bot.reply_to(message, f"❌ Error de procesamiento: {str(e)}")

    def run_polling():
        logging.info("[Telegram] Bot polling thread started.")
        while not stop_event.is_set():
            try:
                bot.infinity_polling(timeout=20, long_polling_timeout=10)
            except Exception as ex:
                if stop_event.is_set():
                    break
                logging.error(f"[Telegram] Connection error in polling, reconnecting in 5s: {ex}")
                stop_event.wait(timeout=5)

    bot_thread = threading.Thread(target=run_polling, name="TelegramBotThread", daemon=True)
    bot_thread.start()

def stop_telegram_bot():
    """Detiene el bot de Telegram de forma limpia."""
    global bot
    logging.info("[Telegram] Deteniendo bot...")
    stop_event.set()
    if bot:
        try:
            bot.stop_polling()
            logging.info("[Telegram] Bot polling stopped.")
        except Exception as e:
            logging.error(f"[Telegram] Error stopping bot: {e}")
