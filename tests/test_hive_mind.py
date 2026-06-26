"""Tests del Protocolo Mente Colmena (core/hive_mind.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.hive_mind as hive


class TestParseModels(unittest.TestCase):
    def test_dedup_and_strip(self):
        self.assertEqual(hive._parse_model_list("a, b ,a, c"), ["a", "b", "c"])

    def test_empty(self):
        self.assertEqual(hive._parse_model_list(""), [])

    def test_default_from_env(self):
        with patch.dict(os.environ, {"JARVIS_HIVE_MODELS": "x/1, y/2"}):
            self.assertEqual(hive.get_default_models(), ["x/1", "y/2"])

    def test_default_from_configured(self):
        with patch.dict(os.environ, {"JARVIS_HIVE_MODELS": "",
                                     "JARVIS_MODEL_DEFAULT": "m/def",
                                     "JARVIS_MODEL_THINK": "m/think",
                                     "JARVIS_MODEL_CODE": "m/code"}):
            self.assertEqual(hive.get_default_models(), ["m/def", "m/think", "m/code"])


class TestShortName(unittest.TestCase):
    def test(self):
        self.assertEqual(hive._short_name("deepseek/deepseek-v4-pro"), "deepseek-v4-pro")
        self.assertEqual(hive._short_name("gemini"), "gemini")


class TestSynthesisPrompt(unittest.TestCase):
    def test_includes_question_and_answers(self):
        p = hive.build_synthesis_prompt("¿2+2?", [
            {"model": "a/x", "answer": "4"},
            {"model": "b/y", "answer": "Cuatro"},
        ])
        self.assertIn("¿2+2?", p)
        self.assertIn("4", p)
        self.assertIn("Cuatro", p)
        self.assertIn("x", p)  # nombre corto del modelo
        self.assertIn("CONSENSO", p)

    def test_skips_empty_answers(self):
        p = hive.build_synthesis_prompt("q", [{"model": "a", "answer": ""}, {"model": "b", "answer": "ok"}])
        self.assertIn("ok", p)


class TestConsult(unittest.TestCase):
    def test_empty_question(self):
        self.assertIn("Qué desea", hive.consult("  "))

    def test_synthesizes_multiple(self):
        canned = {
            "m1": {"model": "m1", "answer": "Respuesta uno", "error": None},
            "m2": {"model": "m2", "answer": "Respuesta dos", "error": None},
            "SYNTH": {"model": "SYNTH", "answer": "Consenso final", "error": None},
        }

        def fake_ask(model, prompt):
            return canned[model]

        with patch.object(hive, "_ask_one", side_effect=fake_ask):
            out = hive.consult("pregunta", models=["m1", "m2"], synthesizer="SYNTH")
        self.assertEqual(out, "Consenso final")

    def test_single_valid_returns_directly(self):
        def fake_ask(model, prompt):
            if model == "m1":
                return {"model": "m1", "answer": "Solo yo", "error": None}
            return {"model": model, "answer": "", "error": "boom"}

        with patch.object(hive, "_ask_one", side_effect=fake_ask):
            out = hive.consult("q", models=["m1", "m2"], synthesizer="SYNTH")
        self.assertEqual(out, "Solo yo")

    def test_all_fail(self):
        with patch.object(hive, "_ask_one", return_value={"model": "x", "answer": "", "error": "e"}):
            out = hive.consult("q", models=["a", "b"])
        self.assertIn("no he obtenido respuesta", out)

    def test_synth_failure_falls_back_to_raw(self):
        def fake_ask(model, prompt):
            if model in ("m1", "m2"):
                return {"model": model, "answer": f"ans-{model}", "error": None}
            return {"model": model, "answer": "", "error": "synth boom"}

        with patch.object(hive, "_ask_one", side_effect=fake_ask):
            out = hive.consult("q", models=["m1", "m2"], synthesizer="SYNTH")
        self.assertIn("ans-m1", out)
        self.assertIn("ans-m2", out)


class TestQueryAllParallel(unittest.TestCase):
    def test_preserves_model_order(self):
        def fake_ask(model, prompt):
            return {"model": model, "answer": model.upper(), "error": None}

        with patch.object(hive, "_ask_one", side_effect=fake_ask):
            res = hive._query_all("q", ["a", "b", "c"])
        self.assertEqual([r["model"] for r in res], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
