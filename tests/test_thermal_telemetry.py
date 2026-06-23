"""Tests de la telemetría térmica de hardware (core/thermal_telemetry.py)."""
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.thermal_telemetry as tt


class TestBuildCoreList(unittest.TestCase):
    def test_indices_and_rounding(self):
        cores = tt._build_core_list([0.0, 24.234, 100.0])
        self.assertEqual(cores, [
            {"id": 0, "load": 0.0},
            {"id": 1, "load": 24.2},
            {"id": 2, "load": 100.0},
        ])

    def test_empty(self):
        self.assertEqual(tt._build_core_list([]), [])
        self.assertEqual(tt._build_core_list(None), [])

    def test_bad_values_default_zero(self):
        cores = tt._build_core_list([None, "x", 5])
        self.assertEqual([c["load"] for c in cores], [0.0, 0.0, 5.0])


class TestDeciKelvin(unittest.TestCase):
    def test_conversion(self):
        # 3032 deciK = 303.2K = 30.05°C
        self.assertEqual(tt._celsius_from_decikelvin(3032), 30.1)
        self.assertEqual(tt._celsius_from_decikelvin(2982), 25.1)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_structure_and_overall(self):
        with patch.object(tt, "_read_per_core_load", return_value=[10.0, 30.0, 50.0, 10.0]), \
             patch.object(tt, "_read_ram_percent", return_value=42.0), \
             patch.object(tt, "_read_cpu_temperature", return_value=None), \
             patch.object(tt, "_read_battery", return_value=None):
            snap = tt.get_thermal_snapshot()
        self.assertEqual(len(snap["cores"]), 4)
        self.assertEqual(snap["cpu_overall"], 25.0)
        self.assertEqual(snap["ram_percent"], 42.0)
        self.assertIsNone(snap["cpu_temp"])
        self.assertIsNone(snap["battery"])
        self.assertIn("timestamp", snap)

    def test_overall_zero_when_no_cores(self):
        with patch.object(tt, "_read_per_core_load", return_value=[]), \
             patch.object(tt, "_read_ram_percent", return_value=0.0), \
             patch.object(tt, "_read_cpu_temperature", return_value=None), \
             patch.object(tt, "_read_battery", return_value=None):
            snap = tt.get_thermal_snapshot()
        self.assertEqual(snap["cpu_overall"], 0.0)


class TestReadBattery(unittest.TestCase):
    def test_no_battery_returns_none(self):
        fake_psutil = types.SimpleNamespace(sensors_battery=lambda: None)
        with patch.dict(sys.modules, {"psutil": fake_psutil}):
            self.assertIsNone(tt._read_battery())

    def test_battery_mapped(self):
        b = types.SimpleNamespace(percent=88.0, power_plugged=True)
        fake_psutil = types.SimpleNamespace(sensors_battery=lambda: b)
        with patch.dict(sys.modules, {"psutil": fake_psutil}):
            self.assertEqual(tt._read_battery(), {"percent": 88.0, "plugged": True})


class TestEmit(unittest.TestCase):
    def test_emits_thermal_update(self):
        emitted = []
        fake = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: emitted.append((ev, a))))
        with patch.dict(sys.modules, {"gui.app": fake}):
            tt._emit({"cpu_overall": 1})
        self.assertEqual(emitted[0][0], "thermal_update")

    def test_no_emit_without_gui(self):
        saved = sys.modules.pop("gui.app", None)
        try:
            tt._emit({"x": 1})  # no debe lanzar
        finally:
            if saved is not None:
                sys.modules["gui.app"] = saved


class TestDaemon(unittest.TestCase):
    def tearDown(self):
        tt.stop_thermal_telemetry_daemon()
        tt.THERMAL_THREAD = None

    def test_disabled_does_not_start(self):
        with patch.dict(os.environ, {"JARVIS_THERMAL_TELEMETRY_ENABLED": "false"}):
            tt.start_thermal_telemetry_daemon()
        self.assertIsNone(tt.THERMAL_THREAD)

    def test_enabled_starts(self):
        with patch.dict(os.environ, {"JARVIS_THERMAL_TELEMETRY_ENABLED": "true"}), \
             patch.object(tt, "_read_per_core_load", return_value=[]):
            tt.start_thermal_telemetry_daemon()
        self.assertIsNotNone(tt.THERMAL_THREAD)
        self.assertTrue(tt.THERMAL_THREAD.is_alive())


if __name__ == "__main__":
    unittest.main()
