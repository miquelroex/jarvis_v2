import sys
import os
import unittest
import importlib
import inspect
from langchain_core.tools import BaseTool

class TestToolsLoad(unittest.TestCase):
    def test_all_tools_load(self):
        # Asegurar que el root del proyecto está en sys.path
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        tools_dir = os.path.join(project_root, "tools")
        self.assertTrue(os.path.exists(tools_dir), f"El directorio tools no existe en: {tools_dir}")

        loaded_tools_count = 0
        failures = []

        for filename in os.listdir(tools_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = f"tools.{filename[:-3]}"
                try:
                    # Intentar importar el módulo
                    module = importlib.import_module(module_name)
                    
                    # Buscar instancias de BaseTool
                    found_tool = False
                    for name, obj in inspect.getmembers(module):
                        if isinstance(obj, BaseTool):
                            found_tool = True
                            loaded_tools_count += 1
                            
                except Exception as e:
                    failures.append((filename, str(e)))

        self.assertEqual(len(failures), 0, f"Las siguientes herramientas fallaron al cargar:\n" + 
                         "\n".join([f"- {f[0]}: {f[1]}" for f in failures]))
        print(f"Se cargaron exitosamente {loaded_tools_count} herramientas sin fallos de importacion.")

if __name__ == "__main__":
    unittest.main()
