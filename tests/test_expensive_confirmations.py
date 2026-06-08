import sys
import os
import unittest
import json
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Asegurar una clave temporal para pasar la validación del API Key en el test
if not os.getenv("OPENROUTER_API_KEY"):
    os.environ["OPENROUTER_API_KEY"] = "mock-key"

from tools.model_delegate import ask_pro_model, ask_gpt_model, PENDING_MODEL_REQUEST

class TestExpensiveConfirmations(unittest.TestCase):
    def setUp(self):
        # Limpiar cualquier solicitud previa
        if PENDING_MODEL_REQUEST.exists():
            try:
                PENDING_MODEL_REQUEST.unlink()
            except Exception:
                pass

    def tearDown(self):
        # Limpiar después de la prueba
        if PENDING_MODEL_REQUEST.exists():
            try:
                PENDING_MODEL_REQUEST.unlink()
            except Exception:
                pass

    def test_pro_model_requires_confirmation(self):
        prompt = "Escribe un análisis exhaustivo."
        response = ask_pro_model.invoke(prompt)

        # 1. Comprobar que devuelve el mensaje de confirmación
        self.assertIn("Es un modelo de coste alto", response)
        self.assertIn("confirmo modelo", response)

        # 2. Comprobar que se ha creado el archivo temporal de solicitud
        self.assertTrue(PENDING_MODEL_REQUEST.exists())

        # 3. Comprobar que el contenido del archivo es correcto
        data = json.loads(PENDING_MODEL_REQUEST.read_text(encoding="utf-8"))
        self.assertEqual(data["tool_name"], "ask_pro_model")
        self.assertEqual(data["model_env"], "JARVIS_MODEL_PRO")
        self.assertEqual(data["prompt"], prompt)

    def test_gpt_model_requires_confirmation(self):
        prompt = "Hazme un resumen usando GPT."
        response = ask_gpt_model.invoke(prompt)

        # 1. Comprobar que devuelve el mensaje de confirmación
        self.assertIn("Es un modelo de coste alto", response)
        self.assertIn("confirmo modelo", response)

        # 2. Comprobar que se ha creado el archivo temporal de solicitud
        self.assertTrue(PENDING_MODEL_REQUEST.exists())

        # 3. Comprobar que el contenido del archivo es correcto
        data = json.loads(PENDING_MODEL_REQUEST.read_text(encoding="utf-8"))
        self.assertEqual(data["tool_name"], "ask_gpt_model")
        self.assertEqual(data["model_env"], "JARVIS_MODEL_GPT")
        self.assertEqual(data["prompt"], prompt)

if __name__ == "__main__":
    unittest.main()
