"""Tests para el resumen nocturno (core/daily_digest.py)."""
import os
import sys
import types
import threading
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.daily_digest as dd


FAKE_TASKS = [
    {
        "name": "recordatorio_pizza",
        "task_type": "reminder",
        "target": "sacar la pizza del horno",
        "next_run": "2026-06-10T21:00:00+00:00",
    },
    {
        "name": "monitor_blog",
        "task_type": "url_monitor",
        "target": "https://example.com",
        "next_run": "2026-06-10T22:00:00+00:00",
    },
]


class TestDailyDigest(unittest.TestCase):

    # ── git ─────────────────────────────────────────────────────

    @patch("core.daily_digest.subprocess.run")
    def test_get_today_commits_parses_lines(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="abc123 fix: bug\ndef456 feat: digest\n"
        )
        commits = dd._get_today_commits()
        self.assertEqual(len(commits), 2)
        self.assertIn("fix: bug", commits[0])
        # Solo lectura: debe usar git log
        self.assertEqual(mock_run.call_args[0][0][:2], ["git", "log"])

    @patch("core.daily_digest.subprocess.run")
    def test_get_today_commits_handles_non_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        self.assertEqual(dd._get_today_commits(), [])

    @patch("core.daily_digest.subprocess.run", side_effect=OSError("git missing"))
    def test_get_today_commits_handles_exception(self, mock_run):
        self.assertEqual(dd._get_today_commits(), [])

    # ── digest completo ─────────────────────────────────────────

    @patch("core.daily_digest._get_services_summary", return_value="5 servicios activos")
    @patch("core.daily_digest._get_today_memories", return_value=[])
    @patch("core.daily_digest._get_active_tasks", return_value=FAKE_TASKS)
    @patch("core.daily_digest._get_today_commits", return_value=["abc123 feat: digest"])
    def test_digest_includes_all_sections(self, *mocks):
        digest = dd.generate_daily_digest()
        self.assertIn("Resumen del día", digest)
        self.assertIn("1 commits", digest)
        self.assertIn("sacar la pizza del horno", digest)
        self.assertIn("monitores de URL", digest)
        self.assertIn("5 servicios activos", digest)
        self.assertIn("Próximo paso programado", digest)

    @patch("core.daily_digest._get_services_summary", return_value="ok")
    @patch("core.daily_digest._get_today_memories", return_value=[])
    @patch("core.daily_digest._get_active_tasks", return_value=[])
    @patch("core.daily_digest._get_today_commits", return_value=[])
    def test_digest_empty_day_is_graceful(self, *mocks):
        digest = dd.generate_daily_digest()
        self.assertIn("no se han registrado commits", digest)
        self.assertIn("No hay recordatorios pendientes", digest)
        self.assertIn("No hay próximos pasos programados", digest)

    @patch("core.daily_digest._get_services_summary", return_value="ok")
    @patch("core.daily_digest._get_today_memories")
    @patch("core.daily_digest._get_active_tasks", return_value=[])
    @patch("core.daily_digest._get_today_commits", return_value=[])
    def test_digest_includes_today_notes(self, mock_commits, mock_tasks, mock_mem, mock_srv):
        mock_mem.return_value = [{"content": "comprar filamento", "created_at": "2026-06-10"}]
        digest = dd.generate_daily_digest()
        self.assertIn("comprar filamento", digest)

    # ── telegram ────────────────────────────────────────────────

    def test_telegram_skipped_without_config(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_USER_ID": ""}):
            self.assertFalse(dd.send_digest_to_telegram("hola"))

    # ── fast command ────────────────────────────────────────────

    @patch("core.daily_digest.generate_daily_digest", return_value="RESUMEN_TEST")
    def test_fast_command_triggers_digest(self, mock_gen):
        from core.fast_commands import handle_fast_command
        res = handle_fast_command("dame el resumen del día")
        self.assertEqual(res, "RESUMEN_TEST")

    @patch("core.daily_digest.generate_daily_digest", return_value="RESUMEN_TEST")
    def test_fast_command_nocturno_variant(self, mock_gen):
        from core.fast_commands import handle_fast_command
        res = handle_fast_command("resumen nocturno por favor")
        self.assertEqual(res, "RESUMEN_TEST")


class TestShouldDeliverNow(unittest.TestCase):
    def test_fires_at_target_hour(self):
        now = datetime(2026, 6, 21, 22, 0, 0)
        self.assertTrue(dd._should_deliver_now(now, 22, None))

    def test_skips_wrong_hour(self):
        now = datetime(2026, 6, 21, 21, 0, 0)
        self.assertFalse(dd._should_deliver_now(now, 22, None))

    def test_skips_if_already_delivered_today(self):
        now = datetime(2026, 6, 21, 22, 0, 0)
        self.assertFalse(dd._should_deliver_now(now, 22, now.date()))

    def test_fires_again_next_day(self):
        now = datetime(2026, 6, 22, 22, 0, 0)
        yesterday = datetime(2026, 6, 21, 22, 0, 0).date()
        self.assertTrue(dd._should_deliver_now(now, 22, yesterday))


class TestDeliverDigest(unittest.TestCase):
    def _fake_voice(self, spoken):
        # Inyectamos tools.voice falso para no importar el real (crash local OpenSSL).
        return {"tools.voice": types.SimpleNamespace(speak=lambda msg, **k: spoken.append(msg))}

    def test_voice_only(self):
        spoken = []
        with patch.object(dd, "generate_daily_digest", return_value="RESUMEN"), \
             patch.dict(sys.modules, self._fake_voice(spoken)):
            res = dd.deliver_digest(channel="voice")
        self.assertTrue(res["voice"])
        self.assertFalse(res["telegram"])
        self.assertEqual(spoken, ["RESUMEN"])

    def test_telegram_only(self):
        with patch.object(dd, "generate_daily_digest", return_value="RESUMEN"), \
             patch.object(dd, "send_digest_to_telegram", return_value=True):
            res = dd.deliver_digest(channel="telegram")
        self.assertTrue(res["telegram"])
        self.assertFalse(res["voice"])

    def test_both_channels(self):
        spoken = []
        with patch.object(dd, "generate_daily_digest", return_value="RESUMEN"), \
             patch.object(dd, "send_digest_to_telegram", return_value=True), \
             patch.dict(sys.modules, self._fake_voice(spoken)):
            res = dd.deliver_digest(channel="both")
        self.assertTrue(res["voice"])
        self.assertTrue(res["telegram"])


class TestDigestDaemon(unittest.TestCase):
    def setUp(self):
        dd.DIGEST_THREAD = None
        dd.stop_event.clear()

    def tearDown(self):
        dd.stop_event.set()
        dd.DIGEST_THREAD = None

    def test_disabled_by_env(self):
        with patch.dict(os.environ, {"JARVIS_DAILY_DIGEST_ENABLED": "false"}):
            dd.start_daily_digest_daemon()
        self.assertIsNone(dd.DIGEST_THREAD)

    def test_start_stop_idempotent(self):
        keep_alive = threading.Event()

        def fake_loop():
            keep_alive.wait(timeout=5)

        with patch.dict(os.environ, {"JARVIS_DAILY_DIGEST_ENABLED": "true"}), \
             patch.object(dd, "_digest_loop", side_effect=fake_loop):
            dd.start_daily_digest_daemon()
            self.assertIsNotNone(dd.DIGEST_THREAD)
            first = dd.DIGEST_THREAD
            self.assertTrue(first.is_alive())

            dd.start_daily_digest_daemon()  # no-op
            self.assertIs(dd.DIGEST_THREAD, first)

            dd.stop_daily_digest_daemon()
            self.assertTrue(dd.stop_event.is_set())

            keep_alive.set()
            first.join(timeout=2)
            self.assertFalse(first.is_alive())


if __name__ == "__main__":
    unittest.main()
