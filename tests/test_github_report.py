"""Tests del resumen de GitHub (core/github_report.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.github_report as gh


class TestBuildSummary(unittest.TestCase):
    def test_unavailable(self):
        r = gh.build_github_summary({"available": False})
        self.assertIn("No he podido consultar", r)

    def test_no_prs_no_issues_no_ci(self):
        r = gh.build_github_summary({"pr_count": 0, "issue_count": 0, "ci": None})
        self.assertIn("Sin pull requests abiertos", r)
        self.assertIn("Todo tranquilo", r)

    def test_prs_plural(self):
        r = gh.build_github_summary({"pr_count": 3, "issue_count": 0, "ci": None})
        self.assertIn("3 pull requests abiertos pendientes", r)

    def test_pr_singular(self):
        r = gh.build_github_summary({"pr_count": 1, "issue_count": 0, "ci": None})
        self.assertIn("1 pull request abierto pendiente", r)

    def test_issues(self):
        r = gh.build_github_summary({"pr_count": 0, "issue_count": 2, "ci": None})
        self.assertIn("2 issues abiertas", r)

    def test_ci_green(self):
        r = gh.build_github_summary({"pr_count": 0, "issue_count": 0,
                                     "ci": {"status": "completed", "conclusion": "success", "displayTitle": "x"}})
        self.assertIn("en verde", r)

    def test_ci_red(self):
        r = gh.build_github_summary({"pr_count": 0, "issue_count": 0,
                                     "ci": {"status": "completed", "conclusion": "failure", "displayTitle": "feat: y"}})
        self.assertIn("ROJO", r)
        self.assertIn("feat: y", r)

    def test_ci_in_progress(self):
        r = gh.build_github_summary({"pr_count": 0, "issue_count": 0,
                                     "ci": {"status": "in_progress", "conclusion": None, "displayTitle": "x"}})
        self.assertIn("en ejecución", r)


class TestGhJson(unittest.TestCase):
    def test_parses_json(self):
        with patch.object(gh, "_run_gh", return_value=(0, '[{"number": 1}, {"number": 2}]')):
            self.assertEqual(gh._gh_json(["x"]), [{"number": 1}, {"number": 2}])

    def test_none_on_error_code(self):
        with patch.object(gh, "_run_gh", return_value=(1, "")):
            self.assertIsNone(gh._gh_json(["x"]))

    def test_none_on_bad_json(self):
        with patch.object(gh, "_run_gh", return_value=(0, "no es json")):
            self.assertIsNone(gh._gh_json(["x"]))

    def test_count(self):
        with patch.object(gh, "_gh_json", return_value=[{}, {}, {}]):
            self.assertEqual(gh._count(["x"]), 3)


class TestGetSummary(unittest.TestCase):
    def test_unavailable_when_all_fail(self):
        with patch.object(gh, "_count", return_value=None), \
             patch.object(gh, "_gh_json", return_value=None):
            r = gh.get_github_summary()
        self.assertIn("No he podido consultar", r)

    def test_assembles_real(self):
        def fake_count(args):
            return 2 if args[0] == "pr" else 0
        with patch.object(gh, "_count", side_effect=fake_count), \
             patch.object(gh, "_gh_json", return_value=[{"status": "completed", "conclusion": "success", "displayTitle": "t"}]):
            r = gh.get_github_summary()
        self.assertIn("2 pull requests", r)
        self.assertIn("en verde", r)

    def test_empty_ci_list_no_crash(self):
        # ci_list vacío -> ci debe ser None, sin IndexError.
        with patch.object(gh, "_count", return_value=0), \
             patch.object(gh, "_gh_json", return_value=[]):
            r = gh.get_github_summary()
        self.assertIn("Todo tranquilo", r)

    def test_available_when_only_some_data(self):
        # PRs=2 pero issues/ci no disponibles -> sigue disponible y reporta PRs.
        def fake_count(args):
            return 2 if args[0] == "pr" else None
        with patch.object(gh, "_count", side_effect=fake_count), \
             patch.object(gh, "_gh_json", return_value=None):
            r = gh.get_github_summary()
        self.assertNotIn("No he podido consultar", r)
        self.assertIn("2 pull requests", r)

    def test_issue_count_propagated(self):
        def fake_count(args):
            return 0 if args[0] == "pr" else 5
        with patch.object(gh, "_count", side_effect=fake_count), \
             patch.object(gh, "_gh_json", return_value=None):
            r = gh.get_github_summary()
        self.assertIn("5 issues abiertas", r)


if __name__ == "__main__":
    unittest.main()
