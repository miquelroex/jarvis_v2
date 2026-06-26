"""Tests del Protocolo Casa Llena (core/house_party.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.house_party as hp


class TestRolePrompt(unittest.TestCase):
    def test_includes_role_and_objective(self):
        p = hp.build_role_prompt("ingeniero", "crear una API REST")
        self.assertIn("INGENIERÍA", p)
        self.assertIn("crear una API REST", p)

    def test_unknown_role_safe(self):
        p = hp.build_role_prompt("desconocido", "obj")
        self.assertIn("obj", p)


class TestCoordinatorPrompt(unittest.TestCase):
    def test_includes_contributions_with_labels(self):
        p = hp.build_coordinator_prompt("objetivo X", [
            ("investigador", "contexto importante"),
            ("ingeniero", "haz esto en python"),
        ])
        self.assertIn("objetivo X", p)
        self.assertIn("Investigación", p)
        self.assertIn("Ingeniería", p)
        self.assertIn("contexto importante", p)
        self.assertIn("haz esto en python", p)

    def test_skips_empty(self):
        p = hp.build_coordinator_prompt("o", [("investigador", ""), ("ingeniero", "algo")])
        self.assertIn("algo", p)


class TestRunHouseParty(unittest.TestCase):
    def test_empty_objective(self):
        self.assertIn("objetivo", hp.run_house_party("  ").lower())

    def test_full_flow_synthesizes(self):
        role_answers = {
            "investigador": "contexto",
            "ingeniero": "implementación",
            "control": "riesgos",
        }

        with patch.object(hp, "_ask_role", side_effect=lambda r, o: role_answers[r]), \
             patch.object(hp, "_ask_model", return_value="RESPUESTA UNIFICADA") as mock_model:
            out = hp.run_house_party("objetivo", synthesizer="COORD")
        self.assertEqual(out, "RESPUESTA UNIFICADA")
        # El coordinador se llamó una vez (la síntesis).
        mock_model.assert_called_once()

    def test_single_contribution_returns_directly(self):
        def fake_role(r, o):
            return "solo investigador" if r == "investigador" else ""

        with patch.object(hp, "_ask_role", side_effect=fake_role), \
             patch.object(hp, "_ask_model", return_value="no debería usarse"):
            out = hp.run_house_party("obj", roles=["investigador", "ingeniero"])
        self.assertEqual(out, "solo investigador")

    def test_no_contributions(self):
        with patch.object(hp, "_ask_role", return_value=""):
            out = hp.run_house_party("obj")
        self.assertIn("no ha podido aportar", out)

    def test_coordinator_failure_falls_back(self):
        with patch.object(hp, "_ask_role", side_effect=lambda r, o: f"ap-{r}"), \
             patch.object(hp, "_ask_model", return_value=""):
            out = hp.run_house_party("obj", roles=["investigador", "ingeniero"], synthesizer="C")
        self.assertIn("ap-investigador", out)
        self.assertIn("ap-ingeniero", out)


if __name__ == "__main__":
    unittest.main()
