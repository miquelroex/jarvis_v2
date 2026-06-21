"""Tests de la bandeja de entrada (core/inbox.py).

Usa una base de datos SQLite temporal por test (set_db_path), sin dependencias
pesadas, por lo que es ejecutable de forma aislada.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.memory import set_db_path, init_db
import core.inbox as inbox


class TestInbox(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        set_db_path(self.db_path)
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_add_and_get(self):
        self.assertTrue(inbox.add_inbox_item("comprar pan"))
        self.assertTrue(inbox.add_inbox_item("llamar al banco"))
        items = inbox.get_inbox_items()
        contents = [i["content"] for i in items]
        self.assertEqual(contents, ["comprar pan", "llamar al banco"])
        # Todas pendientes al crearse.
        self.assertTrue(all(i["done"] is False for i in items))

    def test_add_empty_rejected(self):
        self.assertFalse(inbox.add_inbox_item(""))
        self.assertFalse(inbox.add_inbox_item("   "))
        self.assertEqual(inbox.get_inbox_items(), [])

    def test_mark_done_hides_from_default_list(self):
        inbox.add_inbox_item("tarea A")
        inbox.add_inbox_item("tarea B")
        item_id = inbox.get_inbox_items()[0]["id"]

        self.assertTrue(inbox.mark_inbox_done(item_id))
        pending = inbox.get_inbox_items()
        self.assertEqual([i["content"] for i in pending], ["tarea B"])

        # Pero sigue estando con include_done=True.
        all_items = inbox.get_inbox_items(include_done=True)
        self.assertEqual(len(all_items), 2)
        done_item = next(i for i in all_items if i["id"] == item_id)
        self.assertTrue(done_item["done"])

    def test_mark_done_nonexistent_returns_false(self):
        self.assertFalse(inbox.mark_inbox_done(9999))

    def test_clear_all(self):
        inbox.add_inbox_item("uno")
        inbox.add_inbox_item("dos")
        removed = inbox.clear_inbox()
        self.assertEqual(removed, 2)
        self.assertEqual(inbox.get_inbox_items(include_done=True), [])

    def test_clear_only_done(self):
        inbox.add_inbox_item("pendiente")
        inbox.add_inbox_item("completada")
        done_id = inbox.get_inbox_items()[1]["id"]
        inbox.mark_inbox_done(done_id)

        removed = inbox.clear_inbox(only_done=True)
        self.assertEqual(removed, 1)
        remaining = inbox.get_inbox_items(include_done=True)
        self.assertEqual([i["content"] for i in remaining], ["pendiente"])


if __name__ == "__main__":
    unittest.main()
