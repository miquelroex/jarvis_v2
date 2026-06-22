"""Tests del JARVIS Proactivo Visual (core/proactive_vision.py)."""
import os
import sys
import types
import threading
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


class TestDeliverAlert(unittest.TestCase):
    def setUp(self):
        pv._last_alert = ""
        self.spoken = []
        # Fake tools.voice para no importar el real (crash local de OpenSSL).
        self.fakes = {"tools.voice": types.SimpleNamespace(speak=lambda m, **k: self.spoken.append(m))}

    def test_speaks_on_interrupt(self):
        with patch.dict(sys.modules, self.fakes):
            ok = pv.deliver_alert({"interrupt": True, "message": "Señor, hay un error."})
        self.assertTrue(ok)
        self.assertEqual(self.spoken, ["Señor, hay un error."])

    def test_does_not_repeat_same_alert(self):
        with patch.dict(sys.modules, self.fakes):
            pv.deliver_alert({"interrupt": True, "message": "mismo aviso"})
            pv.deliver_alert({"interrupt": True, "message": "mismo aviso"})
        self.assertEqual(len(self.spoken), 1)

    def test_no_interrupt_resets_debounce(self):
        with patch.dict(sys.modules, self.fakes):
            pv.deliver_alert({"interrupt": True, "message": "aviso"})       # habla (1)
            pv.deliver_alert({"interrupt": False, "message": ""})           # reset
            pv.deliver_alert({"interrupt": True, "message": "aviso"})       # vuelve a hablar (2)
        self.assertEqual(len(self.spoken), 2)

    def test_no_speak_when_not_interrupt(self):
        with patch.dict(sys.modules, self.fakes):
            ok = pv.deliver_alert({"interrupt": False, "message": ""})
        self.assertFalse(ok)
        self.assertEqual(self.spoken, [])


class TestDaemon(unittest.TestCase):
    def setUp(self):
        pv.VISION_THREAD = None
        pv.stop_event.clear()

    def tearDown(self):
        pv.stop_event.set()
        pv.VISION_THREAD = None

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_PROACTIVE_VISION_ENABLED", None)
            pv.start_proactive_vision_daemon()
        self.assertIsNone(pv.VISION_THREAD)

    def test_start_stop_idempotent(self):
        keep_alive = threading.Event()

        def fake_loop():
            keep_alive.wait(timeout=5)

        with patch.dict(os.environ, {"JARVIS_PROACTIVE_VISION_ENABLED": "true"}), \
             patch.object(pv, "_vision_loop", side_effect=fake_loop):
            pv.start_proactive_vision_daemon()
            self.assertIsNotNone(pv.VISION_THREAD)
            first = pv.VISION_THREAD
            self.assertTrue(first.is_alive())
            pv.start_proactive_vision_daemon()  # no-op
            self.assertIs(pv.VISION_THREAD, first)
            pv.stop_proactive_vision_daemon()
            self.assertTrue(pv.stop_event.is_set())
            keep_alive.set()
            first.join(timeout=2)
            self.assertFalse(first.is_alive())


if __name__ == "__main__":
    unittest.main()
