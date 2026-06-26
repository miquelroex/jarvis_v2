"""Tests del anunciador de notificaciones (core/announcer.py)."""
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.announcer as an


class TestFormat(unittest.TestCase):
    def test_message(self):
        self.assertEqual(an.format_announcement("Telegram"), "Señor, mensaje entrante de Telegram.")

    def test_message_high_priority(self):
        self.assertEqual(an.format_announcement("Jefe", priority="high"), "Mensaje prioritario de Jefe, señor.")

    def test_call(self):
        self.assertEqual(an.format_announcement("Mamá", kind="call"), "Señor, una llamada entrante de Mamá.")

    def test_device(self):
        self.assertIn("dispositivo entrante", an.format_announcement("iPhone", kind="device"))

    def test_alert_high(self):
        self.assertIn("ALERTA PRIORITARIA", an.format_announcement("build roto", kind="alert", priority="high"))

    def test_empty_source(self):
        self.assertIn("origen desconocido", an.format_announcement(""))


class TestAnnounce(unittest.TestCase):
    def _fake_gui(self):
        emitted = []
        fake = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: emitted.append((ev, a))))
        return fake, emitted

    def test_emits_banner(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.dict(os.environ, {"JARVIS_ANNOUNCE_ENABLED": "true"}):
            out = an.announce("Telegram")
        self.assertIn("Telegram", out)
        self.assertEqual(emitted[0][0], "notification_announce")
        self.assertEqual(emitted[0][1][0]["kind"], "message")

    def test_disabled(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.dict(os.environ, {"JARVIS_ANNOUNCE_ENABLED": "false"}):
            self.assertEqual(an.announce("X"), "")
            self.assertEqual(emitted, [])

    def test_voice_only_when_enabled(self):
        spoken = []
        fake_voice = types.SimpleNamespace(speak=lambda t, **k: spoken.append((t, k)))
        with patch.dict(sys.modules, {"tools.voice": fake_voice}), \
             patch.dict(os.environ, {"JARVIS_ANNOUNCE_ENABLED": "true", "JARVIS_ANNOUNCE_VOICE": "true"}):
            an.announce("Jefe", priority="high")
        self.assertEqual(len(spoken), 1)
        self.assertEqual(spoken[0][1].get("tone"), "alert")

    def test_no_voice_when_disabled(self):
        spoken = []
        fake_voice = types.SimpleNamespace(speak=lambda t, **k: spoken.append(t))
        with patch.dict(sys.modules, {"tools.voice": fake_voice}), \
             patch.dict(os.environ, {"JARVIS_ANNOUNCE_ENABLED": "true", "JARVIS_ANNOUNCE_VOICE": "false"}):
            an.announce("X")
        self.assertEqual(spoken, [])

    def test_speak_false_skips_voice(self):
        spoken = []
        fake_voice = types.SimpleNamespace(speak=lambda t, **k: spoken.append(t))
        with patch.dict(sys.modules, {"tools.voice": fake_voice}), \
             patch.dict(os.environ, {"JARVIS_ANNOUNCE_ENABLED": "true", "JARVIS_ANNOUNCE_VOICE": "true"}):
            an.announce("X", speak=False)
        self.assertEqual(spoken, [])

    def test_no_gui_no_crash(self):
        saved = sys.modules.pop("gui.app", None)
        try:
            with patch.dict(os.environ, {"JARVIS_ANNOUNCE_ENABLED": "true"}):
                an.announce("sin gui")
        finally:
            if saved is not None:
                sys.modules["gui.app"] = saved


if __name__ == "__main__":
    unittest.main()
