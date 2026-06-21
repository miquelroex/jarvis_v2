"""Tests de la auditoría proactiva de salud de dependencias (core/dependency_health.py).

Sin red real: se mockea la consulta a PyPI. Módulo ligero, ejecutable en local.
"""
import os
import sys
import json
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


if __name__ == "__main__":
    unittest.main()
