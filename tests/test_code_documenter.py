import os
import unittest
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.code_documenter import (
    scan_file_for_undocumented_elements,
    generate_docstring_for_element,
    write_documenter_changes
)
from tools.code_documenter_tool import (
    scan_undocumented_code,
    generate_pep257_docstrings
)
from core.pending_actions import PENDING_ACTION_FILE, clear_pending_action, execute_pending_action


class TestCodeDocumenter(unittest.TestCase):
    def setUp(self):
        clear_pending_action()
        self.test_dir = Path(__file__).resolve().parent / "temp_workspace_documenter"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear código de prueba
        self.test_file = self.test_dir / "test_code.py"
        self.test_file_content = """# Archivo de prueba
class MyTestClass:
    def method_one(self):
        print("Hello")

def my_function(x, y):
    \"\"\"Docstring existente.\"\"\"
    return x + y

@app.route('/api/data')
def get_data():
    pass
"""
        self.test_file.write_text(self.test_file_content, encoding="utf-8")

    def tearDown(self):
        clear_pending_action()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_scan_undocumented_code_finds_correct_elements(self):
        undoc = scan_file_for_undocumented_elements(str(self.test_file))
        # Debe encontrar MyTestClass (clase), method_one (método) y get_data (endpoint)
        # my_function ya tiene docstring, por lo que debe ignorarse
        self.assertEqual(len(undoc), 3)
        
        types = [el["type"] for el in undoc]
        self.assertIn("class", types)
        self.assertIn("method", types)
        self.assertIn("endpoint", types)
        
        names = [el["name"] for el in undoc]
        self.assertIn("MyTestClass", names)
        self.assertIn("method_one", names)
        self.assertIn("get_data", names)
        self.assertNotIn("my_function", names)

    @patch("core.code_documenter.ask_code_model")
    def test_generate_docstring_inserts_new(self, mock_ask):
        mock_ask.return_value = '"""Docstring generado para method_one."""'
        
        modified_code, diff, error = generate_docstring_for_element(
            str(self.test_file),
            target_name="method_one",
            parent_class="MyTestClass"
        )
        
        self.assertEqual(error, "")
        self.assertIn('"""Docstring generado para method_one."""', modified_code)
        self.assertIn("+        \"\"\"Docstring generado para method_one.\"\"\"", diff)
        
        # Verificar que conserve la indentación de 8 espacios (4 del class + 4 del method)
        self.assertIn("        \"\"\"Docstring generado para method_one.\"\"\"\n        print", modified_code)

    @patch("core.code_documenter.ask_code_model")
    def test_generate_docstring_replaces_existing(self, mock_ask):
        mock_ask.return_value = '"""Nuevo docstring."""'
        
        modified_code, diff, error = generate_docstring_for_element(
            str(self.test_file),
            target_name="my_function"
        )
        
        self.assertEqual(error, "")
        self.assertIn('"""Nuevo docstring."""', modified_code)
        self.assertNotIn('"""Docstring existente."""', modified_code)
        self.assertIn("-    \"\"\"Docstring existente.\"\"\"", diff)
        self.assertIn("+    \"\"\"Nuevo docstring.\"\"\"", diff)

    @patch("tools.code_documenter_tool.generate_docstring_for_element")
    def test_generate_pep257_docstrings_tool_saves_action(self, mock_gen):
        mock_gen.return_value = ("modified code here", "diff here", "")
        
        res = generate_pep257_docstrings.invoke({
            "file_path": str(self.test_file),
            "target_name": "method_one",
            "parent_class": "MyTestClass"
        })
        
        self.assertIn("he generado la documentación propuesta para `method_one`", res)
        self.assertTrue(PENDING_ACTION_FILE.exists())
        
        # Cargar y verificar
        data = json.loads(PENDING_ACTION_FILE.read_text(encoding="utf-8"))
        self.assertEqual(data["action_type"], "apply_docstrings")
        self.assertEqual(data["data"]["file_path"], str(self.test_file))
        self.assertEqual(data["data"]["target_name"], "method_one")
        self.assertEqual(data["data"]["modified_code"], "modified code here")

    def test_execute_pending_action_apply_docstrings(self):
        # Configurar la acción pendiente manualmente
        payload = {
            "action_type": "apply_docstrings",
            "data": {
                "file_path": str(self.test_file),
                "target_name": "method_one",
                "modified_code": "modified code applied successfully!"
            }
        }
        PENDING_ACTION_FILE.write_text(json.dumps(payload), encoding="utf-8")
        
        res = execute_pending_action()
        self.assertIn("He insertado los docstrings generados en el archivo", res)
        self.assertFalse(PENDING_ACTION_FILE.exists())
        
        # Verificar que el archivo se haya actualizado
        updated_content = self.test_file.read_text(encoding="utf-8")
        self.assertEqual(updated_content, "modified code applied successfully!")


if __name__ == "__main__":
    unittest.main()
