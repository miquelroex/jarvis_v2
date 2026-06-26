"""Tests de la base de conocimiento de errores recurrentes (core/error_kb.py)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.error_kb as kb


TB1 = """Traceback (most recent call last):
  File "C:\\Users\\miquel\\jarvis\\main.py", line 42, in <module>
    open('/home/a/config.json')
FileNotFoundError: [Errno 2] No such file or directory: '/home/a/config.json'"""

TB2 = """Traceback (most recent call last):
  File "/srv/app/run.py", line 999, in load
    open('/var/data/other.json')
FileNotFoundError: [Errno 2] No such file or directory: '/var/data/other.json'"""

TB_OTHER = """Traceback (most recent call last):
  File "x.py", line 1, in <module>
ValueError: invalid literal for int() with base 10: 'abc'"""


class TestSignature(unittest.TestCase):
    def test_same_error_different_paths_same_signature(self):
        self.assertEqual(kb.error_signature(TB1), kb.error_signature(TB2))

    def test_different_errors_differ(self):
        self.assertNotEqual(kb.error_signature(TB1), kb.error_signature(TB_OTHER))

    def test_signature_is_normalized(self):
        sig = kb.error_signature(TB1)
        self.assertIn("filenotfounderror", sig)
        self.assertNotIn("config.json", sig)  # ruta/literal normalizados

    def test_empty(self):
        self.assertEqual(kb.error_signature(""), "")
        self.assertEqual(kb.error_signature("   "), "")

    def test_plain_exception_line(self):
        self.assertTrue(kb.error_signature("KeyError: 'missing'"))


class TestKB(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "error_kb.json"
        self._patch = patch.object(kb, "KB_FILE", self.tmp)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_record_increments_count(self):
        kb.record_error(TB1)
        kb.record_error(TB2)  # misma firma
        entry = kb.lookup(TB1)
        self.assertEqual(entry["count"], 2)

    def test_recall_empty_without_solution(self):
        kb.record_error(TB1)
        self.assertEqual(kb.recall(TB1), "")

    def test_recall_with_solution(self):
        kb.record_error(TB1)
        kb.record_error(TB2)  # misma firma -> count 2
        kb.record_solution(TB1, "Crear el fichero de config antes de abrirlo.")
        msg = kb.recall(TB2)  # misma firma, distinto path
        self.assertIn("2 veces", msg)
        self.assertIn("Crear el fichero", msg)

    def test_record_error_with_solution(self):
        kb.record_error(TB_OTHER, solution="Validar la entrada con try/except.")
        self.assertIn("Validar la entrada", kb.recall(TB_OTHER))

    def test_lookup_unknown(self):
        self.assertIsNone(kb.lookup("AlgoQueNoExisteError: nope"))

    def test_summary(self):
        kb.record_error(TB1)
        kb.record_error(TB1)
        kb.record_error(TB_OTHER)
        kb.record_solution(TB_OTHER, "fix")
        s = kb.get_summary()
        self.assertIn("2×", s)
        self.assertIn("con solución", s)

    def test_summary_empty(self):
        self.assertIn("No tengo errores", kb.get_summary())

    def test_record_solution_empty_ignored(self):
        self.assertFalse(kb.record_solution(TB1, "  "))


if __name__ == "__main__":
    unittest.main()
