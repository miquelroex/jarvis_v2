"""Tests para el mantenimiento de logs (core/log_maintenance.py)."""
import os
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.log_maintenance as lm


def _make_file(path: Path, content: bytes = b"x", age_seconds: int = 0):
    """Crea un archivo y opcionalmente envejece su mtime."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(path, (old, old))
    return path


class TestLogMaintenance(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()
        lm.stop_log_maintenance()

    # ── audio_temp ──────────────────────────────────────────────

    def test_audio_temp_old_files_removed_recent_kept(self):
        old = _make_file(self.logs / "audio_temp" / "old.mp3", age_seconds=48 * 3600)
        recent = _make_file(self.logs / "audio_temp" / "recent.mp3", age_seconds=60)
        removed = lm.cleanup_audio_temp(self.logs)
        self.assertEqual(removed, 1)
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    # ── backups ─────────────────────────────────────────────────

    def test_backups_removed_by_age(self):
        old = _make_file(self.logs / "backup" / "main.py.20250101_000000.bak",
                         age_seconds=60 * 86400)
        recent = _make_file(self.logs / "backup" / "main.py.20260609_120000.bak",
                            age_seconds=3600)
        removed = lm.cleanup_backups(self.logs)
        self.assertEqual(removed, 1)
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_backups_size_cap_removes_oldest_first_keeps_newest(self):
        # Límite de 1 MB; tres backups de ~600 KB cada uno
        with patch.dict(os.environ, {"JARVIS_BACKUP_MAX_MB": "1"}):
            data = b"0" * (600 * 1024)
            oldest = _make_file(self.logs / "backup" / "a.bak", data, age_seconds=3000)
            middle = _make_file(self.logs / "backup" / "b.bak", data, age_seconds=2000)
            newest = _make_file(self.logs / "backup" / "c.bak", data, age_seconds=1000)
            lm.cleanup_backups(self.logs)
            # El más reciente debe conservarse SIEMPRE
            self.assertTrue(newest.exists())
            self.assertFalse(oldest.exists())
            # El tamaño total restante debe ser <= 1 MB + un archivo
            remaining = list((self.logs / "backup").iterdir())
            self.assertLessEqual(len(remaining), 2)
            self.assertFalse(middle.exists() and oldest.exists())

    # ── archivos operativos ─────────────────────────────────────

    def test_operational_files_never_removed(self):
        protected = []
        for name in ["jarvis.lock", "pending_action.json", "known_devices.json",
                     "last_network_scan.json", "terminal_history.json"]:
            protected.append(_make_file(self.logs / name, age_seconds=365 * 86400))
        lm.run_log_maintenance(base_dir=self.logs)
        for f in protected:
            self.assertTrue(f.exists(), f"{f.name} no debería haberse borrado")

    def test_safe_unlink_refuses_operational(self):
        f = _make_file(self.logs / "jarvis.lock")
        self.assertFalse(lm._safe_unlink(f))
        self.assertTrue(f.exists())

    # ── transitorios ────────────────────────────────────────────

    def test_transient_old_removed_recent_kept(self):
        old = _make_file(self.logs / "last_exception.json", age_seconds=30 * 86400)
        recent = _make_file(self.logs / "temp_run.py", age_seconds=60)
        removed = lm.cleanup_transient_files(self.logs)
        self.assertEqual(removed, 1)
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    # ── rotación de model_usage.log ─────────────────────────────

    def test_model_log_rotated_when_oversized(self):
        with patch.dict(os.environ, {"JARVIS_LOG_MAX_MB": "1"}):
            log = _make_file(self.logs / "model_usage.log", b"0" * (2 * 1024 * 1024))
            rotated = lm.rotate_model_usage_log(self.logs)
            self.assertTrue(rotated)
            self.assertFalse(log.exists())
            self.assertTrue((self.logs / "model_usage.log.1").exists())

    def test_model_log_not_rotated_when_small(self):
        log = _make_file(self.logs / "model_usage.log", b"pequeno")
        self.assertFalse(lm.rotate_model_usage_log(self.logs))
        self.assertTrue(log.exists())

    # ── pasada completa y daemon ────────────────────────────────

    def test_run_log_maintenance_returns_summary(self):
        _make_file(self.logs / "audio_temp" / "old.mp3", age_seconds=48 * 3600)
        summary = lm.run_log_maintenance(base_dir=self.logs)
        self.assertEqual(summary["audio_temp_removed"], 1)
        self.assertIn("backups_removed", summary)

    def test_run_log_maintenance_missing_dir_is_noop(self):
        summary = lm.run_log_maintenance(base_dir=self.logs / "no_existe")
        self.assertEqual(summary["audio_temp_removed"], 0)

    def test_daemon_disabled_by_env(self):
        with patch.dict(os.environ, {"JARVIS_LOG_MAINTENANCE_ENABLED": "false"}):
            self.assertFalse(lm.start_log_maintenance())
            self.assertIsNone(lm.MAINTENANCE_THREAD)

    def test_daemon_start_stop(self):
        with patch.dict(os.environ, {"JARVIS_LOG_MAINTENANCE_ENABLED": "true"}):
            with patch.object(lm, "run_log_maintenance", return_value={}):
                self.assertTrue(lm.start_log_maintenance())
                self.assertTrue(lm.MAINTENANCE_THREAD.is_alive())
                lm.stop_log_maintenance()
                self.assertIsNone(lm.MAINTENANCE_THREAD)


if __name__ == "__main__":
    unittest.main()
