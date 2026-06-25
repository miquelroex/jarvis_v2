"""Tests del Medidor de Sarcasmo (core/personality.py)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.personality as personality


class TestClamp(unittest.TestCase):
    def test_within_range(self):
        self.assertEqual(personality.clamp_level(5), 5)

    def test_out_of_range(self):
        self.assertEqual(personality.clamp_level(-3), 0)
        self.assertEqual(personality.clamp_level(99), 10)

    def test_rounds_and_parses(self):
        self.assertEqual(personality.clamp_level("7"), 7)
        self.assertEqual(personality.clamp_level(6.6), 7)

    def test_bad_value_defaults(self):
        self.assertEqual(personality.clamp_level("x"), personality.DEFAULT_LEVEL)
        self.assertEqual(personality.clamp_level(None), personality.DEFAULT_LEVEL)


class TestDirective(unittest.TestCase):
    def test_levels_change_tone(self):
        formal = personality.get_sarcasm_directive(0)
        mid = personality.get_sarcasm_directive(6)
        savage = personality.get_sarcasm_directive(10)
        self.assertIn("formal", formal.lower())
        self.assertIn("0/10", formal)
        self.assertIn("6/10", mid)
        self.assertIn("socarrón", savage.lower())
        self.assertIn("10/10", savage)

    def test_directive_clamps(self):
        d = personality.get_sarcasm_directive(50)
        self.assertIn("10/10", d)


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "sarcasm_level.txt"
        self._patch = patch.object(personality, "SARCASM_FILE", self.tmp)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        if self.tmp.exists():
            self.tmp.unlink()

    def test_default_when_missing(self):
        self.assertEqual(personality.get_sarcasm_level(), personality.DEFAULT_LEVEL)

    def test_set_and_get(self):
        eff = personality.set_sarcasm_level(8)
        self.assertEqual(eff, 8)
        self.assertEqual(personality.get_sarcasm_level(), 8)

    def test_set_clamps_and_persists(self):
        self.assertEqual(personality.set_sarcasm_level(100), 10)
        self.assertEqual(personality.get_sarcasm_level(), 10)

    def test_adjust(self):
        personality.set_sarcasm_level(5)
        self.assertEqual(personality.adjust_sarcasm(3), 8)
        self.assertEqual(personality.adjust_sarcasm(-10), 0)


class TestPromptInjection(unittest.TestCase):
    def test_prompt_includes_sarcasm_directive(self):
        import core.prompts as prompts
        with patch("core.personality.get_sarcasm_level", return_value=9), \
             patch("core.memory.get_all_memories", return_value=[]), \
             patch.object(prompts, "is_socratic_mode_active", return_value=False):
            compiled = prompts.get_compiled_system_prompt()
        self.assertIn("MEDIDOR DE SARCASMO", compiled)
        self.assertIn("9/10", compiled)


if __name__ == "__main__":
    unittest.main()
