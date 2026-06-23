"""Tests del Protocolo Blackout / modo noche (core/night_mode.py)."""
import os
import sys
import types
import unittest
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.night_mode as nm


class TestIsNight(unittest.TestCase):
    def test_simple_window_no_wrap(self):
        # Franja 00:00–07:00 (start < end).
        self.assertTrue(nm._is_night(0, 0, 7))
        self.assertTrue(nm._is_night(6, 0, 7))
        self.assertFalse(nm._is_night(7, 0, 7))
        self.assertFalse(nm._is_night(12, 0, 7))
        self.assertFalse(nm._is_night(23, 0, 7))

    def test_wrap_around_midnight(self):
        # Franja 23:00–07:00 (start > end, cruza la medianoche).
        self.assertTrue(nm._is_night(23, 23, 7))
        self.assertTrue(nm._is_night(0, 23, 7))
        self.assertTrue(nm._is_night(6, 23, 7))
        self.assertFalse(nm._is_night(7, 23, 7))
        self.assertFalse(nm._is_night(22, 23, 7))
        self.assertFalse(nm._is_night(12, 23, 7))

    def test_equal_start_end_is_never_night(self):
        self.assertFalse(nm._is_night(0, 5, 5))
        self.assertFalse(nm._is_night(5, 5, 5))


class TestSetBlackout(unittest.TestCase):
    def setUp(self):
        nm._blackout_active = False

    def _fake_gui(self):
        emitted = []
        fake = types.SimpleNamespace(socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: emitted.append(ev)))
        return fake, emitted

    def test_activate_emits_on_and_sets_state(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}):
            result = nm.set_blackout(True)
        self.assertTrue(result)
        self.assertTrue(nm.is_blackout_active())
        self.assertEqual(emitted, ["blackout_on"])

    def test_deactivate_emits_off(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}):
            nm.set_blackout(False)
        self.assertFalse(nm.is_blackout_active())
        self.assertEqual(emitted, ["blackout_off"])

    def test_announce_speaks_reminder(self):
        fake, _ = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.object(nm, "_gentle_reminder") as mock_remind, \
             patch.object(nm, "_maybe_lower_volume") as mock_vol:
            nm.set_blackout(True, announce=True)
        mock_remind.assert_called_once()
        mock_vol.assert_called_once()

    def test_no_emit_when_gui_not_loaded(self):
        # Sin gui.app en sys.modules no debe lanzar excepción.
        saved = sys.modules.pop("gui.app", None)
        try:
            nm.set_blackout(True)
        finally:
            if saved is not None:
                sys.modules["gui.app"] = saved
        self.assertTrue(nm.is_blackout_active())


class TestMaybeLowerVolume(unittest.TestCase):
    def test_disabled_does_nothing(self):
        fake_audio = types.SimpleNamespace(set_volume=lambda v: (_ for _ in ()).throw(AssertionError("no debería llamarse")))
        with patch.dict(os.environ, {"JARVIS_BLACKOUT_LOWER_VOLUME": "false"}), \
             patch.dict(sys.modules, {"core.system_audio": fake_audio}):
            nm._maybe_lower_volume()  # no debe llamar set_volume

    def test_enabled_lowers_volume(self):
        calls = []
        fake_audio = types.SimpleNamespace(set_volume=lambda v: calls.append(v))
        with patch.dict(os.environ, {"JARVIS_BLACKOUT_LOWER_VOLUME": "true", "JARVIS_BLACKOUT_VOLUME": "25"}), \
             patch.dict(sys.modules, {"core.system_audio": fake_audio}):
            nm._maybe_lower_volume()
        self.assertEqual(calls, [25])


class TestDaemon(unittest.TestCase):
    def tearDown(self):
        nm.stop_night_mode_daemon()
        nm.BLACKOUT_THREAD = None

    def test_disabled_does_not_start(self):
        with patch.dict(os.environ, {"JARVIS_BLACKOUT_ENABLED": "false"}):
            nm.start_night_mode_daemon()
        self.assertIsNone(nm.BLACKOUT_THREAD)

    def test_enabled_starts_thread(self):
        with patch.dict(os.environ, {"JARVIS_BLACKOUT_ENABLED": "true"}):
            nm.start_night_mode_daemon()
        self.assertIsNotNone(nm.BLACKOUT_THREAD)
        self.assertTrue(nm.BLACKOUT_THREAD.is_alive())


if __name__ == "__main__":
    unittest.main()
