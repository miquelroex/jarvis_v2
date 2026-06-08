import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

from core.log_test_generator import extract_referenced_files, generate_reproduction_test

class TestLogTestGenerator(unittest.TestCase):
    def setUp(self):
        self.test_log_path = Path("logs/test_exception_unit.json")
        self.dummy_py_file = Path("core/dummy_for_test.py")
        
        # Crear archivos dummy si es necesario
        self.dummy_py_file.parent.mkdir(exist_ok=True)
        self.dummy_py_file.write_text("def error_func():\n    raise ValueError('dummy error')\n", encoding="utf-8")
        
        # Crear un JSON log de excepción dummy
        self.log_data = {
            "command": "python core/dummy_for_test.py",
            "stdout": "",
            "stderr": (
                "Traceback (most recent call last):\n"
                "  File \"core/dummy_for_test.py\", line 2, in error_func\n"
                "ValueError: dummy error"
            ),
            "timestamp": 12345678.9
        }
        
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        self.test_log_path.write_text(json.dumps(self.log_data), encoding="utf-8")
        self.generated_files = []

    def tearDown(self):
        # Limpieza de archivos creados
        if self.test_log_path.exists():
            self.test_log_path.unlink()
        if self.dummy_py_file.exists():
            self.dummy_py_file.unlink()
            
        for path in self.generated_files:
            file_path = Path(path)
            if file_path.exists():
                file_path.unlink()

    def test_extract_referenced_files(self):
        error_text = (
            "Traceback (most recent call last):\n"
            "  File \"core/dummy_for_test.py\", line 2, in error_func\n"
            "ValueError: dummy error"
        )
        files = extract_referenced_files(error_text)
        self.assertIn("core/dummy_for_test.py", files)

    @patch("core.log_test_generator.get_llm")
    @patch("subprocess.run")
    def test_generate_reproduction_test_success(self, mock_subprocess_run, mock_get_llm):
        # Configurar mock de LLM
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        
        mock_response = MagicMock()
        mock_response.content = (
            "```python\n"
            "import unittest\n"
            "class TestDummyError(unittest.TestCase):\n"
            "    def test_func(self):\n"
            "        raise ValueError('dummy error')\n"
            "```"
        )
        mock_llm_instance.invoke.return_value = mock_response

        # Configurar mock de subprocess.run para simular fallo de test (reproducción exitosa)
        mock_result = MagicMock()
        mock_result.returncode = 1  # Esperamos que falle el test reproducido
        mock_result.stdout = "Test failed as expected"
        mock_result.stderr = "ValueError: dummy error"
        mock_subprocess_run.return_value = mock_result

        # Ejecutar generación
        res = generate_reproduction_test(str(self.test_log_path))
        
        self.assertTrue(res["success"])
        self.assertTrue(res["reproduced"])
        self.assertIn("test_file", res)
        
        # Registrar para borrar luego
        self.generated_files.append(res["test_file"])
        
        # Verificar que el archivo se creó físicamente y contiene el código del test
        test_file = Path(res["test_file"])
        self.assertTrue(test_file.exists())
        content = test_file.read_text(encoding="utf-8")
        self.assertIn("class TestDummyError", content)

if __name__ == "__main__":
    unittest.main()
