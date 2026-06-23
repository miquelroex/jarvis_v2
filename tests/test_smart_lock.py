"""Tests de Smart Lock por proximidad Bluetooth (core/smart_lock.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.smart_lock as sl


class TestEvaluatePresence(unittest.TestCase):
    def _devs(self):
        return [
            {"address": "AA:BB:CC:DD:EE:FF", "name": "Galaxy Watch", "rssi": -60},
            {"address": "11:22:33:44:55:66", "name": "Otro", "rssi": -40},
        ]

    def test_present_by_mac_above_threshold(self):
        present, rssi = sl._evaluate_presence(self._devs(), "aa:bb:cc:dd:ee:ff", "", -85)
        self.assertTrue(present)
        self.assertEqual(rssi, -60)

    def test_absent_when_below_threshold(self):
        present, rssi = sl._evaluate_presence(self._devs(), "AA:BB:CC:DD:EE:FF", "", -50)
        self.assertFalse(present)
        self.assertEqual(rssi, -60)

    def test_not_found_returns_false_none(self):
        present, rssi = sl._evaluate_presence(self._devs(), "00:00:00:00:00:00", "", -85)
        self.assertFalse(present)
        self.assertIsNone(rssi)

    def test_match_by_name(self):
        present, rssi = sl._evaluate_presence(self._devs(), "", "galaxy", -85)
        self.assertTrue(present)
        self.assertEqual(rssi, -60)

    def test_mac_normalization_dashes(self):
        present, _ = sl._evaluate_presence(
            [{"address": "AA-BB-CC-DD-EE-FF", "name": None, "rssi": -70}],
            "aa:bb:cc:dd:ee:ff", "", -85)
        self.assertTrue(present)


class TestDecide(unittest.TestCase):
    def test_present_resets_counter(self):
        count, was, action = sl._decide(True, 2, True, 3)
        self.assertEqual(count, 0)
        self.assertTrue(was)
        self.assertIsNone(action)

    def test_return_triggers_welcome(self):
        count, was, action = sl._decide(True, 5, False, 3)
        self.assertEqual(count, 0)
        self.assertTrue(was)
        self.assertEqual(action, "welcome")

    def test_absent_increments_until_lock(self):
        # Dos ausencias: aún no bloquea.
        count, was, action = sl._decide(False, 1, True, 3)
        self.assertEqual(count, 2)
        self.assertTrue(was)
        self.assertIsNone(action)
        # Tercera ausencia: bloquea y marca ausente.
        count, was, action = sl._decide(False, 2, True, 3)
        self.assertEqual(count, 3)
        self.assertFalse(was)
        self.assertEqual(action, "lock")

    def test_no_relock_while_absent(self):
        count, was, action = sl._decide(False, 10, False, 3)
        self.assertEqual(count, 11)
        self.assertFalse(was)
        self.assertIsNone(action)


class TestScanDevicesNoBleak(unittest.TestCase):
    def test_returns_empty_without_bleak(self):
        # Forzar ImportError de bleak.
        with patch.dict(sys.modules, {"bleak": None}):
            sl._warned_no_bleak = False
            result = sl._scan_devices(1.0)
        self.assertEqual(result, [])


class TestStartGate(unittest.TestCase):
    def tearDown(self):
        sl.stop_smart_lock_daemon()
        sl.LOCK_THREAD = None

    def test_disabled_does_not_start(self):
        with patch.dict(os.environ, {"JARVIS_SMART_LOCK_ENABLED": "false"}):
            sl.start_smart_lock_daemon()
        self.assertIsNone(sl.LOCK_THREAD)

    def test_enabled_without_target_does_not_start(self):
        with patch.dict(os.environ, {"JARVIS_SMART_LOCK_ENABLED": "true",
                                     "JARVIS_SMART_LOCK_MAC": "", "JARVIS_SMART_LOCK_NAME": ""}):
            sl.start_smart_lock_daemon()
        self.assertIsNone(sl.LOCK_THREAD)

    def test_enabled_with_mac_starts(self):
        with patch.dict(os.environ, {"JARVIS_SMART_LOCK_ENABLED": "true",
                                     "JARVIS_SMART_LOCK_MAC": "AA:BB:CC:DD:EE:FF"}):
            sl.start_smart_lock_daemon()
        self.assertIsNotNone(sl.LOCK_THREAD)
        self.assertTrue(sl.LOCK_THREAD.is_alive())


if __name__ == "__main__":
    unittest.main()
