import unittest
from unittest.mock import patch, MagicMock
from tools.active_window import get_active_window_details, get_active_window

class TestActiveWindow(unittest.TestCase):
    @patch('tools.active_window.win32gui')
    @patch('tools.active_window.win32process')
    @patch('psutil.Process')
    def test_get_active_window_details(self, mock_process_class, mock_win32process, mock_win32gui):
        # Configurar mocks
        mock_win32gui.GetForegroundWindow.return_value = 12345
        mock_win32gui.GetWindowText.return_value = "main.py - jarvis - Visual Studio Code"
        mock_win32process.GetWindowThreadProcessId.return_value = (9876, 54321) # thread_id, pid
        
        mock_process_instance = MagicMock()
        mock_process_instance.name.return_value = "Code.exe"
        mock_process_class.return_value = mock_process_instance
        
        # Ejecutar función
        details = get_active_window_details()
        
        # Validar resultados
        self.assertEqual(details["title"], "main.py - jarvis - Visual Studio Code")
        self.assertEqual(details["app_name"], "Code")
        self.assertEqual(details["pid"], 54321)
        
        mock_win32gui.GetForegroundWindow.assert_called_once()
        mock_win32gui.GetWindowText.assert_called_once_with(12345)
        mock_win32process.GetWindowThreadProcessId.assert_called_once_with(12345)
        mock_process_class.assert_called_once_with(54321)

    @patch('tools.active_window.get_active_window_details')
    def test_get_active_window_tool(self, mock_details):
        mock_details.return_value = {
            "title": "Google - Chrome",
            "app_name": "chrome",
            "pid": 9999
        }
        
        res = get_active_window.invoke("")
        self.assertIn("CHROME", res)
        self.assertIn("Google - Chrome", res)
        mock_details.assert_called_once()

if __name__ == '__main__':
    unittest.main()
