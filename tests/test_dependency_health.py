"""Tests de la auditoría proactiva de salud de dependencias (core/dependency_health.py).

Sin red real: se mockea la consulta a PyPI. Módulo ligero, ejecutable en local.
"""
import os
import sys
import json
import types
import threading
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.dependency_health as dh


def _meta(version, days_ago):
    """Construye unos metadatos PyPI mínimos con la última publicación hace N días."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    ts = dt.isoformat().replace("+00:00", "Z")
    return {
        "info": {"version": version},
        "releases": {version: [{"upload_time_iso_8601": ts}]},
    }


class TestParseRequirements(unittest.TestCase):
    def test_parses_pinned_and_skips_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "requirements.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comentario\n")
                f.write("flask==3.1.3\n")
                f.write("-r otro.txt\n")
                f.write("\n")
                f.write("requests==2.34.2  # con comentario\n")
                f.write("paquete-sin-pin\n")
            deps = dh.parse_requirements(path)
        names = {d["name"]: d["version"] for d in deps}
        self.assertEqual(names, {"flask": "3.1.3", "requests": "2.34.2"})


class TestIsOutdated(unittest.TestCase):
    def test_older_is_outdated(self):
        self.assertTrue(dh._is_outdated("1.0.0", "2.0.0"))

    def test_equal_not_outdated(self):
        self.assertFalse(dh._is_outdated("2.0.0", "2.0.0"))

    def test_newer_not_outdated(self):
        self.assertFalse(dh._is_outdated("2.1.0", "2.0.0"))

    def test_empty_latest_not_outdated(self):
        self.assertFalse(dh._is_outdated("1.0.0", ""))


class TestLatestReleaseDate(unittest.TestCase):
    def test_picks_most_recent_upload(self):
        old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat().replace("+00:00", "Z")
        new = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
        meta = {"info": {"version": "2.0"}, "releases": {
            "1.0": [{"upload_time_iso_8601": old}],
            "2.0": [{"upload_time_iso_8601": new}],
        }}
        dt = dh._latest_release_date(meta)
        self.assertIsNotNone(dt)
        self.assertLess((datetime.now(timezone.utc) - dt).days, 30)


class TestAnalyzeDependency(unittest.TestCase):
    def test_outdated_flag(self):
        with patch.object(dh, "_fetch_pypi_metadata", return_value=_meta("2.0.0", days_ago=5)):
            r = dh.analyze_dependency({"name": "x", "version": "1.0.0"})
        self.assertTrue(r["outdated"])
        self.assertFalse(r["stale"])
        self.assertEqual(r["latest"], "2.0.0")

    def test_stale_flag(self):
        # Última publicación hace más de STALE_DAYS -> stale.
        with patch.object(dh, "_fetch_pypi_metadata", return_value=_meta("1.0.0", days_ago=dh.STALE_DAYS + 100)):
            r = dh.analyze_dependency({"name": "x", "version": "1.0.0"})
        self.assertTrue(r["stale"])
        self.assertFalse(r["outdated"])  # misma versión
        self.assertGreater(r["days_since_release"], dh.STALE_DAYS)

    def test_healthy_package(self):
        with patch.object(dh, "_fetch_pypi_metadata", return_value=_meta("1.0.0", days_ago=10)):
            r = dh.analyze_dependency({"name": "x", "version": "1.0.0"})
        self.assertFalse(r["outdated"])
        self.assertFalse(r["stale"])
        self.assertIsNone(r["error"])

    def test_pypi_error(self):
        with patch.object(dh, "_fetch_pypi_metadata", return_value=None):
            r = dh.analyze_dependency({"name": "x", "version": "1.0.0"})
        self.assertIsNotNone(r["error"])
        self.assertFalse(r["outdated"])
        self.assertFalse(r["stale"])


class TestRunHealthCheck(unittest.TestCase):
    def test_advisory_when_issues(self):
        deps = [{"name": "a", "version": "1.0.0"}, {"name": "b", "version": "2.0.0"}]

        def fake_analyze(dep, now=None):
            if dep["name"] == "a":
                return {"name": "a", "current": "1.0.0", "latest": "2.0.0", "outdated": True,
                        "stale": False, "last_release": None, "days_since_release": None, "error": None}
            return {"name": "b", "current": "2.0.0", "latest": "2.0.0", "outdated": False,
                    "stale": True, "last_release": "2022-01-01", "days_since_release": 900, "error": None}

        with patch.object(dh, "parse_requirements", return_value=deps), \
             patch.object(dh, "analyze_dependency", side_effect=fake_analyze):
            report = dh.run_dependency_health_check()

        self.assertEqual(report["status"], "advisory")
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["checked"], 2)
        self.assertEqual([o["name"] for o in report["outdated"]], ["a"])
        self.assertEqual([s["name"] for s in report["stale"]], ["b"])
        self.assertEqual(report["errors"], [])

    def test_healthy_when_all_ok(self):
        deps = [{"name": "a", "version": "1.0.0"}]

        def fake_analyze(dep, now=None):
            return {"name": "a", "current": "1.0.0", "latest": "1.0.0", "outdated": False,
                    "stale": False, "last_release": "2026-01-01", "days_since_release": 5, "error": None}

        with patch.object(dh, "parse_requirements", return_value=deps), \
             patch.object(dh, "analyze_dependency", side_effect=fake_analyze):
            report = dh.run_dependency_health_check()
        self.assertEqual(report["status"], "healthy")

    def test_errors_counted(self):
        deps = [{"name": "a", "version": "1.0.0"}]

        def fake_analyze(dep, now=None):
            return {"name": "a", "current": "1.0.0", "latest": None, "outdated": False,
                    "stale": False, "last_release": None, "days_since_release": None, "error": "boom"}

        with patch.object(dh, "parse_requirements", return_value=deps), \
             patch.object(dh, "analyze_dependency", side_effect=fake_analyze):
            report = dh.run_dependency_health_check()
        self.assertEqual(report["status"], "healthy")  # un error no es advisory
        self.assertEqual(report["checked"], 0)
        self.assertEqual(report["errors"], ["a"])


class TestPersist(unittest.TestCase):
    def test_persist_writes_json(self):
        report = {"status": "healthy", "total": 0}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "dependency_health.json")
            self.assertTrue(dh.persist_report(report, path=path))
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), report)


class TestRunAndReport(unittest.TestCase):
    """run_and_report: persiste, emite a GUI y avisa por voz solo en transición."""

    def setUp(self):
        dh.LAST_STATUS = "unknown"

    def _fakes(self, spoken):
        # Inyectamos gui.app y tools.voice falsos para no importar los reales
        # (que arrastran el crash local de OpenSSL).
        fake_gui = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda *a, **k: None)
        )
        fake_voice = types.SimpleNamespace(speak=lambda msg, **k: spoken.append(msg))
        return {"gui.app": fake_gui, "tools.voice": fake_voice}

    def test_healthy_does_not_speak(self):
        spoken = []
        report = {"status": "healthy", "outdated": [], "stale": []}
        with patch.object(dh, "run_dependency_health_check", return_value=report), \
             patch.object(dh, "persist_report", return_value=True), \
             patch.dict(sys.modules, self._fakes(spoken)):
            result = dh.run_and_report()
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(dh.LAST_STATUS, "healthy")
        self.assertEqual(spoken, [])

    def test_advisory_speaks_on_transition(self):
        spoken = []
        report = {"status": "advisory", "outdated": [{"name": "x"}], "stale": []}
        dh.LAST_STATUS = "healthy"
        with patch.object(dh, "run_dependency_health_check", return_value=report), \
             patch.object(dh, "persist_report", return_value=True), \
             patch.dict(sys.modules, self._fakes(spoken)):
            dh.run_and_report()
        self.assertEqual(len(spoken), 1)
        self.assertEqual(dh.LAST_STATUS, "advisory")

    def test_advisory_does_not_repeat(self):
        spoken = []
        report = {"status": "advisory", "outdated": [{"name": "x"}], "stale": []}
        dh.LAST_STATUS = "advisory"  # ya estaba en advisory
        with patch.object(dh, "run_dependency_health_check", return_value=report), \
             patch.object(dh, "persist_report", return_value=True), \
             patch.dict(sys.modules, self._fakes(spoken)):
            dh.run_and_report()
        self.assertEqual(spoken, [])


class TestDaemon(unittest.TestCase):
    """Arranque/parada del daemon (con el bucle mockeado)."""

    def setUp(self):
        dh.HEALTH_THREAD = None
        dh.stop_event.clear()

    def tearDown(self):
        dh.stop_event.set()
        dh.HEALTH_THREAD = None

    def test_disabled_by_env(self):
        with patch.dict(os.environ, {"JARVIS_DEP_HEALTH_ENABLED": "false"}):
            dh.start_dependency_health_daemon()
        self.assertIsNone(dh.HEALTH_THREAD)

    def test_start_stop_idempotent(self):
        keep_alive = threading.Event()

        def fake_loop():
            keep_alive.wait(timeout=5)

        with patch.dict(os.environ, {"JARVIS_DEP_HEALTH_ENABLED": "true"}), \
             patch.object(dh, "_health_loop", side_effect=fake_loop):
            dh.start_dependency_health_daemon()
            self.assertIsNotNone(dh.HEALTH_THREAD)
            first = dh.HEALTH_THREAD
            self.assertTrue(first.is_alive())

            # Segundo arranque es no-op (hilo aún vivo)
            dh.start_dependency_health_daemon()
            self.assertIs(dh.HEALTH_THREAD, first)

            dh.stop_dependency_health_daemon()
            self.assertTrue(dh.stop_event.is_set())

            keep_alive.set()
            first.join(timeout=2)
            self.assertFalse(first.is_alive())


if __name__ == "__main__":
    unittest.main()
