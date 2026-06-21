"""Tests del versionado y migraciones del esquema SQLite (core/memory.py)."""
import os
import sys
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.memory as memory


class TestSchemaMigrations(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        memory.set_db_path(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _tables(self):
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            return {r[0] for r in rows}
        finally:
            conn.close()

    def test_fresh_db_is_at_current_version(self):
        memory.init_db(self.db_path)
        self.assertEqual(memory.current_schema_version(), memory.SCHEMA_VERSION)
        tables = self._tables()
        self.assertIn("memories", tables)
        self.assertIn("scheduled_tasks", tables)

    def test_init_is_idempotent(self):
        memory.init_db(self.db_path)
        memory.save_memory("dato importante", category="test", source="test")
        # Segunda inicialización no debe perder datos ni cambiar la versión.
        memory.init_db(self.db_path)
        self.assertEqual(memory.current_schema_version(), memory.SCHEMA_VERSION)
        self.assertEqual(len(memory.get_all_memories()), 1)

    def test_legacy_db_version_zero_is_migrated_without_data_loss(self):
        # Simular una BD "antigua": tablas creadas a mano y user_version = 0.
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT, source TEXT, content TEXT UNIQUE, created_at TEXT
            )
        """)
        conn.execute(
            "INSERT INTO memories (category, source, content, created_at) VALUES (?,?,?,?)",
            ("legado", "test", "recuerdo previo", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()
        self.assertEqual(memory.get_schema_version(conn), 0)
        conn.close()

        memory.init_db(self.db_path)

        # La versión se actualiza y el dato previo se conserva.
        self.assertEqual(memory.current_schema_version(), memory.SCHEMA_VERSION)
        mems = memory.get_all_memories()
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems[0]["content"], "recuerdo previo")
        # La tabla que faltaba (scheduled_tasks) se crea durante la migración.
        self.assertIn("scheduled_tasks", self._tables())

    def test_migration_loop_applies_pending_in_order(self):
        # Partimos de una BD ya en v1.
        memory.init_db(self.db_path)
        applied = []

        def fake_v2(conn):
            conn.execute("CREATE TABLE IF NOT EXISTS nueva_tabla (id INTEGER)")
            applied.append(2)

        new_migrations = dict(memory._MIGRATIONS)
        new_migrations[2] = fake_v2

        conn = sqlite3.connect(self.db_path)
        try:
            with patch.object(memory, "SCHEMA_VERSION", 2), \
                 patch.object(memory, "_MIGRATIONS", new_migrations):
                result = memory._apply_migrations(conn)
                self.assertEqual(result, 2)
                self.assertEqual(applied, [2])
                self.assertEqual(memory.get_schema_version(conn), 2)
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='nueva_tabla'"
                ).fetchone()
                self.assertIsNotNone(row)
        finally:
            conn.close()

    def test_already_current_version_is_noop(self):
        memory.init_db(self.db_path)
        conn = sqlite3.connect(self.db_path)
        try:
            # Ya en la versión actual: _apply_migrations no cambia nada.
            result = memory._apply_migrations(conn)
            self.assertEqual(result, memory.SCHEMA_VERSION)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
