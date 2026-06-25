"""Tests del Protocolo Babel (core/babel.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.babel as babel


class TestNormalizeLang(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(babel.normalize_lang("inglés"), "inglés")
        self.assertEqual(babel.normalize_lang("ingles"), "inglés")
        self.assertEqual(babel.normalize_lang("EN"), "inglés")
        self.assertEqual(babel.normalize_lang("english"), "inglés")
        self.assertEqual(babel.normalize_lang("castellano"), "español")

    def test_unknown(self):
        self.assertIsNone(babel.normalize_lang("klingon"))
        self.assertIsNone(babel.normalize_lang(""))
        self.assertIsNone(babel.normalize_lang(None))


class TestParseCommand(unittest.TestCase):
    def test_target_and_text(self):
        target, text = babel.parse_translate_command("traduce al inglés hola qué tal")
        self.assertEqual(target, "inglés")
        self.assertEqual(text, "hola qué tal")

    def test_preserves_case_and_accents(self):
        target, text = babel.parse_translate_command("Traduce al francés Buenos días, Señor")
        self.assertEqual(target, "francés")
        self.assertEqual(text, "Buenos días, Señor")

    def test_no_target(self):
        target, text = babel.parse_translate_command("traduce hello world")
        self.assertIsNone(target)
        self.assertEqual(text, "hello world")

    def test_como_se_dice(self):
        target, text = babel.parse_translate_command("cómo se dice al alemán gracias")
        self.assertEqual(target, "alemán")
        self.assertEqual(text, "gracias")

    def test_a_preposition(self):
        target, text = babel.parse_translate_command("traduce a italiano buenos días")
        self.assertEqual(target, "italiano")
        self.assertEqual(text, "buenos días")

    def test_word_starting_like_lang_not_consumed(self):
        # "traduce hola" -> sin idioma; no debe tragarse "hola".
        target, text = babel.parse_translate_command("traduce hola")
        self.assertIsNone(target)
        self.assertEqual(text, "hola")


class TestPrompt(unittest.TestCase):
    def test_includes_target_and_text(self):
        p = babel.build_translation_prompt("hello", "francés")
        self.assertIn("francés", p)
        self.assertIn("hello", p)
        self.assertIn("JSON", p)


class TestParseResponse(unittest.TestCase):
    def test_clean_json(self):
        r = babel.parse_translation_response('{"source_language": "inglés", "translation": "hola"}')
        self.assertEqual(r["source_language"], "inglés")
        self.assertEqual(r["translation"], "hola")

    def test_json_embedded_in_text(self):
        raw = 'Claro:\n{"source_language":"inglés","translation":"hola mundo"}\nListo.'
        r = babel.parse_translation_response(raw)
        self.assertEqual(r["translation"], "hola mundo")

    def test_plain_text_fallback(self):
        r = babel.parse_translation_response("hola mundo")
        self.assertEqual(r["translation"], "hola mundo")
        self.assertEqual(r["source_language"], "desconocido")

    def test_empty(self):
        r = babel.parse_translation_response("")
        self.assertEqual(r["translation"], "")


class TestTranslate(unittest.TestCase):
    def test_translate_with_mocked_llm(self):
        with patch.object(babel, "_invoke_llm",
                          return_value='{"source_language":"inglés","translation":"hola"}'):
            r = babel.translate("hello", "español")
        self.assertEqual(r["translation"], "hola")
        self.assertEqual(r["target_language"], "español")
        self.assertEqual(r["source_language"], "inglés")

    def test_invalid_target_falls_back_to_default(self):
        captured = {}

        def fake(prompt):
            captured["prompt"] = prompt
            return '{"translation":"x"}'

        with patch.object(babel, "_invoke_llm", side_effect=fake):
            r = babel.translate("hola", "klingon")
        self.assertEqual(r["target_language"], babel.DEFAULT_TARGET)
        self.assertIn(babel.DEFAULT_TARGET, captured["prompt"])

    def test_empty_text_no_llm_call(self):
        with patch.object(babel, "_invoke_llm", side_effect=AssertionError("no debe llamarse")):
            r = babel.translate("   ", "inglés")
        self.assertEqual(r["translation"], "")

    def test_llm_error_is_safe(self):
        with patch.object(babel, "_invoke_llm", side_effect=RuntimeError("boom")):
            r = babel.translate("hello", "español")
        self.assertEqual(r["translation"], "")


if __name__ == "__main__":
    unittest.main()
