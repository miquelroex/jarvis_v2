"""Tests del nivel de amenaza DEFCON (core/threat_level.py)."""
import os
import sys
import types
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.threat_level as tl


def _signals(**overrides):
    s = tl._default_signals()
    s.update(overrides)
    return s


class TestAggregate(unittest.TestCase):

    def test_green_when_nominal(self):
        self.assertEqual(tl._aggregate_threat_level(_signals())["level"], "green")

    def test_amber_high_ram(self):
        self.assertEqual(tl._aggregate_threat_level(_signals(system_ram_percent=85))["level"], "amber")

    def test_amber_stopped_service(self):
        self.assertEqual(tl._aggregate_threat_level(_signals(stopped_services=1))["level"], "amber")

    def test_amber_integrity_warning(self):
        self.assertEqual(tl._aggregate_threat_level(_signals(integrity_status="warning"))["level"], "amber")

    def test_amber_dependency_advisory(self):
        self.assertEqual(tl._aggregate_threat_level(_signals(dependency_status="advisory"))["level"], "amber")

    def test_red_critical_ram(self):
        self.assertEqual(tl._aggregate_threat_level(_signals(system_ram_percent=95))["level"], "red")

    def test_red_safe_mode(self):
        self.assertEqual(tl._aggregate_threat_level(_signals(safe_mode=True))["level"], "red")

    def test_red_integrity_critical(self):
        self.assertEqual(tl._aggregate_threat_level(_signals(integrity_status="critical"))["level"], "red")

    def test_red_unknown_devices(self):
        self.assertEqual(tl._aggregate_threat_level(_signals(unknown_devices=1))["level"], "red")

    def test_violet_ultra_secure(self):
        self.assertEqual(tl._aggregate_threat_level(_signals(ultra_secure=True))["level"], "violet")

    def test_priority_violet_over_red(self):
        # Aunque haya condiciones rojas, ultra-seguro manda (violet).
        result = tl._aggregate_threat_level(_signals(ultra_secure=True, safe_mode=True, system_ram_percent=95))
        self.assertEqual(result["level"], "violet")

    def test_priority_red_over_amber(self):
        result = tl._aggregate_threat_level(_signals(system_ram_percent=95, stopped_services=2))
        self.assertEqual(result["level"], "red")

    def test_reasons_present(self):
        result = tl._aggregate_threat_level(_signals(unknown_devices=2))
        self.assertTrue(any("desconocido" in r for r in result["reasons"]))
        self.assertIn("timestamp", result)


class TestUltraSecureMode(unittest.TestCase):

    def setUp(self):
        tl.set_ultra_secure_mode(False)

    def tearDown(self):
        tl.set_ultra_secure_mode(False)

    def test_flag_toggles(self):
        self.assertFalse(tl.is_ultra_secure_mode())
        tl.set_ultra_secure_mode(True)
        self.assertTrue(tl.is_ultra_secure_mode())

    def test_env_override(self):
        with patch.dict(os.environ, {"JARVIS_ULTRA_SECURE_MODE": "true"}):
            self.assertTrue(tl.is_ultra_secure_mode())


class TestComputeAndEmit(unittest.TestCase):

    def test_compute_uses_gathered_signals(self):
        with patch.object(tl, "_gather_signals", return_value=_signals(unknown_devices=1)):
            self.assertEqual(tl.compute_threat_level()["level"], "red")

    def test_emit_sends_socket_event(self):
        emitted = {}
        fake_gui = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, data: emitted.update({"ev": ev, "data": data}))
        )
        with patch.object(tl, "_gather_signals", return_value=_signals()), \
             patch.dict(sys.modules, {"gui.app": fake_gui}):
            report = tl.emit_threat_level()
        self.assertEqual(emitted["ev"], "threat_level_update")
        self.assertEqual(emitted["data"]["level"], "green")
        self.assertEqual(report["level"], "green")


class TestDaemon(unittest.TestCase):
    def setUp(self):
        tl.THREAT_THREAD = None
        tl.stop_event.clear()
        tl._last_level = None

    def tearDown(self):
        tl.stop_event.set()
        tl.THREAT_THREAD = None

    def test_disabled_by_env(self):
        with patch.dict(os.environ, {"JARVIS_THREAT_LEVEL_ENABLED": "false"}):
            tl.start_threat_level_daemon()
        self.assertIsNone(tl.THREAT_THREAD)

    def test_start_stop_idempotent(self):
        keep_alive = threading.Event()

        def fake_loop():
            keep_alive.wait(timeout=5)

        with patch.dict(os.environ, {"JARVIS_THREAT_LEVEL_ENABLED": "true"}), \
             patch.object(tl, "_threat_loop", side_effect=fake_loop):
            tl.start_threat_level_daemon()
            self.assertIsNotNone(tl.THREAT_THREAD)
            first = tl.THREAT_THREAD
            self.assertTrue(first.is_alive())

            tl.start_threat_level_daemon()  # no-op
            self.assertIs(tl.THREAT_THREAD, first)

            tl.stop_threat_level_daemon()
            self.assertTrue(tl.stop_event.is_set())

            keep_alive.set()
            first.join(timeout=2)
            self.assertFalse(first.is_alive())


if __name__ == "__main__":
    unittest.main()
