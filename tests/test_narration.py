"""Tests del Stream de Pensamiento (core/narration.py)."""
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.narration as nar


def _fake_gui():
    emitted = []
    fake = types.SimpleNamespace(
        socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: emitted.append((ev, a))))
    return fake, emitted


class TestEnabled(unittest.TestCase):
    def test_narration_default_on(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_NARRATION_ENABLED", None)
            self.assertTrue(nar.is_enabled())

    def test_voice_default_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_NARRATION_VOICE", None)
            self.assertFalse(nar.voice_enabled())


class TestNarrate(unittest.TestCase):
    def test_emits_to_gui(self):
        fake, emitted = _fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.dict(os.environ, {"JARVIS_NARRATION_ENABLED": "true"}):
            out = nar.narrate("Compilando…")
        self.assertEqual(out, "Compilando…")
        self.assertEqual(emitted[0][0], "thought_stream")
        self.assertEqual(emitted[0][1][0], {"text": "Compilando…"})

    def test_disabled_does_nothing(self):
        fake, emitted = _fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.dict(os.environ, {"JARVIS_NARRATION_ENABLED": "false"}):
            out = nar.narrate("x")
        self.assertEqual(out, "")
        self.assertEqual(emitted, [])

    def test_empty_ignored(self):
        with patch.dict(os.environ, {"JARVIS_NARRATION_ENABLED": "true"}):
            self.assertEqual(nar.narrate("  "), "")

    def test_speaks_only_when_voice_enabled(self):
        spoken = []
        fake_voice = types.SimpleNamespace(speak=lambda t, **k: spoken.append((t, k)))
        with patch.dict(sys.modules, {"tools.voice": fake_voice}), \
             patch.dict(os.environ, {"JARVIS_NARRATION_ENABLED": "true", "JARVIS_NARRATION_VOICE": "true"}):
            nar.narrate("Ejecutando pruebas…", tone="neutral")
        self.assertEqual(len(spoken), 1)
        self.assertEqual(spoken[0][1].get("tone"), "neutral")

    def test_no_voice_when_disabled(self):
        spoken = []
        fake_voice = types.SimpleNamespace(speak=lambda t, **k: spoken.append(t))
        with patch.dict(sys.modules, {"tools.voice": fake_voice}), \
             patch.dict(os.environ, {"JARVIS_NARRATION_ENABLED": "true", "JARVIS_NARRATION_VOICE": "false"}):
            nar.narrate("Paso silencioso")
        self.assertEqual(spoken, [])

    def test_speak_false_arg_skips_voice(self):
        spoken = []
        fake_voice = types.SimpleNamespace(speak=lambda t, **k: spoken.append(t))
        with patch.dict(sys.modules, {"tools.voice": fake_voice}), \
             patch.dict(os.environ, {"JARVIS_NARRATION_ENABLED": "true", "JARVIS_NARRATION_VOICE": "true"}):
            nar.narrate("solo HUD", speak=False)
        self.assertEqual(spoken, [])

    def test_no_gui_no_crash(self):
        saved = sys.modules.pop("gui.app", None)
        try:
            with patch.dict(os.environ, {"JARVIS_NARRATION_ENABLED": "true"}):
                nar.narrate("sin gui")  # no debe lanzar
        finally:
            if saved is not None:
                sys.modules["gui.app"] = saved


if __name__ == "__main__":
    unittest.main()
