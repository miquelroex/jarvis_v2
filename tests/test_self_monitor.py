"""Tests del dashboard de salud (core/self_monitor.py)."""
import os
import sys
import types
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.self_monitor as sm


class TestServicesSummary(unittest.TestCase):
    def test_counts_by_state(self):
        fake = {"a": "running", "b": "running", "c": "stopped", "d": "disabled"}
        fake_services = types.SimpleNamespace(get_services_status=lambda: fake)
        with patch.dict(sys.modules, {"core.services": fake_services}):
            s = sm._get_services_summary()
        self.assertEqual(s, {"running": 2, "stopped": 1, "disabled": 1})

    def test_defensive_on_error(self):
        fake_services = types.SimpleNamespace(
            get_services_status=lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        with patch.dict(sys.modules, {"core.services": fake_services}):
            s = sm._get_services_summary()
        self.assertEqual(s, {"running": 0, "stopped": 0, "disabled": 0})


class TestDashboard(unittest.TestCase):
    def test_aggregates_all_sections(self):
        with patch.object(sm, "_get_usage", return_value={"calls": 3, "tokens": 1200, "cost": 0.0042}), \
             patch.object(sm, "_get_services_summary", return_value={"running": 8, "stopped": 1, "disabled": 4}), \
             patch.object(sm, "_get_system_metrics", return_value={
                 "system_ram_percent": 55.0, "cpu_percent": 12.0,
                 "process_ram_mb": 180.0, "uptime_seconds": 3600}), \
             patch.object(sm, "_get_threat_level", return_value="amber"):
            d = sm.get_health_dashboard()
        self.assertEqual(d["usage"]["calls"], 3)
        self.assertEqual(d["services"]["running"], 8)
        self.assertEqual(d["system"]["uptime_seconds"], 3600)
        self.assertEqual(d["threat_level"], "amber")
        self.assertIn("timestamp", d)

    def test_emit_sends_socket_event(self):
        emitted = {}
        fake_gui = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, data: emitted.update({"ev": ev}))
        )
        with patch.object(sm, "get_health_dashboard", return_value={"x": 1}), \
             patch.dict(sys.modules, {"gui.app": fake_gui}):
            sm.emit_health_dashboard()
        self.assertEqual(emitted["ev"], "health_dashboard_update")


class TestDaemon(unittest.TestCase):
    def setUp(self):
        sm.MONITOR_THREAD = None
        sm.stop_event.clear()

    def tearDown(self):
        sm.stop_event.set()
        sm.MONITOR_THREAD = None

    def test_disabled_by_env(self):
        with patch.dict(os.environ, {"JARVIS_SELF_MONITOR_ENABLED": "false"}):
            sm.start_self_monitor_daemon()
        self.assertIsNone(sm.MONITOR_THREAD)

    def test_start_stop_idempotent(self):
        keep_alive = threading.Event()

        def fake_loop():
            keep_alive.wait(timeout=5)

        with patch.dict(os.environ, {"JARVIS_SELF_MONITOR_ENABLED": "true"}), \
             patch.object(sm, "_monitor_loop", side_effect=fake_loop):
            sm.start_self_monitor_daemon()
            self.assertIsNotNone(sm.MONITOR_THREAD)
            first = sm.MONITOR_THREAD
            self.assertTrue(first.is_alive())

            sm.start_self_monitor_daemon()  # no-op
            self.assertIs(sm.MONITOR_THREAD, first)

            sm.stop_self_monitor_daemon()
            self.assertTrue(sm.stop_event.is_set())
            keep_alive.set()
            first.join(timeout=2)
            self.assertFalse(first.is_alive())


if __name__ == "__main__":
    unittest.main()
