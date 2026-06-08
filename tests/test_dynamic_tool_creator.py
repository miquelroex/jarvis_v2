import sys
import os
import unittest
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.agent_manager import init_agent, get_executor, reload_agent
from tools.dynamic_tool_creator import create_dynamic_tool

class TestDynamicToolCreator(unittest.TestCase):
    def setUp(self):
        init_agent()
        self.created_tools = []
        self.original_safe_mode = os.environ.get("JARVIS_SAFE_MODE")
        os.environ["JARVIS_SAFE_MODE"] = "False"

    def tearDown(self):
        # Restaurar JARVIS_SAFE_MODE original
        if self.original_safe_mode is not None:
            os.environ["JARVIS_SAFE_MODE"] = self.original_safe_mode
        elif "JARVIS_SAFE_MODE" in os.environ:
            del os.environ["JARVIS_SAFE_MODE"]

        # Eliminar las herramientas dinámicas creadas para las pruebas
        tools_dir = Path(project_root) / "tools"
        for tool_name in self.created_tools:
            filepath = tools_dir / f"{tool_name}.py"
            if filepath.exists():
                try:
                    filepath.unlink()
                except Exception:
                    pass
            # Limpiar también la caché de python para ese módulo
            pycache_dir = tools_dir / "__pycache__"
            if pycache_dir.exists():
                for f in pycache_dir.glob(f"{tool_name}*.pyc"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
                        
            # Eliminar del sys.modules si se cargó
            module_name = f"tools.{tool_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]

        # Recargar para limpiar el estado del agente y dejarlo como estaba
        try:
            reload_agent()
        except Exception:
            pass

    def test_syntax_validation(self):
        # Enviar código con error de sintaxis
        bad_code = "def bad_tool(text: str)\n    return text"  # Falta el ':'
        res = create_dynamic_tool.invoke({
            "name": "test_bad_syntax",
            "description": "should fail",
            "python_code": bad_code
        })
        self.assertIn("error de sintaxis", res.lower())
        
        # Verificar que no se creó ningún archivo
        tools_dir = Path(project_root) / "tools"
        self.assertFalse((tools_dir / "test_bad_syntax.py").exists())

    def test_tool_creation_and_registration(self):
        tool_name = "test_dummy_tool"
        self.created_tools.append(tool_name)
        
        good_code = """
@tool
def test_dummy_tool(text: str) -> str:
    \"\"\"Un dummy tool de test.\"\"\"
    return f"Respuesta dummy: {text}"
"""
        res = create_dynamic_tool.invoke({
            "name": tool_name,
            "description": "Calculates a dummy value",
            "python_code": good_code
        })
        
        self.assertIn("creada, validada y registrada con éxito", res)
        
        # Verificar que el archivo existe
        tools_dir = Path(project_root) / "tools"
        self.assertTrue((tools_dir / f"{tool_name}.py").exists())
        
        # Verificar que la herramienta está registrada en el executor
        registered_tools = get_executor().tools
        matching_tool = next((t for t in registered_tools if t.name == tool_name), None)
        self.assertIsNotNone(matching_tool)
        
        # Probar a invocar la herramienta registrada
        val = matching_tool.invoke("Hola Test")
        self.assertEqual(val, "Respuesta dummy: Hola Test")

    def test_automatic_imports_and_decorations(self):
        tool_name = "test_no_decor_tool"
        self.created_tools.append(tool_name)
        
        # Código sin importación ni decorador
        raw_code = """
def test_no_decor_tool(x: int) -> int:
    \"\"\"Duplica el entero dado.\"\"\"
    return x * 2
"""
        res = create_dynamic_tool.invoke({
            "name": tool_name,
            "description": "Multiplica por dos",
            "python_code": raw_code
        })
        
        self.assertIn("creada, validada y registrada con éxito", res)
        
        # Verificar archivo y contenido inyectado
        tools_dir = Path(project_root) / "tools"
        file_path = tools_dir / f"{tool_name}.py"
        self.assertTrue(file_path.exists())
        
        content = file_path.read_text(encoding="utf-8")
        self.assertIn("from langchain.tools import tool", content)
        self.assertIn("@tool", content)
        
        # Verificar registro y ejecución
        registered_tools = get_executor().tools
        matching_tool = next((t for t in registered_tools if t.name == tool_name), None)
        self.assertIsNotNone(matching_tool)
        
        val = matching_tool.invoke({"x": 21})
        self.assertEqual(val, 42)

    def test_safe_mode_interception(self):
        os.environ["JARVIS_SAFE_MODE"] = "True"
        tool_name = "test_safe_tool"
        self.created_tools.append(tool_name)
        
        raw_code = """
@tool
def test_safe_tool() -> str:
    \"\"\"Docstring.\"\"\"
    return "Safe Hello"
"""
        from core.pending_actions import PENDING_ACTION_FILE, execute_pending_action, clear_pending_action
        clear_pending_action()
        
        # Intentar crear bajo modo seguro
        res = create_dynamic_tool.invoke({
            "name": tool_name,
            "description": "Safe tool",
            "python_code": raw_code
        })
        
        # 1. Comprobar que intercepta y pide confirmación
        self.assertIn("interceptada bajo modo seguro", res)
        self.assertTrue(PENDING_ACTION_FILE.exists())
        
        # 2. Confirmar la creación de la tool
        confirm_res = execute_pending_action()
        self.assertIn("creada, validada y registrada con éxito", confirm_res)
        self.assertFalse(PENDING_ACTION_FILE.exists())
        
        # 3. Comprobar que el archivo se creó finalmente
        tools_dir = Path(project_root) / "tools"
        self.assertTrue((tools_dir / f"{tool_name}.py").exists())

if __name__ == "__main__":
    unittest.main()
