"""Tests del Modo Conversación Continua (core/conversation_flow.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.conversation_flow as cf


class TestEnabled(unittest.TestCase):
    def test_default_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_CONTINUOUS_MODE", None)
            self.assertFalse(cf.continuous_mode_enabled())

    def test_on_variants(self):
        for v in ("true", "1", "YES", "True"):
            with patch.dict(os.environ, {"JARVIS_CONTINUOUS_MODE": v}):
                self.assertTrue(cf.continuous_mode_enabled())

    def test_off_variants(self):
        for v in ("false", "0", "no", ""):
            with patch.dict(os.environ, {"JARVIS_CONTINUOUS_MODE": v}):
                self.assertFalse(cf.continuous_mode_enabled())


class TestTimeout(unittest.TestCase):
    def test_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_CONVERSATION_TIMEOUT", None)
            self.assertEqual(cf.conversation_timeout(), 10)
            self.assertEqual(cf.conversation_timeout(default=20), 20)

    def test_from_env(self):
        with patch.dict(os.environ, {"JARVIS_CONVERSATION_TIMEOUT": "25"}):
            self.assertEqual(cf.conversation_timeout(), 25)

    def test_bad_value_falls_back(self):
        with patch.dict(os.environ, {"JARVIS_CONVERSATION_TIMEOUT": "abc"}):
            self.assertEqual(cf.conversation_timeout(default=12), 12)


class TestShouldStay(unittest.TestCase):
    def test_requires_both_command_and_enabled(self):
        with patch.dict(os.environ, {"JARVIS_CONTINUOUS_MODE": "true"}):
            self.assertTrue(cf.should_stay_conversational(True))
            self.assertFalse(cf.should_stay_conversational(False))   # no hubo comando
        with patch.dict(os.environ, {"JARVIS_CONTINUOUS_MODE": "false"}):
            self.assertFalse(cf.should_stay_conversational(True))    # modo apagado


if __name__ == "__main__":
    unittest.main()
