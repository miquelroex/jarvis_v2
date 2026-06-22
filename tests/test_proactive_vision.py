"""Tests del JARVIS Proactivo Visual (core/proactive_vision.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.proactive_vision as pv


class TestParseDecision(unittest.TestCase):
    def test_plain_json_interrupt(self):
        d = pv._parse_decision('{"interrupt": true, "message": "Señor, hay un error."}')
        self.assertTrue(d["interrupt"])
        self.assertEqual(d["message"], "Señor, hay un error.")

    def test_plain_json_no_interrupt(self):
        d = pv._parse_decision('{"interrupt": false, "message": ""}')
        self.assertFalse(d["interrupt"])
        self.assertEqual(d["message"], "")

    def test_json_in_markdown_fence(self):
        text = '```json\n{"interrupt": true, "message": "Atascado, señor."}\n```'
        d = pv._parse_decision(text)
        self.assertTrue(d["interrupt"])
        self.assertEqual(d["message"], "Atascado, señor.")

    def test_json_with_surrounding_text(self):
        text = 'Claro, aquí tienes: {"interrupt": false, "message": "nada"} fin.'
        d = pv._parse_decision(text)
        self.assertFalse(d["interrupt"])

    def test_garbage_is_conservative(self):
        self.assertEqual(pv._parse_decision("no soy json"), {"interrupt": False, "message": ""})

    def test_empty(self):
        self.assertEqual(pv._parse_decision(""), {"interrupt": False, "message": ""})
        self.assertEqual(pv._parse_decision(None), {"interrupt": False, "message": ""})


class TestRunProactiveCheck(unittest.TestCase):
    def test_returns_decision_when_capture_ok(self):
        with patch.object(pv, "_capture_screen", return_value=True), \
             patch.object(pv, "_analyze_screen", return_value={"interrupt": True, "message": "Aviso."}):
            d = pv.run_proactive_check()
        self.assertTrue(d["interrupt"])
        self.assertEqual(d["message"], "Aviso.")
        self.assertIn("timestamp", d)

    def test_no_interrupt_when_capture_fails(self):
        with patch.object(pv, "_capture_screen", return_value=False), \
             patch.object(pv, "_analyze_screen") as mock_analyze:
            d = pv.run_proactive_check()
        self.assertFalse(d["interrupt"])
        mock_analyze.assert_not_called()  # no analiza si no hay captura


class TestAnalyzeScreen(unittest.TestCase):
    def test_no_api_key_returns_no_interrupt(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": ""}):
            d = pv._analyze_screen()
        self.assertFalse(d["interrupt"])


if __name__ == "__main__":
    unittest.main()
