import sys
import os
import unittest
from unittest.mock import patch

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.fast_commands import handle_fast_command

class TestFastCommands(unittest.TestCase):
    def test_time_command(self):
        resp = handle_fast_command("que hora es")
        self.assertIsNotNone(resp)
        self.assertTrue(resp.startswith("Son las"))
        
        resp_alt = handle_fast_command("dime la hora")
        self.assertIsNotNone(resp_alt)
        self.assertTrue(resp_alt.startswith("Son las"))

    def test_date_command(self):
        resp = handle_fast_command("que dia es")
        self.assertIsNotNone(resp)
        self.assertTrue(resp.startswith("Hoy es"))
        
        resp_alt = handle_fast_command("fecha de hoy")
        self.assertIsNotNone(resp_alt)
        self.assertTrue(resp_alt.startswith("Hoy es"))

    @patch("webbrowser.open")
    def test_website_command(self, mock_open):
        resp = handle_fast_command("abre youtube")
        self.assertEqual(resp, "Abriendo youtube, señor.")
        mock_open.assert_called_once_with("https://www.youtube.com")

        resp_gmail = handle_fast_command("abrir gmail")
        self.assertEqual(resp_gmail, "Abriendo gmail, señor.")
        mock_open.assert_any_call("https://mail.google.com")

    @patch("os.system")
    def test_apps_command(self, mock_system):
        resp = handle_fast_command("abre calculadora")
        self.assertEqual(resp, "Abriendo calculadora, señor.")
        mock_system.assert_called_once_with("start calc")

    def test_no_match(self):
        resp = handle_fast_command("cual es el sentido de la vida")
        self.assertIsNone(resp)

if __name__ == "__main__":
    unittest.main()
