"""Tests de la memoria semántica (core/semantic_memory.py) y la migración v2."""
import os
import sys
import json
import sqlite3
import threading
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.memory as memory
import core.semantic_memory as sm


class TestSchemaV2(unittest.TestCase):
    def test_memories_has_embedding_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "jarvis.db")
            memory.set_db_path(db)
            memory.init_db(db)
            self.assertEqual(memory.current_schema_version(), 2)
            conn = sqlite3.connect(db)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(memories)").fetchall()]
            conn.close()
            self.assertIn("embedding", cols)

    def test_legacy_v1_db_migrates_to_v2_without_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "jarvis.db")
            # BD "v1": tabla memories sin embedding, un dato, user_version=1
            conn = sqlite3.connect(db)
            conn.execute("""CREATE TABLE memories (id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT, source TEXT, content TEXT UNIQUE, created_at TEXT)""")
            conn.execute("INSERT INTO memories (content, created_at) VALUES ('dato', '2026-01-01')")
            conn.execute("PRAGMA user_version = 1")
            conn.commit()
            conn.close()

            memory.set_db_path(db)
            memory.init_db(db)

            self.assertEqual(memory.current_schema_version(), 2)
            conn = sqlite3.connect(db)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(memories)").fetchall()]
            row = conn.execute("SELECT content FROM memories").fetchone()
            conn.close()
            self.assertIn("embedding", cols)
            self.assertEqual(row[0], "dato")  # dato previo intacto


class TestCosine(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(sm._cosine([1, 0, 0], [1, 0, 0]), 1.0, places=5)

    def test_orthogonal(self):
        self.assertAlmostEqual(sm._cosine([1, 0], [0, 1]), 0.0, places=5)

    def test_opposite(self):
        self.assertAlmostEqual(sm._cosine([1, 0], [-1, 0]), -1.0, places=5)

    def test_zero_vector(self):
        self.assertEqual(sm._cosine([0, 0], [1, 1]), 0.0)


class TestSemanticSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "jarvis.db")
        memory.set_db_path(self.db)
        memory.init_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def _insert(self, content, embedding):
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT INTO memories (category, source, content, created_at, embedding) "
            "VALUES ('test', 'test', ?, '2026-01-01', ?)",
            (content, json.dumps(embedding)),
        )
        conn.commit()
        conn.close()

    def test_ranks_by_cosine_similarity(self):
        self._insert("perro", [1.0, 0.0, 0.0])
        self._insert("gato", [0.9, 0.1, 0.0])
        self._insert("coche", [0.0, 0.0, 1.0])

        # La consulta apunta hacia el eje "perro/gato".
        with patch.object(sm, "embed_text", return_value=[1.0, 0.0, 0.0]):
            results = sm.semantic_search("animal", top_k=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["content"], "perro")     # coseno 1.0
        self.assertEqual(results[1]["content"], "gato")      # más cerca que coche
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_empty_when_query_not_embeddable(self):
        self._insert("algo", [1.0, 0.0])
        with patch.object(sm, "embed_text", return_value=None):
            self.assertEqual(sm.semantic_search("x"), [])

    def test_ignores_memories_without_embedding(self):
        # Recuerdo sin embedding (NULL) no debe aparecer.
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO memories (category, source, content, created_at) VALUES ('t','t','sin_emb','2026-01-01')")
        conn.commit(); conn.close()
        self._insert("con_emb", [1.0, 0.0])
        with patch.object(sm, "embed_text", return_value=[1.0, 0.0]):
            results = sm.semantic_search("q")
        self.assertEqual([r["content"] for r in results], ["con_emb"])


class TestBackfill(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "jarvis.db")
        memory.set_db_path(self.db)
        memory.init_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_backfills_unembedded(self):
        conn = sqlite3.connect(self.db)
        for c in ("a", "b"):
            conn.execute("INSERT INTO memories (category, source, content, created_at) VALUES ('t','t',?,'2026-01-01')", (c,))
        conn.commit(); conn.close()

        with patch.object(sm, "embed_text", return_value=[0.1, 0.2, 0.3]):
            n = sm.backfill_embeddings()

        self.assertEqual(n, 2)
        conn = sqlite3.connect(self.db)
        rows = conn.execute("SELECT embedding FROM memories").fetchall()
        conn.close()
        self.assertTrue(all(r[0] is not None for r in rows))


class TestAutoIndexGate(unittest.TestCase):
    """El auto-indexado al guardar respeta JARVIS_SEMANTIC_MEMORY_ENABLED."""

    def test_disabled_does_not_index(self):
        with patch.dict(os.environ, {"JARVIS_SEMANTIC_MEMORY_ENABLED": "false"}), \
             patch("core.semantic_memory.index_memory") as mock_idx:
            memory._index_memory_best_effort(1, "hola")
        mock_idx.assert_not_called()

    def test_enabled_spawns_indexing(self):
        done = threading.Event()

        def fake_index(mid, content):
            done.set()
            return True

        with patch.dict(os.environ, {"JARVIS_SEMANTIC_MEMORY_ENABLED": "true"}), \
             patch("core.semantic_memory.index_memory", side_effect=fake_index):
            memory._index_memory_best_effort(99, "hola")
            self.assertTrue(done.wait(timeout=2))


if __name__ == "__main__":
    unittest.main()
