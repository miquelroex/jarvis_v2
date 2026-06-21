"""Tests del briefing matutino (core/morning_briefing.py).

Sin red/git reales: se mockean clima, git y recordatorios.
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.morning_briefing as mb


class TestWeather(unittest.TestCase):
    def test_skipped_without_config(self):
        with patch.dict(os.environ, {"OPENWEATHER_API_KEY": "", "JARVIS_WEATHER_CITY": ""}):
            self.assertIsNone(mb._get_weather())

    def test_formats_weather_line(self):
        payload = json.dumps({
            "weather": [{"description": "cielo claro"}],
            "main": {"temp": 21.4, "feels_like": 20.6},
        }).encode("utf-8")
        fake_resp = MagicMock()
        fake_resp.read.return_value = payload
        fake_cm = MagicMock()
        fake_cm.__enter__.return_value = fake_resp
        with patch.dict(os.environ, {"OPENWEATHER_API_KEY": "k", "JARVIS_WEATHER_CITY": "Madrid,ES"}), \
             patch("core.morning_briefing.urllib.request.urlopen", return_value=fake_cm):
            line = mb._get_weather()
        self.assertIsNotNone(line)
        self.assertIn("Madrid", line)
        self.assertIn("cielo claro", line)
        self.assertIn("21", line)


class TestPendingChanges(unittest.TestCase):
    @patch("core.morning_briefing.subprocess.run")
    def test_counts_modified_files(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=" M a.py\n?? b.py\n M c.py\n")
        self.assertEqual(mb._get_pending_changes(), 3)

    @patch("core.morning_briefing.subprocess.run")
    def test_clean_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        self.assertEqual(mb._get_pending_changes(), 0)

    @patch("core.morning_briefing.subprocess.run", side_effect=OSError("git missing"))
    def test_handles_error(self, mock_run):
        self.assertEqual(mb._get_pending_changes(), 0)


class TestGenerateBriefing(unittest.TestCase):
    def _run(self, weather=None, pending=0, reminders=None):
        with patch.object(mb, "_get_weather", return_value=weather), \
             patch.object(mb, "_get_pending_changes", return_value=pending), \
             patch.object(mb, "_get_today_reminders", return_value=reminders or []):
            return mb.generate_morning_briefing()

    def test_includes_core_sections(self):
        text = self._run(
            weather="El tiempo en Madrid: sol, 20°C.",
            pending=2,
            reminders=[{"target": "llamar al dentista", "next_run": ""}],
        )
        self.assertIn("briefing matutino", text.lower())
        self.assertIn("El tiempo en Madrid", text)
        self.assertIn("2 archivos con cambios", text)
        self.assertIn("llamar al dentista", text)

    def test_clean_and_no_reminders(self):
        text = self._run(weather=None, pending=0, reminders=[])
        self.assertIn("repositorio está limpio", text)
        self.assertIn("No tiene recordatorios programados para hoy", text)

    def test_weather_omitted_when_unavailable(self):
        text = self._run(weather=None, pending=1, reminders=[])
        self.assertIn("1 archivo con cambios", text)
        self.assertNotIn("El tiempo en", text)


if __name__ == "__main__":
    unittest.main()
