"""Tests del loader de keywords del enrutador (core/router_config.py).

Se prueba el loader de forma aislada (no importa core/router.py ni tools), para
no arrastrar dependencias pesadas.
"""
import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.router_config as router_config


class TestRouterKeywords(unittest.TestCase):

    def setUp(self):
        # Limpiar la caché del módulo antes de cada test.
        router_config._router_keywords_cache = None

    def tearDown(self):
        router_config._router_keywords_cache = None

    def test_defaults_when_file_missing(self):
        with patch.object(router_config, "_ROUTER_KEYWORDS_PATH", os.path.join("no", "existe.json")):
            kw = router_config.get_router_keywords(force_reload=True)
        # Todos los grupos esperados presentes con sus defaults.
        self.assertEqual(set(kw.keys()), set(router_config._DEFAULT_ROUTER_KEYWORDS.keys()))
        self.assertIn("gemini", kw["gemini"])
        self.assertIn("kimi", kw["pro"])

    def test_file_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "router_keywords.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"gemini": ["bardo", "geminis"]}, f)
            with patch.object(router_config, "_ROUTER_KEYWORDS_PATH", path):
                kw = router_config.get_router_keywords(force_reload=True)
        # El grupo definido en el archivo sustituye al default...
        self.assertEqual(kw["gemini"], ["bardo", "geminis"])
        # ...y los grupos no definidos conservan el default.
        self.assertEqual(kw["pro"], router_config._DEFAULT_ROUTER_KEYWORDS["pro"])

    def test_invalid_json_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "router_keywords.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{ esto no es json valido ]")
            with patch.object(router_config, "_ROUTER_KEYWORDS_PATH", path):
                kw = router_config.get_router_keywords(force_reload=True)
        self.assertEqual(kw, router_config._DEFAULT_ROUTER_KEYWORDS)

    def test_non_dict_json_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "router_keywords.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(["esto", "es", "una", "lista"], f)
            with patch.object(router_config, "_ROUTER_KEYWORDS_PATH", path):
                kw = router_config.get_router_keywords(force_reload=True)
        self.assertEqual(kw, router_config._DEFAULT_ROUTER_KEYWORDS)

    def test_empty_group_keeps_default(self):
        # Un grupo presente pero vacío no debe vaciar el default (evita romper el routing).
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "router_keywords.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"pro": []}, f)
            with patch.object(router_config, "_ROUTER_KEYWORDS_PATH", path):
                kw = router_config.get_router_keywords(force_reload=True)
        self.assertEqual(kw["pro"], router_config._DEFAULT_ROUTER_KEYWORDS["pro"])

    def test_keywords_lowercased(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "router_keywords.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"gpt": ["ChatGPT", "GPT"]}, f)
            with patch.object(router_config, "_ROUTER_KEYWORDS_PATH", path):
                kw = router_config.get_router_keywords(force_reload=True)
        self.assertEqual(kw["gpt"], ["chatgpt", "gpt"])

    def test_cache_returns_same_object(self):
        with patch.object(router_config, "_ROUTER_KEYWORDS_PATH", os.path.join("no", "existe.json")):
            first = router_config.get_router_keywords(force_reload=True)
            second = router_config.get_router_keywords()
        self.assertIs(first, second)

    def test_defaults_match_shipped_config_file(self):
        # El archivo real config/router_keywords.json debe coincidir con los defaults
        # embebidos para que el comportamiento sea idéntico con o sin archivo.
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        shipped = os.path.join(repo_root, "config", "router_keywords.json")
        self.assertTrue(os.path.exists(shipped), "Falta config/router_keywords.json")
        with open(shipped, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data, router_config._DEFAULT_ROUTER_KEYWORDS)


if __name__ == "__main__":
    unittest.main()
