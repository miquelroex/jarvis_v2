import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import threading

# Asegurar import de telegram_bot
from core.telegram_bot import start_telegram_bot

class MockUser:
    def __init__(self, user_id, username="miquel"):
        self.id = user_id
        self.username = username

class MockChat:
    def __init__(self, chat_id=98765):
        self.id = chat_id

class MockMessage:
    def __init__(self, text, user_id=12345, username="miquel"):
        self.text = text
        self.from_user = MockUser(user_id, username)
        self.chat = MockChat()
        self.message_id = 55555

class MockCallbackQuery:
    def __init__(self, data, user_id=12345, username="miquel", message_text="Test Message"):
        self.id = "999"
        self.data = data
        self.from_user = MockUser(user_id, username)
        self.message = MockMessage(message_text, user_id, username)

class TestTelegramBot(unittest.TestCase):
    def setUp(self):
        import core.telegram_bot
        core.telegram_bot.bot = None
        core.telegram_bot.bot_thread = None
        core.telegram_bot.stop_event.clear()

    def tearDown(self):
        import core.telegram_bot
        core.telegram_bot.bot = None
        core.telegram_bot.bot_thread = None
        core.telegram_bot.stop_event.clear()

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    def test_telegram_bot_disabled_when_no_token(self, mock_thread_class, mock_telebot_class):
        # Configurar variables de entorno vacías
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_USER_ID": ""}):
            start_telegram_bot()
            mock_telebot_class.assert_not_called()
            mock_thread_class.assert_not_called()

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    def test_telegram_bot_unauthorized_user(self, mock_thread, mock_telebot_class):
        # 1. Configurar Mock de TeleBot
        handlers = {}
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance

        # Capturar handlers registrados a través del decorador
        def mock_message_handler(**filters):
            def decorator(func):
                handlers[func.__name__] = func
                return func
            return decorator
        
        mock_bot_instance.message_handler.side_effect = mock_message_handler

        # 2. Inicializar bot con Token y User ID
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            # Verificar que se creó el bot y arrancó el hilo
            mock_telebot_class.assert_called_once_with("valid_token", threaded=True)
            mock_thread.assert_called_once()
            
            # 3. Probar petición con ID no autorizado
            unauth_msg = MockMessage("/start", user_id=99999, username="intruder")
            
            # Invocar handle_start
            handlers["handle_start"](unauth_msg)
            
            # Debería responder con error de autorización
            mock_bot_instance.reply_to.assert_called_once()
            args, kwargs = mock_bot_instance.reply_to.call_args
            self.assertIn("no tienes autorización", args[1].lower())

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.boot_time')
    @patch('time.time')
    def test_telegram_bot_status_authorized(self, mock_time, mock_boot_time, mock_virtual_mem, mock_cpu, mock_thread, mock_telebot_class):
        # 1. Mocks de psutil
        mock_cpu.return_value = 12.5
        mock_virtual_mem.return_value.percent = 45.0
        mock_boot_time.return_value = 1000.0
        mock_time.return_value = 2000.0 # Uptime = 1000 segundos

        # 2. Capturar handlers
        handlers = {}
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        mock_bot_instance.message_handler.side_effect = lambda **f: lambda func: handlers.setdefault(func.__name__, func)

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            # 3. Probar status con ID autorizado
            auth_msg = MockMessage("/status", user_id=12345)
            handlers["handle_status"](auth_msg)
            
            mock_bot_instance.reply_to.assert_called_once()
            args, kwargs = mock_bot_instance.reply_to.call_args
            response_text = args[1]
            self.assertIn("12.5%", response_text)
            self.assertIn("45.0%", response_text)
            self.assertIn("CPU", response_text)

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    @patch('core.telegram_bot.take_screenshot')
    @patch('os.path.exists')
    def test_telegram_bot_screenshot_authorized(self, mock_exists, mock_take_screenshot, mock_thread, mock_telebot_class):
        handlers = {}
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        mock_bot_instance.message_handler.side_effect = lambda **f: lambda func: handlers.setdefault(func.__name__, func)

        mock_exists.return_value = True

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            auth_msg = MockMessage("/screenshot", user_id=12345)
            
            # Mock de open para simular envío de archivo
            with patch("builtins.open", mock_open(read_data=b"image_bytes")) as mock_file:
                handlers["handle_screenshot"](auth_msg)
                mock_take_screenshot.assert_called_once()
                mock_bot_instance.send_photo.assert_called_once()
                args, kwargs = mock_bot_instance.send_photo.call_args
                self.assertEqual(args[0], 98765) # chat.id
                self.assertIn("Captura de pantalla actual", kwargs.get("caption", ""))

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    @patch('tools.voice.speak')
    def test_telegram_bot_say_authorized(self, mock_speak, mock_thread, mock_telebot_class):
        handlers = {}
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        mock_bot_instance.message_handler.side_effect = lambda **f: lambda func: handlers.setdefault(func.__name__, func)

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            auth_msg = MockMessage("/say Hola Jarvis", user_id=12345)
            handlers["handle_say"](auth_msg)
            
            mock_speak.assert_called_once_with("Hola Jarvis", disable_vad=True)
            mock_bot_instance.reply_to.assert_called_once()

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    @patch('core.telegram_bot.is_command_safe')
    @patch('core.telegram_bot.execute_cmd')
    def test_telegram_bot_cmd_authorized(self, mock_execute, mock_safe, mock_thread, mock_telebot_class):
        handlers = {}
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        mock_bot_instance.message_handler.side_effect = lambda **f: lambda func: handlers.setdefault(func.__name__, func)

        mock_safe.return_value = True
        mock_execute.return_value = "Command output result"

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            auth_msg = MockMessage("/cmd git status", user_id=12345)
            handlers["handle_cmd"](auth_msg)
            
            mock_safe.assert_called_once_with("git status")
            mock_execute.assert_called_once_with("git status")
            mock_bot_instance.reply_to.assert_called_once()
            args, kwargs = mock_bot_instance.reply_to.call_args
            self.assertIn("Command output result", args[1])

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    @patch('core.telegram_bot.smart_route')
    @patch('core.telegram_bot.get_executor')
    @patch('core.telegram_bot.update_state')
    def test_telegram_bot_natural_language_agent(self, mock_update_state, mock_get_executor, mock_route, mock_thread, mock_telebot_class):
        handlers = {}
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        mock_bot_instance.message_handler.side_effect = lambda **f: lambda func: handlers.setdefault(func.__name__, func)

        # Simular que el router inteligente no puede procesarlo
        mock_route.return_value = None
        
        # Simular respuesta del agente
        mock_agent_instance = MagicMock()
        mock_get_executor.return_value = mock_agent_instance
        mock_agent_instance.invoke.return_value = {"output": "Respuesta del agente general"}

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            auth_msg = MockMessage("busca en internet", user_id=12345)
            handlers["handle_natural_language"](auth_msg)
            
            mock_route.assert_called_once_with("busca en internet")
            mock_agent_instance.invoke.assert_called_once_with({"input": "busca en internet"})
            mock_bot_instance.reply_to.assert_called_once_with(auth_msg, "Respuesta del agente general")
            
            # Verificar que actualizó los estados de la GUI
            mock_update_state.assert_any_call("thinking", transcript="[Telegram] busca en internet", model="")
            mock_update_state.assert_any_call("speaking", response="Respuesta del agente general", model="deepseek/deepseek-v4-pro")
            mock_update_state.assert_any_call("idle")

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    def test_telegram_bot_mfa_send_command(self, mock_thread, mock_telebot_class):
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            from core.telegram_bot import _send_mfa_request_sync
            _send_mfa_request_sync("command", {"command": "git status"})
            
            mock_bot_instance.send_message.assert_called_once()
            args, kwargs = mock_bot_instance.send_message.call_args
            self.assertEqual(args[0], "12345")
            self.assertIn("MFA: Confirmación de Comando", args[1])
            self.assertIn("git status", args[1])
            self.assertIsNotNone(kwargs.get("reply_markup"))

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    def test_telegram_bot_mfa_send_model(self, mock_thread, mock_telebot_class):
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            from core.telegram_bot import _send_mfa_request_sync
            _send_mfa_request_sync("model", {"model_name": "moonshotai/kimi-k2.6", "prompt": "hola"})
            
            mock_bot_instance.send_message.assert_called_once()
            args, kwargs = mock_bot_instance.send_message.call_args
            self.assertEqual(args[0], "12345")
            self.assertIn("MFA: Uso de Modelo Costoso", args[1])
            self.assertIn("moonshotai/kimi-k2.6", args[1])
            self.assertIsNotNone(kwargs.get("reply_markup"))

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    @patch('tools.model_delegate.confirm_pending_model')
    def test_telegram_bot_callback_approve(self, mock_confirm, mock_thread, mock_telebot_class):
        callback_handlers = {}
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        mock_bot_instance.callback_query_handler.side_effect = lambda **f: lambda func: callback_handlers.setdefault(func.__name__, func)
        
        mock_confirm.invoke.return_value = "Command output success"

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            self.assertIn("handle_mfa_callback", callback_handlers)
            handler = callback_handlers["handle_mfa_callback"]
            
            query = MockCallbackQuery("mfa_approve_command", user_id=12345)
            handler(query)
            
            mock_bot_instance.answer_callback_query.assert_called_once()
            mock_confirm.invoke.assert_called_once_with("adelante")
            mock_bot_instance.edit_message_text.assert_called()

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    @patch('tools.model_delegate.cancel_pending_model')
    def test_telegram_bot_callback_cancel(self, mock_cancel, mock_thread, mock_telebot_class):
        callback_handlers = {}
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        mock_bot_instance.callback_query_handler.side_effect = lambda **f: lambda func: callback_handlers.setdefault(func.__name__, func)
        
        mock_cancel.invoke.return_value = "Cancelado con éxito"

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            self.assertIn("handle_mfa_callback", callback_handlers)
            handler = callback_handlers["handle_mfa_callback"]
            
            query = MockCallbackQuery("mfa_cancel_command", user_id=12345)
            handler(query)
            
            mock_bot_instance.answer_callback_query.assert_called_once()
            mock_cancel.invoke.assert_called_once_with("cancela")
            mock_bot_instance.edit_message_text.assert_called_once()

    @patch('telebot.TeleBot')
    @patch('threading.Thread')
    def test_telegram_bot_callback_unauthorized(self, mock_thread, mock_telebot_class):
        callback_handlers = {}
        mock_bot_instance = MagicMock()
        mock_telebot_class.return_value = mock_bot_instance
        mock_bot_instance.callback_query_handler.side_effect = lambda **f: lambda func: callback_handlers.setdefault(func.__name__, func)
        
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token", "TELEGRAM_USER_ID": "12345"}):
            start_telegram_bot()
            
            self.assertIn("handle_mfa_callback", callback_handlers)
            handler = callback_handlers["handle_mfa_callback"]
            
            query = MockCallbackQuery("mfa_approve_command", user_id=99999)
            handler(query)
            
            mock_bot_instance.answer_callback_query.assert_called_once()
            args, kwargs = mock_bot_instance.answer_callback_query.call_args
            self.assertIn("No tienes autorización", args[1])
            mock_bot_instance.edit_message_text.assert_not_called()

if __name__ == '__main__':
    unittest.main()
