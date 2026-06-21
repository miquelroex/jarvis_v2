"""Tests de la resolución de alias de modelos (core/model_config.py).

Módulo ligero: se prueba de forma aislada (no importa agent_manager ni tools).
"""
import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.model_config as mc


class TestModelConfig(unittest.TestCase):

    def setUp(self):
        mc._aliases_cache = None

    def tearDown(self):
        mc._aliases_cache = None

    def test_resolve_known_alias_uses_env_default(self):
        # Sin la variable definida, resuelve con el default embebido.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_MODEL_CODE", None)
            model = mc.resolve_model_alias("codigo", force_reload=True)
        self.assertEqual(model, "qwen/qwen3-coder")

    def test_resolve_respects_env_override(self):
        with patch.dict(os.environ, {"JARVIS_MODEL_GEMINI": "custom/gemini-x"}):
            model = mc.resolve_model_alias("gemini", force_reload=True)
        self.assertEqual(model, "custom/gemini-x")

    def test_unknown_alias_returns_none(self):
        self.assertIsNone(mc.resolve_model_alias("inventado", force_reload=True))

    def test_empty_alias_returns_none(self):
        self.assertIsNone(mc.resolve_model_alias("", force_reload=True))

    def test_alias_case_insensitive(self):
        with patch.dict(os.environ, {"JARVIS_MODEL_GPT": "openai/x"}):
            self.assertEqual(mc.resolve_model_alias("GPT", force_reload=True), "openai/x")

    def test_unconfigured_model_returns_none(self):
        # ULTRA no tiene default embebido y normalmente no está en el entorno.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_MODEL_ULTRA", None)
            self.assertIsNone(mc.resolve_model_alias("ultra", force_reload=True))

    def test_available_aliases_includes_known(self):
        aliases = mc.available_aliases()
        self.assertIn("gemini", aliases)
        self.assertIn("codigo", aliases)

    def test_file_overrides_alias_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "model_aliases.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"turbo": "JARVIS_MODEL_GPT"}, f)
            with patch.object(mc, "_MODEL_ALIASES_PATH", path), \
                 patch.dict(os.environ, {"JARVIS_MODEL_GPT": "openai/turbo"}):
                model = mc.resolve_model_alias("turbo", force_reload=True)
        self.assertEqual(model, "openai/turbo")

    def test_defaults_match_shipped_config(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        shipped = os.path.join(repo_root, "config", "model_aliases.json")
        self.assertTrue(os.path.exists(shipped), "Falta config/model_aliases.json")
        with open(shipped, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data, mc._DEFAULT_ALIASES)


if __name__ == "__main__":
    unittest.main()
