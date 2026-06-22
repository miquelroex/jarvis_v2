"""Tests de la conciencia del proyecto git activo (core/project_awareness.py)."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.project_awareness as pa


class TestGitState(unittest.TestCase):
    def _fake_git(self, mapping):
        """Devuelve una función _run_git falsa según el primer argumento del comando."""
        def runner(args, cwd):
            key = args[0]
            return mapping.get(key)
        return runner

    def test_full_state(self):
        mapping = {
            "rev-parse": "/home/user/miproyecto",  # --show-toplevel (primer rev-parse)
            "log": "abc123 feat: algo",
            "status": " M a.py\n?? b.py\n",
        }
        # branch usa rev-parse --abbrev-ref; como ambos empiezan por rev-parse,
        # diferenciamos por la presencia de "--abbrev-ref".
        def runner(args, cwd):
            if args[0] == "rev-parse" and "--abbrev-ref" in args:
                return "feature/mapa"
            if args[0] == "rev-parse":
                return "/home/user/miproyecto"
            if args[0] == "log":
                return "abc123 feat: algo"
            if args[0] == "status":
                return " M a.py\n?? b.py\n"
            return None

        with patch.object(pa, "_run_git", side_effect=runner):
            s = pa.get_git_state("/cualquier/sitio")
        self.assertTrue(s["is_repo"])
        self.assertEqual(s["repo_name"], "miproyecto")
        self.assertEqual(s["branch"], "feature/mapa")
        self.assertEqual(s["dirty_count"], 2)
        self.assertIn("feat: algo", s["last_commit"])

    def test_clean_repo(self):
        def runner(args, cwd):
            if args[0] == "rev-parse" and "--abbrev-ref" in args:
                return "main"
            if args[0] == "rev-parse":
                return "/r/jarvis"
            if args[0] == "log":
                return "deadbee fix"
            if args[0] == "status":
                return ""
            return None
        with patch.object(pa, "_run_git", side_effect=runner):
            s = pa.get_git_state("/r/jarvis")
        self.assertTrue(s["is_repo"])
        self.assertEqual(s["dirty_count"], 0)

    def test_not_a_repo(self):
        with patch.object(pa, "_run_git", return_value=None):
            s = pa.get_git_state("/tmp/no-repo")
        self.assertFalse(s["is_repo"])
        self.assertEqual(s["dirty_count"], 0)


class TestResolveDir(unittest.TestCase):
    def test_falls_back_to_jarvis_root_without_base(self):
        with patch.dict(os.environ, {"JARVIS_PROJECTS_DIR": ""}):
            self.assertEqual(pa._resolve_active_repo_dir(), pa.PROJECT_ROOT)


class TestContextLine(unittest.TestCase):
    def test_includes_branch_and_dirty(self):
        state = {"is_repo": True, "repo_name": "jarvis", "branch": "main",
                 "last_commit": "abc feat", "dirty_count": 4}
        with patch.object(pa, "get_active_project", return_value=state):
            line = pa.get_context_line()
        self.assertIn("jarvis", line)
        self.assertIn("main", line)
        self.assertIn("4 cambios sin confirmar", line)

    def test_clean_repo_line(self):
        state = {"is_repo": True, "repo_name": "jarvis", "branch": "main",
                 "last_commit": "abc feat", "dirty_count": 0}
        with patch.object(pa, "get_active_project", return_value=state):
            self.assertIn("sin cambios pendientes", pa.get_context_line())

    def test_empty_when_not_repo(self):
        with patch.object(pa, "get_active_project", return_value={"is_repo": False}):
            self.assertEqual(pa.get_context_line(), "")


if __name__ == "__main__":
    unittest.main()
