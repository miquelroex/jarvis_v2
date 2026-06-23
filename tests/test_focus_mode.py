"""Tests del Protocolo de Enfoque "Verónica" (core/focus_mode.py)."""
import os
import sys
import types
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.focus_mode as fm


class TestFormatRemaining(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(fm._format_remaining(0), "00:00")
        self.assertEqual(fm._format_remaining(65), "01:05")
        self.assertEqual(fm._format_remaining(1500), "25:00")

    def test_negative_clamped(self):
        self.assertEqual(fm._format_remaining(-10), "00:00")

    def test_bad_value(self):
        self.assertEqual(fm._format_remaining(None), "00:00")


class TestStartStop(unittest.TestCase):
    def setUp(self):
        fm._active = False
        fm._ends_at = None
        fm._prev_toast = None

    def tearDown(self):
        fm.stop_timer.set()
        if fm.FOCUS_TIMER is not None and fm.FOCUS_TIMER.is_alive():
            fm.FOCUS_TIMER.join(timeout=2)
        fm.FOCUS_TIMER = None

    def _fake_gui(self):
        emitted = []
        fake = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: emitted.append((ev, a))))
        return fake, emitted

    def test_start_sets_state_and_emits(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.object(fm, "_set_toast_notifications", return_value=1) as mute, \
             patch.object(fm, "_speak"):
            mins = fm.start_focus(30, announce=True)
        self.assertEqual(mins, 30)
        self.assertTrue(fm.is_focus_active())
        self.assertIsNotNone(fm.get_ends_at())
        self.assertGreater(fm.get_ends_at(), time.time())
        mute.assert_called_once_with(False)
        self.assertEqual(emitted[0][0], "veronica_on")

    def test_start_uses_default_minutes(self):
        fake, _ = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.dict(os.environ, {"JARVIS_FOCUS_DEFAULT_MINUTES": "40"}), \
             patch.object(fm, "_set_toast_notifications", return_value=1), \
             patch.object(fm, "_speak"):
            mins = fm.start_focus(None, announce=False)
        self.assertEqual(mins, 40)

    def test_stop_restores_notifications_and_state(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.object(fm, "_set_toast_notifications", return_value=1) as toggle, \
             patch.object(fm, "_speak"):
            fm.start_focus(30, announce=False)
            toggle.reset_mock()
            was = fm.stop_focus(announce=True)
        self.assertTrue(was)
        self.assertFalse(fm.is_focus_active())
        self.assertIsNone(fm.get_ends_at())
        # Restaura al valor previo (1 -> True).
        toggle.assert_called_once_with(True)
        self.assertIn("veronica_off", [e[0] for e in emitted])

    def test_mute_disabled_skips_registry(self):
        fake, _ = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.dict(os.environ, {"JARVIS_FOCUS_MUTE_NOTIFICATIONS": "false"}), \
             patch.object(fm, "_set_toast_notifications") as toggle, \
             patch.object(fm, "_speak"):
            fm.start_focus(10, announce=False)
            fm.stop_focus(announce=False)
        toggle.assert_not_called()


class TestRegistryFunction(unittest.TestCase):
    def test_writes_and_returns_prev(self):
        fake_key = object()
        fake_winreg = types.SimpleNamespace(
            HKEY_CURRENT_USER=0, KEY_READ=1, KEY_WRITE=2, REG_DWORD=4,
            OpenKey=lambda *a, **k: _Ctx(fake_key),
            QueryValueEx=lambda key, name: (1, 4),
            SetValueEx=lambda *a: None,
        )
        with patch.dict(sys.modules, {"winreg": fake_winreg}):
            prev = fm._set_toast_notifications(False)
        self.assertEqual(prev, 1)


class _Ctx:
    def __init__(self, val):
        self.val = val
    def __enter__(self):
        return self.val
    def __exit__(self, *a):
        return False


if __name__ == "__main__":
    unittest.main()
