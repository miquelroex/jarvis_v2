import unittest
import os
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.router import smart_route
from tools.model_delegate import (
    ask_delegated_model,
    ask_reasoning_model,
    ask_code_model,
    ask_agent_model,
    ask_pro_model,
    ask_ultra_model,
    ask_gpt_model
)

class TestModelRouting(unittest.TestCase):

    def setUp(self):
        # Asegurarse de que no queden archivos temporales de acciones pendientes en logs/
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        for f in ["pending_action.json", "pending_model_request.json", "pending_terminal_command.json"]:
            p = logs_dir / f
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def tearDown(self):
        logs_dir = Path("logs")
        for f in ["pending_action.json", "pending_model_request.json", "pending_terminal_command.json"]:
            p = logs_dir / f
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    @patch("tools.model_delegate.ask_code_model")
    @patch("tools.model_delegate.ask_reasoning_model")
    @patch("tools.model_delegate.ask_ultra_model")
    @patch("tools.model_delegate.ask_pro_model")
    def test_smart_router_keywords(self, mock_pro, mock_ultra, mock_reason, mock_code):
        """Verifica que el router clasifique y derive correctamente según las palabras clave."""
        mock_code.invoke.return_value = "code_result"
        mock_reason.invoke.return_value = "reason_result"
        mock_ultra.invoke.return_value = "ultra_result"
        mock_pro.invoke.return_value = "pro_result"

        # 1. Código (usa palabra clave exacta "escribe un script")
        res1 = smart_route("Escribe un script de python para procesar logs")
        self.assertIsNotNone(res1)
        self.assertEqual(res1["type"], "delegation_code")
        mock_code.invoke.assert_called_with("Escribe un script de python para procesar logs")

        # 2. Razonamiento largo (usa palabra clave exacta "analisis largo")
        res2 = smart_route("Haz un analisis largo sobre el impacto de la IA")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["type"], "delegation_reasoning")
        mock_reason.invoke.assert_called_with("Haz un analisis largo sobre el impacto de la IA")

        # 3. Ultra (usa palabra clave exacta "modo ultra")
        res3 = smart_route("Usa el modo ultra para resolver este problema dificil")
        self.assertIsNotNone(res3)
        self.assertEqual(res3["type"], "delegation_ultra")
        mock_ultra.invoke.assert_called_with("Usa el modo ultra para resolver este problema dificil")

        # 4. Pro (usa palabra clave exacta "modo pro")
        res4 = smart_route("Usa el modo pro para esta pregunta")
        self.assertIsNotNone(res4)
        self.assertEqual(res4["type"], "delegation_pro")
        mock_pro.invoke.assert_called_with("Usa el modo pro para esta pregunta")

    @patch("google.genai.Client")
    @patch("tools.model_delegate.get_llm")
    def test_providers_mapping(self, mock_get_llm, mock_genai_client):
        """Verifica que THINK use google_ai_studio de forma nativa y otros usen openrouter."""
        # Configurar mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(content="openrouter_response")
        mock_get_llm.return_value = mock_llm_instance

        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "google_response"
        mock_response.usage_metadata = None
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_genai_client.return_value = mock_client_instance

        env_dict = {
            "OPENROUTER_API_KEY": "sk-or-test-key",
            "GOOGLE_API_KEY": "AIzaSy-test-key",
            "JARVIS_MODEL_THINK": "gemini-3.5-flash",
            "JARVIS_MODEL_CODE": "claude-sonnet-4.6"
        }

        with patch.dict(os.environ, env_dict):
            # 1. Invocar THINK (Debe ir a Google AI Studio obligatoriamente)
            res_think = ask_delegated_model(
                tool_name="test_think",
                model_env="JARVIS_MODEL_THINK",
                fallback_model="gemini-3.5-flash",
                prompt="¿Cuál es el sentido de la vida?",
                require_confirmation=False
            )
            self.assertEqual(res_think, "google_response")
            mock_genai_client.assert_called_once_with(api_key="AIzaSy-test-key")

            # 2. Invocar CODE (Debe ir a OpenRouter por defecto)
            res_code = ask_delegated_model(
                tool_name="test_code",
                model_env="JARVIS_MODEL_CODE",
                fallback_model="claude-sonnet-4.6",
                prompt="def hello(): pass",
                require_confirmation=False
            )
            self.assertEqual(res_code, "openrouter_response")
            mock_get_llm.assert_called_once_with("claude-sonnet-4.6", temperature=0.2)

    def test_confirmation_handling(self):
        """Verifica que las peticiones que requieren confirmación guarden la acción pendiente."""
        env_dict = {
            "JARVIS_MODEL_PRO": "openai/gpt-5.5",
            "JARVIS_REQUIRE_CONFIRM_PRO": "True"
        }

        with patch.dict(os.environ, env_dict):
            res = ask_pro_model("Explica la física cuántica")
            self.assertIn("confirmo modelo", res)
            self.assertTrue(Path("logs/pending_action.json").exists())

            # Leer archivo para verificar contenido guardado
            data = json.loads(Path("logs/pending_action.json").read_text(encoding="utf-8"))
            self.assertEqual(data["action_type"], "model")
            self.assertEqual(data["data"]["model_env"], "JARVIS_MODEL_PRO")
            self.assertEqual(data["data"]["prompt"], "Explica la física cuántica")

    @patch("tools.model_delegate.ask_pro_model")
    @patch("tools.model_delegate.ask_ultra_model")
    def test_gpt_alias_compat(self, mock_ultra, mock_pro):
        """Verifica que ask_gpt_model actúe como un alias dinámico hacia PRO o ULTRA."""
        mock_pro.return_value = "pro_called"
        mock_ultra.return_value = "ultra_called"

        # 1. Petición normal -> PRO
        res1 = ask_gpt_model("Dime una receta de cocina")
        self.assertEqual(res1, "pro_called")
        mock_pro.assert_called_once_with("Dime una receta de cocina")

        # 2. Petición ultra/pro -> ULTRA
        res2 = ask_gpt_model("Usa gpt-5.5-pro para esta simulación")
        self.assertEqual(res2, "ultra_called")
        mock_ultra.assert_called_once_with("Usa gpt-5.5-pro para esta simulación")

if __name__ == "__main__":
    unittest.main()
