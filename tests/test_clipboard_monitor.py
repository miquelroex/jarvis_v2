import unittest
import os
import sys
import time
from unittest.mock import patch, MagicMock, call

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mockear win32clipboard y tkinter antes de importar los módulos de core
mock_win32cb = MagicMock()
sys.modules['win32clipboard'] = mock_win32cb

import core.clipboard_monitor as cb_monitor
import core.pending_actions as pending_actions


class TestClipboardMonitor(unittest.TestCase):

    def setUp(self):
        cb_monitor.LAST_DETECTION = None
        cb_monitor._last_clipboard_hash = None

    def test_detect_type_traceback(self):
        """Valida la detección correcta de tracebacks de Python."""
        tb_text = (
            "Traceback (most recent call last):\n"
            "  File \"main.py\", line 15, in <module>\n"
            "    foo()\n"
            "ValueError: invalid value"
        )
        self.assertEqual(cb_monitor.detect_type(tb_text), "traceback")

    def test_detect_type_url(self):
        """Valida la detección correcta de URLs."""
        url_text = "https://www.google.com"
        self.assertEqual(cb_monitor.detect_type(url_text), "url")
        
        # URL con espacios o texto alrededor no debe clasificarse como tipo URL simple
        mixed_text = "mira esta web https://google.com es genial"
        self.assertNotEqual(cb_monitor.detect_type(mixed_text), "url")

    def test_detect_type_code(self):
        """Valida la detección correcta de fragmentos de código."""
        code_text = "def calculate_sum(a, b):\n    return a + b"
        self.assertEqual(cb_monitor.detect_type(code_text), "code")

        non_code_text = "hola señor, cómo está usted hoy?"
        self.assertIsNone(cb_monitor.detect_type(non_code_text))

    @patch("core.clipboard_monitor.read_clipboard_win32")
    @patch("core.clipboard_monitor.read_clipboard_tkinter")
    def test_read_clipboard_fallbacks(self, mock_tk, mock_win):
        """Valida que read_clipboard intente win32 y caiga a tkinter si falla."""
        # Caso 1: Win32 devuelve valor exitoso
        mock_win.return_value = "win32 text"
        self.assertEqual(cb_monitor.read_clipboard(), "win32 text")
        mock_tk.assert_not_called()

        # Caso 2: Win32 devuelve None, llama a Tkinter
        mock_win.return_value = None
        mock_tk.return_value = "tkinter text"
        self.assertEqual(cb_monitor.read_clipboard(), "tkinter text")
        mock_tk.assert_called_once()

    @patch("core.clipboard_monitor.read_clipboard")
    @patch("tools.voice.speak")
    def test_monitor_loop_emits_event(self, mock_speak, mock_read):
        """Prueba que el loop de monitoreo detecte cambios y emita eventos por socket."""
        mock_socketio = MagicMock()
        mock_read.side_effect = ["Traceback (most recent call last):\n  File \"a.py\", line 1", None]

        # Corremos una iteración corta limitando con stop_event
        cb_monitor._stop_event.clear()
        
        # Hilo para detenerlo enseguida
        def stop_after_delay():
            time.sleep(0.05)
            cb_monitor._stop_event.set()
        
        import threading
        threading.Thread(target=stop_after_delay).start()
        
        cb_monitor.monitor_loop(mock_socketio)

        # Validar emisión del socket
        mock_socketio.emit.assert_called_once()
        args = mock_socketio.emit.call_args[0]
        self.assertEqual(args[0], "clipboard_detection")
        self.assertEqual(args[1]["type"], "traceback")
        self.assertIn("Traceback", args[1]["preview"])

    @patch("tools.model_delegate.ask_delegated_model")
    def test_pending_action_clipboard_traceback(self, mock_ask):
        """Valida que execute_pending_action resuelva tracebacks del portapapeles."""
        cb_monitor.LAST_DETECTION = {
            "type": "traceback",
            "text": "ValueError: error",
            "timestamp": time.time()
        }
        mock_ask.return_value = "Solución propuesta"

        with patch("core.pending_actions.load_pending_action") as mock_load:
            mock_load.return_value = None  # No hay acción en archivo json
            res = pending_actions.execute_pending_action()
            
            self.assertEqual(res, "Solución propuesta")
            mock_ask.assert_called_once()
            # Se limpia la detección
            self.assertIsNone(cb_monitor.LAST_DETECTION)


if __name__ == "__main__":
    unittest.main()
