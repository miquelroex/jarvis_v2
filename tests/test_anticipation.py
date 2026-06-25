"""Tests del motor de Anticipación (core/anticipation.py)."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.anticipation as ant


def _ev(action, hour, weekday, ts=None):
    return {"action": action, "hour": hour, "weekday": weekday, "ts": ts}


class TestHourDistance(unittest.TestCase):
    def test_wraps(self):
        self.assertEqual(ant._hour_distance(23, 0), 1)
        self.assertEqual(ant._hour_distance(1, 23), 2)
        self.assertEqual(ant._hour_distance(9, 9), 0)


class TestPredict(unittest.TestCase):
    def test_ranks_by_frequency_in_hour_window(self):
        now = datetime(2026, 6, 25, 9, 0)  # jueves 09:00 (weekday=3)
        events = [
            _ev("app:code", 9, 3), _ev("app:code", 9, 3), _ev("app:code", 8, 3),
            _ev("web:gmail", 9, 3),
            _ev("app:spotify", 15, 3),  # fuera de la ventana horaria
        ]
        out = ant.predict(events, now, min_score=1)
        actions = [o["action"] for o in out]
        self.assertEqual(actions[0], "app:code")
        self.assertIn("web:gmail", actions)
        self.assertNotIn("app:spotify", actions)

    def test_weekday_match_weighs_more(self):
        now = datetime(2026, 6, 25, 9, 0)  # weekday 3
        events = [
            _ev("a", 9, 3),            # mismo día -> peso 2
            _ev("b", 9, 0), _ev("b", 9, 1),  # otros días -> peso 1 cada uno
        ]
        out = ant.predict(events, now, min_score=1)
        # 'a' (2) empata con 'b' (2): ambos presentes, 'a' primero por orden de inserción
        scores = {o["action"]: o["score"] for o in out}
        self.assertEqual(scores["a"], 2)
        self.assertEqual(scores["b"], 2)

    def test_min_score_filters(self):
        now = datetime(2026, 6, 25, 9, 0)
        events = [_ev("rare", 9, 3)]  # score 2
        self.assertEqual(ant.predict(events, now, min_score=3), [])
        self.assertTrue(ant.predict(events, now, min_score=2))

    def test_excludes_recent(self):
        now = datetime(2026, 6, 25, 9, 0)
        events = [_ev("app:code", 9, 3)] * 3
        out = ant.predict(events, now, min_score=1, recent_exclude={"app:code"})
        self.assertEqual(out, [])

    def test_top_k(self):
        now = datetime(2026, 6, 25, 9, 0)
        events = []
        for a in ("a", "b", "c", "d"):
            events += [_ev(a, 9, 3)] * 3
        out = ant.predict(events, now, min_score=1, top_k=2)
        self.assertEqual(len(out), 2)


class TestPhrase(unittest.TestCase):
    def test_app_and_web(self):
        self.assertEqual(ant._phrase("app:code"), "abrir code")
        self.assertEqual(ant._phrase("web:gmail"), "abrir gmail")

    def test_plain(self):
        self.assertEqual(ant._phrase("hacer algo"), "hacer algo")


class TestRecordAndLoad(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "anticipation_log.jsonl"
        self._patch = patch.object(ant, "LOG_FILE", self.tmp)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        if self.tmp.exists():
            self.tmp.unlink()

    def test_record_then_load(self):
        ant.record_action("app:code")
        ant.record_action("web:gmail")
        events = ant._load_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["action"], "app:code")
        self.assertIn("hour", events[0])

    def test_record_empty_ignored(self):
        ant.record_action("  ")
        self.assertEqual(ant._load_events(), [])

    def test_recent_actions(self):
        now = datetime(2026, 6, 25, 9, 0)
        events = [
            {"action": "x", "ts": (now - timedelta(minutes=10)).isoformat()},
            {"action": "y", "ts": (now - timedelta(hours=5)).isoformat()},
        ]
        recent = ant._recent_actions(events, now, within_hours=1)
        self.assertIn("x", recent)
        self.assertNotIn("y", recent)


class TestDaemon(unittest.TestCase):
    def setUp(self):
        ant.stop_anticipation_daemon()
        if ant.ANTICIPATE_THREAD is not None and ant.ANTICIPATE_THREAD.is_alive():
            ant.ANTICIPATE_THREAD.join(timeout=2)
        ant.ANTICIPATE_THREAD = None
        ant.stop_event.clear()

    def tearDown(self):
        ant.stop_anticipation_daemon()
        ant.ANTICIPATE_THREAD = None

    def test_disabled_does_not_start(self):
        with patch.dict(os.environ, {"JARVIS_ANTICIPATION_ENABLED": "false"}):
            ant.start_anticipation_daemon()
        self.assertIsNone(ant.ANTICIPATE_THREAD)

    def test_enabled_starts(self):
        with patch.dict(os.environ, {"JARVIS_ANTICIPATION_ENABLED": "true"}):
            ant.start_anticipation_daemon()
        self.assertIsNotNone(ant.ANTICIPATE_THREAD)
        self.assertTrue(ant.ANTICIPATE_THREAD.is_alive())


if __name__ == "__main__":
    unittest.main()
