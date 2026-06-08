import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.peer_review_tool import audit_code_architecture, PEER_REVIEW_HTML

class TestPeerReviewTool(unittest.TestCase):
    def setUp(self):
        # Limpieza de archivo de reporte previo
        if PEER_REVIEW_HTML.exists():
            try:
                PEER_REVIEW_HTML.unlink()
            except Exception:
                pass
        
        # Crear un archivo dummy para auditar en las pruebas
        self.dummy_file = Path("tests/dummy_to_audit.py")
        self.dummy_file.write_text("def my_dummy_function():\n    pass\n", encoding="utf-8")

    def tearDown(self):
        # Limpieza final
        if PEER_REVIEW_HTML.exists():
            try:
                PEER_REVIEW_HTML.unlink()
            except Exception:
                pass
        if self.dummy_file.exists():
            try:
                self.dummy_file.unlink()
            except Exception:
                pass

    def test_path_safety_check(self):
        # Intentar acceder a un archivo fuera del workspace
        resp = audit_code_architecture("../outside_file.py")
        self.assertTrue("Acceso denegado" in resp)

    def test_file_not_found(self):
        # Intentar auditar un archivo inexistente
        resp = audit_code_architecture("non_existent_file_xyz.py")
        self.assertTrue("no existe en el espacio de trabajo" in resp)

    @patch("tools.peer_review_tool.get_llm")
    def test_audit_execution_success(self, mock_get_llm):
        # Mock del LLM para retornar respuestas predeterminadas en las 4 fases
        mock_response_purista = MagicMock()
        mock_response_purista.content = "Crítica Purista de Clean Code"
        
        mock_response_pragmatico = MagicMock()
        mock_response_pragmatico.content = "Réplica Pragmática de Simplicidad"
        
        mock_response_replica = MagicMock()
        mock_response_replica.content = "Defensa Purista final"
        
        mock_response_veredicto = MagicMock()
        mock_response_veredicto.content = """
        VEREDICTO:
        Este es el veredicto conciliado de Jarvis.
        CODIGO REFACTORIZADO:
        ```python
        def refactored_dummy():
            pass
        ```
        """
        
        mock_llm_instance = MagicMock()
        # Definir la secuencia de retorno de las invocaciones del LLM
        mock_llm_instance.invoke.side_effect = [
            mock_response_purista,
            mock_response_pragmatico,
            mock_response_replica,
            mock_response_veredicto
        ]
        mock_get_llm.return_value = mock_llm_instance

        # Ejecutar la auditoría
        resp = audit_code_architecture("tests/dummy_to_audit.py")
        
        # Verificar que se generó y guardó el HTML del reporte
        self.assertTrue(PEER_REVIEW_HTML.exists())
        html_content = PEER_REVIEW_HTML.read_text(encoding="utf-8")
        self.assertTrue("TWIN-AGENT PEER REVIEW" in html_content)
        self.assertTrue("Crítica Purista de Clean Code" in html_content)
        self.assertTrue("Réplica Pragmática de Simplicidad" in html_content)
        self.assertTrue("def refactored_dummy" in html_content)

        # Verificar el formato de retorno Markdown interactivo
        self.assertTrue("VEREDICTO" in resp)
        self.assertTrue("refactored_dummy" in resp)
        self.assertTrue("<html" in resp)

if __name__ == "__main__":
    unittest.main()
