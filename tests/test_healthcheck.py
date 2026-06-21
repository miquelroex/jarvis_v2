"""Tests del healthcheck de arranque (core/healthcheck.py).

Todo se prueba con mocks/temp DB: no se importan tools reales, no se ejecuta
la suite de tests y no se depende de servicios reales.
"""
import os
import sys
import json
import types
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.healthcheck as healthcheck


class TestAggregateStatus(unittest.TestCase):
    """Reglas de agregación del estado global."""

    def test_healthy(self):
        status = healthcheck._aggregate_status(
            tools_report={"loaded": 10, "failed": []},
            services={"web_gui": "running", "telegram_bot": "disabled"},
            database={"ok": True},
        )
        self.assertEqual(status, "healthy")

    def test_degraded_on_failed_tool(self):
        status = healthcheck._aggregate_status(
            tools_report={"loaded": 9, "failed": [{"file": "tools/x.py", "error": "boom"}]},
            services={"web_gui": "running"},
            database={"ok": True},
        )
        self.assertEqual(status, "degraded")

    def test_degraded_on_stopped_service(self):
        status = healthcheck._aggregate_status(
            tools_report={"loaded": 10, "failed": []},
            services={"web_gui": "stopped"},
            database={"ok": True},
        )
        self.assertEqual(status, "degraded")

    def test_disabled_service_does_not_degrade(self):
        status = healthcheck._aggregate_status(
            tools_report={"loaded": 10, "failed": []},
            services={"web_gui": "disabled", "telegram_bot": "disabled"},
            database={"ok": True},
        )
        self.assertEqual(status, "healthy")

    def test_error_on_db_failure_overrides_degraded(self):
        # Aunque haya tools fallidas y servicios caídos, una BD inaccesible -> error.
        status = healthcheck._aggregate_status(
            tools_report={"loaded": 0, "failed": [{"file": "tools/x.py", "error": "boom"}]},
            services={"web_gui": "stopped"},
            database={"ok": False, "error": "db locked"},
        )
        self.assertEqual(status, "error")


class TestCheckDatabase(unittest.TestCase):
    """Comprobación de SQLite / esquema."""

    def test_ok_with_expected_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "jarvis.db")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE memories (id INTEGER)")
            conn.execute("CREATE TABLE scheduled_tasks (id INTEGER)")
            conn.commit()
            conn.close()
            with patch("core.memory.init_db"), patch("core.memory.get_db_path", return_value=db_path):
                result = healthcheck._check_database()
        self.assertTrue(result["ok"])
        self.assertIn("memories", result["tables"])
        self.assertIn("scheduled_tasks", result["tables"])
        self.assertIsNone(result["error"])

    def test_missing_table_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "jarvis.db")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE memories (id INTEGER)")  # falta scheduled_tasks
            conn.commit()
            conn.close()
            with patch("core.memory.init_db"), patch("core.memory.get_db_path", return_value=db_path):
                result = healthcheck._check_database()
        self.assertFalse(result["ok"])
        self.assertIsNotNone(result["error"])
        self.assertIn("scheduled_tasks", result["error"])

    def test_error_when_inaccessible(self):
        with patch("core.memory.init_db", side_effect=sqlite3.OperationalError("unable to open database file")):
            result = healthcheck._check_database()
        self.assertFalse(result["ok"])
        self.assertIsNotNone(result["error"])


class TestCheckApiKeys(unittest.TestCase):
    """Las claves API solo reportan presencia, nunca su valor."""

    def test_only_presence_no_values(self):
        fake = [
            {"name": "OPENROUTER_API_KEY", "configured": True},
            {"name": "TAVILY_API_KEY", "configured": False},
        ]
        with patch("core.jarvis_integrity.check_env_variables", return_value=fake):
            keys = healthcheck._check_api_keys()

        for entry in keys:
            # Estructura exacta: solo nombre y booleano de presencia.
            self.assertEqual(set(entry.keys()), {"name", "configured"})
        names = {e["name"]: e["configured"] for e in keys}
        self.assertTrue(names["OPENROUTER_API_KEY"])
        self.assertFalse(names["TAVILY_API_KEY"])


class TestCheckTools(unittest.TestCase):
    """El reporte de tools se lee del estado de agent_manager, sin reimportar."""

    def test_reads_report_without_reimport(self):
        fake_report = {"loaded": 7, "failed": [{"file": "tools/bad.py", "error": "ImportError"}]}
        # Inyectamos un módulo falso en sys.modules para no importar el agent_manager
        # real (pesado: arrastra langchain). Esto verifica que _check_tools solo lee
        # un reporte ya calculado, sin reimportar ni recargar nada.
        fake_mod = types.SimpleNamespace(get_tools_load_report=lambda: fake_report)
        with patch.dict(sys.modules, {"core.agent_manager": fake_mod}):
            result = healthcheck._check_tools()
        self.assertEqual(result["loaded"], 7)
        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(result["failed"][0]["file"], "tools/bad.py")


class TestRunHealthcheck(unittest.TestCase):
    """Integración del agregador con las secciones mockeadas."""

    def _run_with(self, tools_report, services, api_keys, database):
        with patch.object(healthcheck, "_check_tools", return_value=tools_report), \
             patch.object(healthcheck, "_check_services", return_value=services), \
             patch.object(healthcheck, "_check_api_keys", return_value=api_keys), \
             patch.object(healthcheck, "_check_database", return_value=database):
            return healthcheck.run_healthcheck()

    def test_healthy_report_shape(self):
        report = self._run_with(
            tools_report={"loaded": 5, "failed": []},
            services={"web_gui": "running", "telegram_bot": "disabled"},
            api_keys=[{"name": "OPENROUTER_API_KEY", "configured": True}],
            database={"ok": True, "path": ":memory:", "tables": ["memories", "scheduled_tasks"], "error": None},
        )
        self.assertEqual(report["status"], "healthy")
        self.assertIn("timestamp", report)
        self.assertEqual(report["tools"]["loaded"], 5)
        self.assertEqual(set(report.keys()), {"status", "timestamp", "tools", "services", "api_keys", "database"})

    def test_error_report_on_db(self):
        report = self._run_with(
            tools_report={"loaded": 5, "failed": []},
            services={"web_gui": "running"},
            api_keys=[],
            database={"ok": False, "error": "locked"},
        )
        self.assertEqual(report["status"], "error")

    def test_degraded_report_on_failed_tool(self):
        report = self._run_with(
            tools_report={"loaded": 4, "failed": [{"file": "tools/x.py", "error": "boom"}]},
            services={"web_gui": "running"},
            api_keys=[],
            database={"ok": True},
        )
        self.assertEqual(report["status"], "degraded")

    def test_report_never_contains_key_values(self):
        report = self._run_with(
            tools_report={"loaded": 1, "failed": []},
            services={},
            api_keys=[{"name": "OPENROUTER_API_KEY", "configured": True}],
            database={"ok": True},
        )
        for entry in report["api_keys"]:
            self.assertNotIn("value", entry)
            self.assertEqual(set(entry.keys()), {"name", "configured"})


class TestSummarizeHealthcheck(unittest.TestCase):
    """Resumen de una línea para logging."""

    def test_summary_contains_status_and_counts(self):
        report = {
            "status": "degraded",
            "tools": {"loaded": 30, "failed": [{"file": "tools/x.py", "error": "boom"}]},
            "services": {"a": "running", "b": "stopped", "c": "disabled"},
            "api_keys": [
                {"name": "OPENROUTER_API_KEY", "configured": True},
                {"name": "TAVILY_API_KEY", "configured": False},
            ],
            "database": {"ok": True},
        }
        summary = healthcheck.summarize_healthcheck(report)
        self.assertIn("status=degraded", summary)
        self.assertIn("30 ok/1 fallidas", summary)
        self.assertIn("1 activos/1 detenidos/1 desactivados", summary)
        self.assertIn("api_keys=1/2", summary)
        self.assertIn("sqlite=ok", summary)

    def test_summary_never_leaks_key_values(self):
        report = {
            "status": "healthy",
            "tools": {"loaded": 1, "failed": []},
            "services": {},
            "api_keys": [{"name": "OPENROUTER_API_KEY", "configured": True}],
            "database": {"ok": True},
        }
        summary = healthcheck.summarize_healthcheck(report)
        # Solo cuenta presencia; el nombre de la clave no aparece como valor.
        self.assertIn("api_keys=1/1", summary)

    def test_summary_handles_missing_sections(self):
        # No debe lanzar aunque falten secciones.
        summary = healthcheck.summarize_healthcheck({"status": "error"})
        self.assertIn("status=error", summary)
        self.assertIn("sqlite=ERROR", summary)


class TestPersistHealthcheck(unittest.TestCase):
    """Persistencia del reporte a JSON."""

    def test_persist_writes_valid_json(self):
        report = {"status": "healthy", "tools": {"loaded": 3, "failed": []}}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "startup_health.json")  # subdir aún no existe
            ok = healthcheck.persist_healthcheck(report, path=path)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(path))
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
        self.assertEqual(loaded, report)

    def test_persist_returns_false_on_error(self):
        report = {"status": "healthy"}
        # Forzar fallo de escritura.
        with patch("builtins.open", side_effect=OSError("disk full")):
            ok = healthcheck.persist_healthcheck(report, path="whatever.json")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
