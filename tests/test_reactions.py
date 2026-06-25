"""Tests de las Reacciones con Alma (core/reactions.py)."""
import os
import sys
import random
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.reactions as reactions


class TestGetReaction(unittest.TestCase):
    def test_unknown_event(self):
        self.assertIsNone(reactions.get_reaction("inexistente"))

    def test_fills_template(self):
        r = reactions.get_reaction("test_broken", {"name": "tests.test_x"}, rng=random.Random(0))
        self.assertIn("tests.test_x", r["phrase"])
        self.assertEqual(r["tone"], "alert")

    def test_recovered_normal_vs_streak(self):
        normal = reactions.get_reaction("test_recovered", {"name": "S", "fails": 1}, rng=random.Random(1))
        streak = reactions.get_reaction("test_recovered", {"name": "S", "fails": 5}, rng=random.Random(1))
        # La variante de racha menciona el nº de fallos.
        self.assertNotIn("5", normal["phrase"])
        self.assertIn("5", streak["phrase"])
        self.assertEqual(streak["tone"], "success")

    def test_missing_context_key_is_safe(self):
        # Sin 'name' en el contexto no debe lanzar.
        r = reactions.get_reaction("test_broken", {}, rng=random.Random(0))
        self.assertIsInstance(r["phrase"], str)


class TestReact(unittest.TestCase):
    def test_disabled_returns_empty_and_silent(self):
        with patch.dict(os.environ, {"JARVIS_REACTIONS_ENABLED": "false"}):
            spoken = []
            fake_voice = type(sys)("tools.voice")
            fake_voice.speak = lambda *a, **k: spoken.append(a)
            with patch.dict(sys.modules, {"tools.voice": fake_voice}):
                out = reactions.react("task_success")
            self.assertEqual(out, "")
            self.assertEqual(spoken, [])

    def test_enabled_speaks_with_tone(self):
        spoken = {}
        fake_voice = type(sys)("tools.voice")
        def _speak(text, disable_vad=False, tone=None):
            spoken["text"] = text
            spoken["tone"] = tone
        fake_voice.speak = _speak
        with patch.dict(os.environ, {"JARVIS_REACTIONS_ENABLED": "true"}), \
             patch.dict(sys.modules, {"tools.voice": fake_voice}):
            out = reactions.react("critical_alert")
        self.assertTrue(out)
        self.assertEqual(spoken["tone"], "alert")
        self.assertEqual(spoken["text"], out)

    def test_unknown_event_returns_empty(self):
        with patch.dict(os.environ, {"JARVIS_REACTIONS_ENABLED": "true"}):
            self.assertEqual(reactions.react("xxx"), "")


class TestEmotionDirective(unittest.TestCase):
    def test_enabled(self):
        with patch.dict(os.environ, {"JARVIS_REACTIONS_ENABLED": "true"}):
            self.assertIn("REACCIONES CON ALMA", reactions.get_emotion_directive())

    def test_disabled_empty(self):
        with patch.dict(os.environ, {"JARVIS_REACTIONS_ENABLED": "false"}):
            self.assertEqual(reactions.get_emotion_directive(), "")

    def test_prompt_injection(self):
        import core.prompts as prompts
        with patch.dict(os.environ, {"JARVIS_REACTIONS_ENABLED": "true"}), \
             patch("core.memory.get_all_memories", return_value=[]), \
             patch.object(prompts, "is_socratic_mode_active", return_value=False):
            compiled = prompts.get_compiled_system_prompt()
        self.assertIn("REACCIONES CON ALMA", compiled)


if __name__ == "__main__":
    unittest.main()
