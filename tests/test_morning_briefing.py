"""Tests del briefing matutino (core/morning_briefing.py).

Sin red/git reales: se mockean clima, git y recordatorios.
"""
import os
import sys
import json
import types
import threading
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.morning_briefing as mb


class TestWeather(unittest.TestCase):
    def test_skipped_without_config(self):
        with patch.dict(os.environ, {"OPENWEATHER_API_KEY": "", "OPENWEATHERMAP_API_KEY": "",
                                     "JARVIS_WEATHER_CITY": ""}):
            self.assertIsNone(mb._get_weather())

    def test_accepts_openweathermap_var_name(self):
        # La clave también se reconoce bajo OPENWEATHERMAP_API_KEY (con 'MAP').
        payload = json.dumps({
            "weather": [{"description": "nubes"}],
            "main": {"temp": 15.0, "feels_like": 14.0},
        }).encode("utf-8")
        fake_resp = MagicMock()
        fake_resp.read.return_value = payload
        fake_cm = MagicMock()
        fake_cm.__enter__.return_value = fake_resp
        with patch.dict(os.environ, {"OPENWEATHER_API_KEY": "", "OPENWEATHERMAP_API_KEY": "k",
                                     "JARVIS_WEATHER_CITY": "Barcelona,ES"}), \
             patch("core.morning_briefing.urllib.request.urlopen", return_value=fake_cm):
            line = mb._get_weather()
        self.assertIsNotNone(line)
        self.assertIn("Barcelona", line)

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


class TestDeliverBriefing(unittest.TestCase):
    def _fake_voice(self, spoken):
        return {"tools.voice": types.SimpleNamespace(speak=lambda msg, **k: spoken.append(msg))}

    def test_voice_only(self):
        spoken = []
        with patch.object(mb, "generate_morning_briefing", return_value="BRIEF"), \
             patch.dict(sys.modules, self._fake_voice(spoken)):
            res = mb.deliver_briefing(channel="voice")
        self.assertTrue(res["voice"])
        self.assertFalse(res["telegram"])
        self.assertEqual(spoken, ["BRIEF"])

    def test_telegram_only(self):
        with patch.object(mb, "generate_morning_briefing", return_value="BRIEF"), \
             patch.object(mb, "_send_to_telegram", return_value=True):
            res = mb.deliver_briefing(channel="telegram")
        self.assertTrue(res["telegram"])
        self.assertFalse(res["voice"])

    def test_telegram_skipped_without_config(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_USER_ID": ""}):
            self.assertFalse(mb._send_to_telegram("hola"))


class TestBriefingDaemon(unittest.TestCase):
    def setUp(self):
        mb.BRIEFING_THREAD = None
        mb.stop_event.clear()

    def tearDown(self):
        mb.stop_event.set()
        mb.BRIEFING_THREAD = None

    def test_disabled_by_env(self):
        with patch.dict(os.environ, {"JARVIS_MORNING_BRIEFING_ENABLED": "false"}):
            mb.start_morning_briefing_daemon()
        self.assertIsNone(mb.BRIEFING_THREAD)

    def test_start_stop_idempotent(self):
        keep_alive = threading.Event()

        def fake_loop():
            keep_alive.wait(timeout=5)

        with patch.dict(os.environ, {"JARVIS_MORNING_BRIEFING_ENABLED": "true"}), \
             patch.object(mb, "_briefing_loop", side_effect=fake_loop):
            mb.start_morning_briefing_daemon()
            self.assertIsNotNone(mb.BRIEFING_THREAD)
            first = mb.BRIEFING_THREAD
            self.assertTrue(first.is_alive())

            mb.start_morning_briefing_daemon()  # no-op
            self.assertIs(mb.BRIEFING_THREAD, first)

            mb.stop_morning_briefing_daemon()
            self.assertTrue(mb.stop_event.is_set())

            keep_alive.set()
            first.join(timeout=2)
            self.assertFalse(first.is_alive())


if __name__ == "__main__":
    unittest.main()
