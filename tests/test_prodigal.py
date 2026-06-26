"""Tests del Protocolo Hijo Pródigo (core/prodigal.py)."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.prodigal as prodigal


class TestFmtAbsence(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(prodigal._fmt_absence(1), "1 minuto")
        self.assertEqual(prodigal._fmt_absence(45), "45 minutos")

    def test_hours(self):
        self.assertEqual(prodigal._fmt_absence(60), "1 hora")
        self.assertEqual(prodigal._fmt_absence(150), "2 horas y 30 minutos")

    def test_days(self):
        self.assertEqual(prodigal._fmt_absence(60 * 24 * 2), "2 días")


class TestBuildWelcomeBack(unittest.TestCase):
    def test_full_context(self):
        ctx = {"absence_minutes": 120, "new_commits": 3, "dirty_count": 2,
               "branch": "main", "devices_count": 5, "pending_count": 1, "threat_level": "amber"}
        text = prodigal.build_welcome_back(ctx)
        self.assertIn("Bienvenido de nuevo", text)
        self.assertIn("3 commits nuevos en main", text)
        self.assertIn("2 archivos con cambios", text)
        self.assertIn("5 dispositivos", text)
        self.assertIn("1 nota pendiente", text)
        self.assertIn("ámbar", text)

    def test_no_news(self):
        ctx = {"absence_minutes": 30, "new_commits": 0, "dirty_count": 0,
               "devices_count": 0, "pending_count": 0, "threat_level": "green"}
        text = prodigal.build_welcome_back(ctx)
        self.assertIn("sin novedades", text)

    def test_singular_plurals(self):
        ctx = {"absence_minutes": 61, "new_commits": 1, "dirty_count": 1,
               "branch": "dev", "devices_count": 1, "pending_count": 1, "threat_level": "green"}
        text = prodigal.build_welcome_back(ctx)
        self.assertIn("1 commit nuevo en dev", text)
        self.assertIn("1 archivo con cambios", text)
        self.assertIn("1 dispositivo en la red", text)

    def test_green_threat_not_mentioned(self):
        ctx = {"absence_minutes": 10, "new_commits": 1, "threat_level": "green"}
        self.assertNotIn("amenaza", prodigal.build_welcome_back(ctx))


class TestGetCatchup(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "checkin.txt"
        self._patch = patch.object(prodigal, "LAST_CHECKIN_FILE", self.tmp)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        if self.tmp.exists():
            self.tmp.unlink()

    def test_assembles_and_updates_checkin(self):
        with patch.object(prodigal, "_count_new_commits", return_value=2), \
             patch.object(prodigal, "_get_git_state", return_value={"is_repo": True, "branch": "main", "dirty_count": 4}), \
             patch.object(prodigal, "_get_devices_count", return_value=3), \
             patch.object(prodigal, "_get_pending_count", return_value=0), \
             patch.object(prodigal, "_get_threat_level", return_value="green"):
            text = prodigal.get_catchup()
        self.assertIn("2 commits", text)
        self.assertIn("4 archivos", text)
        # El check-in se ha persistido.
        self.assertTrue(self.tmp.exists())

    def test_default_lookback_when_no_checkin(self):
        # Sin fichero, el lookback por defecto es ~8h.
        since = prodigal._read_last_checkin()
        delta_h = (datetime.now() - since).total_seconds() / 3600
        self.assertAlmostEqual(delta_h, prodigal.DEFAULT_LOOKBACK_HOURS, delta=0.1)

    def test_reads_persisted_checkin(self):
        ts = datetime.now() - timedelta(hours=2)
        self.tmp.write_text(ts.isoformat(), encoding="utf-8")
        since = prodigal._read_last_checkin()
        self.assertAlmostEqual((datetime.now() - since).total_seconds() / 3600, 2, delta=0.1)


if __name__ == "__main__":
    unittest.main()