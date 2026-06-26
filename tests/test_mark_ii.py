"""Tests del Protocolo Mark II (core/mark_ii.py)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.mark_ii as m2


class TestPathAllowed(unittest.TestCase):
    def test_allowed(self):
        self.assertTrue(m2.is_path_allowed("core/blackout.py", ["core", "tools"]))
        self.assertTrue(m2.is_path_allowed("tools/voice.py", ["core", "tools"]))

    def test_disallowed(self):
        self.assertFalse(m2.is_path_allowed(".env", ["core", "tools"]))
        self.assertFalse(m2.is_path_allowed("gui/app.py", ["core", "tools"]))

    def test_traversal_blocked(self):
        self.assertFalse(m2.is_path_allowed("core/../.env", ["core"]))

    def test_empty(self):
        self.assertFalse(m2.is_path_allowed("", ["core"]))


class TestHelpers(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(m2._slug("Añade validación de entrada!"), "a-ade-validaci-n-de-entrada")

    def test_strip_fences(self):
        self.assertEqual(m2._strip_code_fences("```python\nx = 1\n```"), "x = 1")
        self.assertEqual(m2._strip_code_fences("sin vallas"), "sin vallas")

    def test_prompt(self):
        p = m2.build_improvement_prompt("core/x.py", "def f(): pass", "mejóralo")
        self.assertIn("core/x.py", p)
        self.assertIn("mejóralo", p)
        self.assertIn("def f()", p)


class TestRunMarkII(unittest.TestCase):
    def setUp(self):
        # Fichero objetivo real dentro de un "repo" temporal.
        self.root = Path(tempfile.mkdtemp())
        (self.root / "core").mkdir()
        self.target = self.root / "core" / "mod.py"
        self.target.write_text("ORIGINAL\n", encoding="utf-8")
        self._patch_root = patch.object(m2, "PROJECT_ROOT", self.root)
        self._patch_root.start()

    def tearDown(self):
        self._patch_root.stop()

    def _git_recorder(self, clean=True, branch="main"):
        calls = []

        def fake(args):
            calls.append(args)
            if args[:2] == ["status", "--porcelain"]:
                return (0, "" if clean else " M core/mod.py")
            if args[:2] == ["rev-parse", "--abbrev-ref"]:
                return (0, branch + "\n")
            return (0, "")
        return fake, calls

    def test_rejects_disallowed_path(self):
        with patch.dict(os.environ, {"JARVIS_MARKII_ALLOWED_DIRS": "core"}):
            out = m2.run_mark_ii("gui/app.py", "algo")
        self.assertIn("seguridad", out.lower())

    def test_rejects_dirty_tree(self):
        fake, calls = self._git_recorder(clean=False)
        with patch.dict(os.environ, {"JARVIS_MARKII_ALLOWED_DIRS": "core"}), \
             patch.object(m2, "_run_git", side_effect=fake):
            out = m2.run_mark_ii("core/mod.py", "mejora")
        self.assertIn("sin confirmar", out)

    def test_success_commits_and_returns_to_branch(self):
        fake, calls = self._git_recorder(clean=True, branch="main")
        with patch.dict(os.environ, {"JARVIS_MARKII_ALLOWED_DIRS": "core"}), \
             patch.object(m2, "_run_git", side_effect=fake), \
             patch.object(m2, "_generate_improved", return_value="MEJORADO\n"), \
             patch.object(m2, "_run_tests", return_value=(True, "10 passed")):
            out = m2.run_mark_ii("core/mod.py", "mejora")
        self.assertIn("validada en la rama markII/", out)
        self.assertIn("10 passed", out)
        # Se hizo commit y se volvió a main.
        self.assertTrue(any(a[0] == "commit" for a in calls))
        self.assertIn(["checkout", "main"], calls)
        # El fichero se escribió con el contenido mejorado.
        self.assertEqual(self.target.read_text(encoding="utf-8"), "MEJORADO\n")

    def test_failure_discards_and_deletes_branch(self):
        fake, calls = self._git_recorder(clean=True, branch="main")
        with patch.dict(os.environ, {"JARVIS_MARKII_ALLOWED_DIRS": "core"}), \
             patch.object(m2, "_run_git", side_effect=fake), \
             patch.object(m2, "_generate_improved", return_value="ROTO\n"), \
             patch.object(m2, "_run_tests", return_value=(False, "1 failed")):
            out = m2.run_mark_ii("core/mod.py", "mejora")
        self.assertIn("rompía las pruebas", out)
        # Descartó el fichero y borró la rama.
        self.assertTrue(any(a[:2] == ["checkout", "--"] for a in calls))
        self.assertTrue(any(a[:2] == ["branch", "-D"] for a in calls))

    def test_no_change_generated(self):
        fake, calls = self._git_recorder(clean=True)
        with patch.dict(os.environ, {"JARVIS_MARKII_ALLOWED_DIRS": "core"}), \
             patch.object(m2, "_run_git", side_effect=fake), \
             patch.object(m2, "_generate_improved", return_value="ORIGINAL\n"):
            out = m2.run_mark_ii("core/mod.py", "mejora")
        self.assertIn("no he generado una mejora", out.lower())

    def test_missing_file(self):
        with patch.dict(os.environ, {"JARVIS_MARKII_ALLOWED_DIRS": "core"}):
            out = m2.run_mark_ii("core/noexiste.py", "mejora")
        self.assertIn("no encuentro", out.lower())


if __name__ == "__main__":
    unittest.main()
