"""Tests del HUD Overlay flotante (core/hud_overlay.py).

Sólo se prueba la lógica pura y la puerta de arranque; nunca se instancia Tk
(headless en CI).
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.hud_overlay as hud


class TestFmtUptime(unittest.TestCase):
    def test_minutes_seconds(self):
        self.assertEqual(hud._fmt_uptime(0), "0m 00s")
        self.assertEqual(hud._fmt_uptime(65), "1m 05s")

    def test_hours(self):
        self.assertEqual(hud._fmt_uptime(3700), "1h 01m")

    def test_negative_is_clamped(self):
        self.assertEqual(hud._fmt_uptime(-50), "0m 00s")


class TestBuildTelemetry(unittest.TestCase):
    def _dash(self, **over):
        d = {
            "system": {"system_ram_percent": 42.5, "cpu_percent": 13.0,
                       "process_ram_mb": 311.2, "uptime_seconds": 3700},
            "services": {"running": 7, "stopped": 1, "disabled": 4},
            "usage": {"calls": 9, "tokens": 100, "cost": 0.01},
            "threat_level": "amber",
        }
        d.update(over)
        return d

    def test_maps_fields(self):
        t = hud._build_telemetry(self._dash(), "abre el mapa")
        self.assertEqual(t["ram"], "42.5%")
        self.assertEqual(t["cpu"], "13.0%")
        self.assertEqual(t["proc_ram"], "311.2 MB")
        self.assertEqual(t["uptime"], "1h 01m")
        self.assertEqual(t["services"], "7 activos")
        self.assertEqual(t["calls"], "9")
        self.assertEqual(t["threat"], "AMBER")
        self.assertEqual(t["threat_color"], hud._THREAT_COLORS["amber"])
        self.assertEqual(t["last_command"], "abre el mapa")

    def test_truncates_long_command(self):
        long_cmd = "x" * 100
        t = hud._build_telemetry(self._dash(), long_cmd)
        self.assertEqual(len(t["last_command"]), 52)

    def test_empty_dashboard_defaults(self):
        t = hud._build_telemetry({}, None)
        self.assertEqual(t["ram"], "0%")
        self.assertEqual(t["threat"], "GREEN")
        self.assertEqual(t["last_command"], "—")


class TestIsAlert(unittest.TestCase):
    def test_red_threat_alerts(self):
        self.assertTrue(hud._is_alert({"threat_level": "red"}))

    def test_violet_threat_alerts(self):
        self.assertTrue(hud._is_alert({"threat_level": "violet"}))

    def test_high_ram_alerts(self):
        self.assertTrue(hud._is_alert({"system": {"system_ram_percent": 95}}))

    def test_normal_no_alert(self):
        self.assertFalse(hud._is_alert({"threat_level": "green", "system": {"system_ram_percent": 40}}))

    def test_bad_ram_value_no_crash(self):
        self.assertFalse(hud._is_alert({"system": {"system_ram_percent": None}}))


class TestLastCommand(unittest.TestCase):
    def test_set_and_get(self):
        hud.set_last_command("  hola  ")
        self.assertEqual(hud.get_last_command(), "hola")

    def test_empty_becomes_dash(self):
        hud.set_last_command("")
        self.assertEqual(hud.get_last_command(), "—")


class TestStartGate(unittest.TestCase):
    def tearDown(self):
        hud.stop_hud_overlay()
        hud.HUD_THREAD = None

    def test_disabled_does_not_start(self):
        with patch.dict(os.environ, {"JARVIS_HUD_OVERLAY_ENABLED": "false"}):
            hud.start_hud_overlay()
        self.assertIsNone(hud.HUD_THREAD)


if __name__ == "__main__":
    unittest.main()
