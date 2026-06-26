"""Tests del Rastreador de Productividad (core/productivity.py)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.productivity as prod


class TestClassify(unittest.TestCase):
    def test_browser(self):
        self.assertEqual(prod.classify_activity("chrome"), "Navegador")
        self.assertEqual(prod.classify_activity("msedge", "x"), "Navegador")

    def test_editor_with_repo(self):
        self.assertEqual(prod.classify_activity("code", "main.py", "jarvis"), "Proyecto: jarvis")

    def test_editor_without_repo(self):
        self.assertEqual(prod.classify_activity("code"), "Código")

    def test_terminal_and_comms(self):
        self.assertEqual(prod.classify_activity("powershell"), "Terminal")
        self.assertEqual(prod.classify_activity("discord"), "Comunicación")

    def test_other_capitalized(self):
        self.assertEqual(prod.classify_activity("spotify"), "Spotify")

    def test_unknown_is_otros(self):
        self.assertEqual(prod.classify_activity(""), "Otros")
        self.assertEqual(prod.classify_activity("Sistema"), "Otros")


class TestAddTime(unittest.TestCase):
    def test_accumulates(self):
        t = {}
        prod.add_time(t, "A", 30)
        prod.add_time(t, "A", 15)
        prod.add_time(t, "B", 10)
        self.assertEqual(t, {"A": 45, "B": 10})

    def test_ignores_invalid(self):
        t = {}
        prod.add_time(t, "", 30)
        prod.add_time(t, "A", 0)
        prod.add_time(t, "A", -5)
        self.assertEqual(t, {})


class TestFmtAndSummary(unittest.TestCase):
    def test_fmt_duration(self):
        self.assertEqual(prod._fmt_duration(45), "45s")
        self.assertEqual(prod._fmt_duration(120), "2m")
        self.assertEqual(prod._fmt_duration(3700), "1h 01m")

    def test_summary_sorted_with_total(self):
        s = prod.format_summary({"Navegador": 600, "Proyecto: jarvis": 7800})
        self.assertIn("Proyecto: jarvis 2h 10m", s)
        self.assertIn("Navegador 10m", s)
        # El proyecto (más tiempo) va antes que el navegador.
        self.assertLess(s.index("jarvis"), s.index("Navegador"))
        self.assertIn("2h 20m", s)  # total

    def test_summary_empty(self):
        self.assertIn("Aún no he registrado", prod.format_summary({}))

    def test_summary_top_n(self):
        tally = {f"L{i}": (i + 1) * 60 for i in range(10)}
        s = prod.format_summary(tally, top_n=3)
        # Solo los 3 mayores (L9, L8, L7).
        self.assertIn("L9", s)
        self.assertNotIn("L0", s)


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._patch = patch.object(prod, "DATA_DIR", self.tmp)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_record_then_summary(self):
        prod.record("Terminal", 30)
        prod.record("Terminal", 30)
        prod.record("Navegador", 60)
        summary = prod.get_today_summary()
        self.assertIn("Terminal 1m", summary)
        self.assertIn("Navegador 1m", summary)

    def test_load_empty_when_missing(self):
        self.assertEqual(prod._load_today(), {})


class TestTodayPath(unittest.TestCase):
    def test_explicit_day_is_respected(self):
        # Pasar un día explícito NO debe ser sobrescrito por la fecha de hoy.
        p = prod._today_path("2026-01-15")
        self.assertTrue(str(p).endswith("2026-01-15.json"))

    def test_default_day_is_today(self):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(today, str(prod._today_path()))


class TestDaemon(unittest.TestCase):
    def setUp(self):
        prod.stop_productivity_daemon()
        if prod.PRODUCTIVITY_THREAD is not None and prod.PRODUCTIVITY_THREAD.is_alive():
            prod.PRODUCTIVITY_THREAD.join(timeout=2)
        prod.PRODUCTIVITY_THREAD = None
        prod.stop_event.clear()

    def tearDown(self):
        prod.stop_productivity_daemon()
        prod.PRODUCTIVITY_THREAD = None

    def test_disabled_does_not_start(self):
        with patch.dict(os.environ, {"JARVIS_PRODUCTIVITY_ENABLED": "false"}):
            prod.start_productivity_daemon()
        self.assertIsNone(prod.PRODUCTIVITY_THREAD)

    def test_enabled_starts(self):
        with patch.dict(os.environ, {"JARVIS_PRODUCTIVITY_ENABLED": "true"}):
            prod.start_productivity_daemon()
        self.assertIsNotNone(prod.PRODUCTIVITY_THREAD)
        self.assertTrue(prod.PRODUCTIVITY_THREAD.is_alive())


if __name__ == "__main__":
    unittest.main()
