"""Tests del cerebro conversacional reutilizable (core/conversation.py)."""
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.conversation as conv


class TestModelDisplay(unittest.TestCase):
    def test_fast_command(self):
        self.assertEqual(conv.model_display_for_route("fast_command"), "Comando Local")

    def test_gemini(self):
        with patch.dict(os.environ, {"JARVIS_MODEL_GEMINI": "gemini-x"}):
            self.assertEqual(conv.model_display_for_route("gemini_direct"), "gemini-x")

    def test_code_and_reasoning(self):
        with patch.dict(os.environ, {"JARVIS_MODEL_CODE": "coder-x", "JARVIS_MODEL_THINK": "think-x"}):
            self.assertEqual(conv.model_display_for_route("code_delegate"), "coder-x")
            self.assertEqual(conv.model_display_for_route("reasoning_delegate"), "think-x")

    def test_unknown_default(self):
        self.assertEqual(conv.model_display_for_route("algo_raro"), "Procesador Interno")
        self.assertEqual(conv.model_display_for_route(""), "Procesador Interno")


class TestGetResponseRoute(unittest.TestCase):
    def test_route_hit_returns_content_and_model(self):
        fake_router = types.SimpleNamespace(
            smart_route=lambda t: {"content": "Son las tres.", "type": "fast_command"})
        with patch.dict(sys.modules, {"core.router": fake_router}):
            content, model = conv.get_response("que hora es")
        self.assertEqual(content, "Son las tres.")
        self.assertEqual(model, "Comando Local")

    def test_route_miss_delegates_to_agent(self):
        fake_router = types.SimpleNamespace(smart_route=lambda t: None)

        class _CB:
            prompt_tokens = 10
            completion_tokens = 5
            def __enter__(self): return self
            def __exit__(self, *a): return False

        fake_executor = types.SimpleNamespace(invoke=lambda d: {"output": "Respuesta del agente."})
        fake_am = types.SimpleNamespace(get_executor=lambda: fake_executor)
        fake_logging = types.SimpleNamespace(log_model_usage=lambda **k: None)
        fake_callbacks = types.SimpleNamespace(get_openai_callback=lambda: _CB())

        with patch.dict(sys.modules, {
            "core.router": fake_router,
            "core.agent_manager": fake_am,
            "core.model_logging": fake_logging,
            "langchain_community.callbacks": fake_callbacks,
        }), patch.dict(os.environ, {"JARVIS_MODEL_DEFAULT": "modelo-x"}):
            content, model = conv.get_response("hazme un análisis")
        self.assertEqual(content, "Respuesta del agente.")
        self.assertEqual(model, "modelo-x")

    def test_agent_error_logs_and_raises(self):
        fake_router = types.SimpleNamespace(smart_route=lambda t: None)

        class _CB:
            prompt_tokens = 0
            completion_tokens = 0
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def _boom(d):
            raise RuntimeError("fallo del agente")

        logged = []
        fake_executor = types.SimpleNamespace(invoke=_boom)
        fake_am = types.SimpleNamespace(get_executor=lambda: fake_executor)
        fake_logging = types.SimpleNamespace(log_model_usage=lambda **k: logged.append(k))
        fake_callbacks = types.SimpleNamespace(get_openai_callback=lambda: _CB())

        with patch.dict(sys.modules, {
            "core.router": fake_router,
            "core.agent_manager": fake_am,
            "core.model_logging": fake_logging,
            "langchain_community.callbacks": fake_callbacks,
        }):
            with self.assertRaises(RuntimeError):
                conv.get_response("algo")
        self.assertEqual(len(logged), 1)  # registró el intento fallido


if __name__ == "__main__":
    unittest.main()
