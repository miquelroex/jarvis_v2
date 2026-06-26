"""Tests del Iron Legion / enjambre de drones (core/drones.py)."""
import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.drones as drones


def _reset():
    drones.DRONES.clear()
    drones.MISSIONS.clear()
    drones._counter = 0


def _join_all(timeout=3):
    for d in list(drones.DRONES.values()):
        t = d.get("_thread")
        if t:
            t.join(timeout=timeout)


class TestMissions(unittest.TestCase):
    def setUp(self):
        _reset()

    def test_register_and_list(self):
        drones.register_mission("x", "Misión X", lambda: "ok")
        self.assertEqual(drones.list_missions(), {"x": "Misión X"})

    def test_launch_unknown_returns_none(self):
        self.assertIsNone(drones.launch_drone("noexiste"))


class TestLaunchAndRun(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _join_all()
        _reset()

    def test_drone_completes_with_result(self):
        drones.register_mission("ok", "Tarea OK", lambda: "resultado-123")
        with patch.object(drones, "_notify_done"), patch.object(drones, "_emit"):
            d = drones.launch_drone("ok")
            _join_all()
        self.assertIsNotNone(d)
        final = drones.find_drone(d["short"])
        self.assertEqual(final["status"], "completed")
        self.assertIn("resultado-123", final["result"])

    def test_drone_failure_captured(self):
        def boom():
            raise RuntimeError("explosión")
        drones.register_mission("bad", "Tarea Mala", boom)
        with patch.object(drones, "_notify_done"), patch.object(drones, "_emit"):
            d = drones.launch_drone("bad")
            _join_all()
        final = drones.find_drone(d["short"])
        self.assertEqual(final["status"], "failed")
        self.assertIn("explosión", final["error"])

    def test_direct_fn_launch(self):
        with patch.object(drones, "_notify_done"), patch.object(drones, "_emit"):
            d = drones.launch_drone("custom", label="Directa", fn=lambda: "y")
            _join_all()
        self.assertEqual(d["name"], "Directa")
        self.assertEqual(drones.find_drone(d["short"])["status"], "completed")

    def test_notify_called_on_completion(self):
        drones.register_mission("ok", "T", lambda: "r")
        with patch.object(drones, "_notify_done") as mock_notify, patch.object(drones, "_emit"):
            drones.launch_drone("ok")
            _join_all()
        mock_notify.assert_called_once()

    def test_short_numbers_increment(self):
        drones.register_mission("ok", "T", lambda: "r")
        with patch.object(drones, "_notify_done"), patch.object(drones, "_emit"):
            d1 = drones.launch_drone("ok")
            d2 = drones.launch_drone("ok")
            _join_all()
        self.assertEqual(d1["short"], "01")
        self.assertEqual(d2["short"], "02")


class TestFormat(unittest.TestCase):
    def test_empty(self):
        self.assertIn("No hay drones", drones.format_drones([]))

    def test_counts_and_actives(self):
        ds = [
            {"short": "01", "name": "Tests", "status": "running"},
            {"short": "02", "name": "Limpieza", "status": "completed"},
            {"short": "03", "name": "Deps", "status": "failed"},
        ]
        s = drones.format_drones(ds)
        self.assertIn("1 en curso", s)
        self.assertIn("1 completados", s)
        self.assertIn("1 fallidos", s)
        self.assertIn("01 (Tests)", s)


class TestFindAndClear(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _join_all()
        _reset()

    def test_find_by_short_variants(self):
        drones.register_mission("ok", "T", lambda: "r")
        with patch.object(drones, "_notify_done"), patch.object(drones, "_emit"):
            d = drones.launch_drone("ok")
            _join_all()
        self.assertIsNotNone(drones.find_drone("01"))
        self.assertIsNotNone(drones.find_drone("1"))
        self.assertIsNotNone(drones.find_drone(d["id"]))
        self.assertIsNone(drones.find_drone("99"))

    def test_clear_finished(self):
        drones.register_mission("ok", "T", lambda: "r")
        with patch.object(drones, "_notify_done"), patch.object(drones, "_emit"):
            drones.launch_drone("ok")
            _join_all()
            removed = drones.clear_finished()
        self.assertEqual(removed, 1)
        self.assertEqual(drones.get_drones(), [])


if __name__ == "__main__":
    unittest.main()
