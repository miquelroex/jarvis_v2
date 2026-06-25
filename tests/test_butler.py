"""Tests del Protocolo Mayordomo (core/butler.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.butler as butler


class TestParseTargets(unittest.TestCase):
    def test_comma_and_semicolon(self):
        self.assertEqual(butler._parse_targets("code, spotify ; chrome"), ["code", "spotify", "chrome"])

    def test_empty(self):
        self.assertEqual(butler._parse_targets(""), [])
        self.assertEqual(butler._parse_targets(None), [])

    def test_strips_and_drops_blanks(self):
        self.assertEqual(butler._parse_targets("code,, , spotify"), ["code", "spotify"])


class TestBuildReport(unittest.TestCase):
    def test_includes_briefing_and_launched(self):
        r = butler.build_butler_report("Buenos días, señor.", ["code", "spotify"])
        self.assertIn("Buenos días", r)
        self.assertIn("code, spotify", r)
        self.assertIn("estación de trabajo", r)

    def test_no_launched_only_briefing(self):
        r = butler.build_butler_report("Parte del día.", [])
        self.assertEqual(r, "Parte del día.")


class TestLaunchEnvironment(unittest.TestCase):
    def test_launches_apps_and_urls(self):
        calls = {"apps": [], "urls": []}
        fake_launcher = type(sys)("tools.launcher")
        fake_browser = type(sys)("tools.browser")
        fake_launcher.open_windows_app = type("T", (), {
            "invoke": staticmethod(lambda d: calls["apps"].append(d["app_executable"]))})()
        fake_browser.open_website = type("T", (), {
            "invoke": staticmethod(lambda d: calls["urls"].append(d["url"]))})()
        with patch.dict(os.environ, {"JARVIS_BUTLER_APPS": "code,spotify", "JARVIS_BUTLER_URLS": "https://github.com"}), \
             patch.dict(sys.modules, {"tools.launcher": fake_launcher, "tools.browser": fake_browser}):
            launched = butler._launch_environment()
        self.assertEqual(calls["apps"], ["code", "spotify"])
        self.assertEqual(calls["urls"], ["https://github.com"])
        self.assertEqual(launched, ["code", "spotify", "https://github.com"])

    def test_nothing_configured(self):
        with patch.dict(os.environ, {"JARVIS_BUTLER_APPS": "", "JARVIS_BUTLER_URLS": ""}):
            self.assertEqual(butler._launch_environment(), [])


class TestRunButler(unittest.TestCase):
    def test_run_assembles_and_announces(self):
        spoken = []
        with patch.object(butler, "_launch_environment", return_value=["code"]), \
             patch.object(butler, "_get_briefing", return_value="Buenos días, señor. Cielo despejado."), \
             patch.dict(sys.modules, {"tools.voice": type(sys)("tools.voice")}):
            sys.modules["tools.voice"].speak = lambda text, disable_vad=False: spoken.append(text)
            report = butler.run_butler()
        self.assertIn("Cielo despejado", report)
        self.assertIn("code", report)
        self.assertEqual(len(spoken), 1)

    def test_run_without_launch_or_announce(self):
        with patch.object(butler, "_launch_environment", side_effect=AssertionError("no debe lanzarse")), \
             patch.object(butler, "_get_briefing", return_value="Parte."):
            report = butler.run_butler(launch=False, announce=False)
        self.assertEqual(report, "Parte.")


if __name__ == "__main__":
    unittest.main()
