import os
import unittest
from unittest.mock import patch, MagicMock
import json

# Import central module
import core.jarvis_integrity as integrity
from tools.filesystem import WORKSPACE_ROOT

# Ruta de core dentro del proyecto real (varía según el entorno/CI), necesaria
# para que Path.relative_to(WORKSPACE_ROOT) no lance ValueError.
CORE_DIR = os.path.join(WORKSPACE_ROOT, "core")

class TestJarvisIntegrity(unittest.TestCase):

    @patch("core.jarvis_integrity.walk")
    @patch("core.jarvis_integrity.Path.read_text")
    def test_check_codebase_syntax_success(self, mock_read, mock_walk):
        # Simular archivos válidos para las 3 carpetas (core, tools, gui)
        mock_walk.side_effect = [
            [(CORE_DIR, [], ["module1.py"])],
            [],
            []
        ]
        mock_read.return_value = "def my_func():\n    pass\n"
        
        failures = integrity.check_codebase_syntax()
        self.assertEqual(failures, [])

    @patch("core.jarvis_integrity.walk")
    @patch("core.jarvis_integrity.Path.read_text")
    def test_check_codebase_syntax_failure(self, mock_read, mock_walk):
        # Simular un archivo con error de sintaxis en core, y carpetas vacías en tools/gui
        mock_walk.side_effect = [
            [(CORE_DIR, [], ["module1.py"])],
            [],
            []
        ]
        mock_read.return_value = "def invalid_func(\n" # Falta paréntesis
        
        failures = integrity.check_codebase_syntax()
        self.assertEqual(len(failures), 1)
        self.assertIn("Error de sintaxis", failures[0]["error"])
        self.assertEqual(failures[0]["file"], "core/module1.py")

    @patch("core.jarvis_integrity.listdir")
    @patch("core.jarvis_integrity.import_module")
    def test_check_tools_load_status_success(self, mock_import, mock_listdir):
        mock_listdir.return_value = ["valid_tool.py", "__init__.py"]
        mock_import.return_value = MagicMock()
        
        failures = integrity.check_tools_load_status()
        self.assertEqual(failures, [])

    @patch("core.jarvis_integrity.listdir")
    @patch("core.jarvis_integrity.import_module")
    def test_check_tools_load_status_failure(self, mock_import, mock_listdir):
        mock_listdir.return_value = ["broken_tool.py"]
        mock_import.side_effect = ImportError("No module named 'missing'")
        
        failures = integrity.check_tools_load_status()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["file"], "tools/broken_tool.py")
        self.assertIn("No module named 'missing'", failures[0]["error"])

    @patch("core.jarvis_integrity.os.getenv")
    def test_check_env_variables(self, mock_getenv):
        # Simular algunas configuradas y otras no
        mock_getenv.side_effect = lambda k: "some-key" if k != "TAVILY_API_KEY" else ""
        
        results = integrity.check_env_variables()
        
        openai_res = next(item for item in results if item["name"] == "OPENROUTER_API_KEY")
        tavily_res = next(item for item in results if item["name"] == "TAVILY_API_KEY")
        
        self.assertTrue(openai_res["configured"])
        self.assertFalse(tavily_res["configured"])

    @patch("core.jarvis_integrity.subprocess.run")
    def test_run_unit_tests_success(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stderr = "Ran 86 tests in 12.000s\n\nOK"
        mock_run.return_value = mock_res
        
        stats = integrity.run_unit_tests()
        
        self.assertTrue(stats["passed"])
        self.assertEqual(stats["ran"], 86)
        self.assertEqual(stats["failures"], 0)
        self.assertEqual(stats["errors"], 0)

    @patch("core.jarvis_integrity.subprocess.run")
    def test_run_unit_tests_failure(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 1
        mock_res.stderr = "Ran 86 tests in 12.000s\n\nFAILED (failures=2, errors=1)"
        mock_run.return_value = mock_res
        
        stats = integrity.run_unit_tests()
        
        self.assertFalse(stats["passed"])
        self.assertEqual(stats["ran"], 86)
        self.assertEqual(stats["failures"], 2)
        self.assertEqual(stats["errors"], 1)

    @patch("core.jarvis_integrity.check_codebase_syntax")
    @patch("core.jarvis_integrity.check_tools_load_status")
    @patch("core.jarvis_integrity.check_env_variables")
    @patch("core.jarvis_integrity.run_unit_tests")
    @patch("core.jarvis_integrity.Path.write_text")
    @patch("core.jarvis_integrity.Path.mkdir")
    def test_run_integrity_check_secure(self, mock_mkdir, mock_write, mock_tests, mock_env, mock_tools, mock_syntax):
        mock_syntax.return_value = []
        mock_tools.return_value = []
        mock_env.return_value = [{"name": "OPENROUTER_API_KEY", "configured": True}]
        mock_tests.return_value = {"ran": 86, "failures": 0, "errors": 0, "passed": True}
        
        report = integrity.run_integrity_check()
        
        self.assertEqual(report["status"], "secure")
        mock_write.assert_called_once()
        written_data = json.loads(mock_write.call_args[0][0])
        self.assertEqual(written_data["status"], "secure")

    @patch("core.jarvis_integrity.check_codebase_syntax")
    @patch("core.jarvis_integrity.check_tools_load_status")
    @patch("core.jarvis_integrity.check_env_variables")
    @patch("core.jarvis_integrity.run_unit_tests")
    @patch("core.jarvis_integrity.Path.write_text")
    @patch("core.jarvis_integrity.Path.mkdir")
    @patch("tools.voice.speak")
    @patch("core.telegram_bot.bot")
    def test_run_integrity_check_critical(self, mock_bot, mock_speak, mock_mkdir, mock_write, mock_tests, mock_env, mock_tools, mock_syntax):
        # Reset de transiciones
        integrity.LAST_STATUS = "secure"
        
        mock_syntax.return_value = [{"file": "core/app.py", "error": "Syntax Error"}]
        mock_tools.return_value = []
        mock_env.return_value = [{"name": "OPENROUTER_API_KEY", "configured": True}]
        mock_tests.return_value = {"ran": 86, "failures": 0, "errors": 0, "passed": True}
        
        # Simular bot telegram
        mock_bot.send_message = MagicMock()
        
        with patch("core.jarvis_integrity.os.getenv", return_value="123456"):
            report = integrity.run_integrity_check()
            
        self.assertEqual(report["status"], "critical")
        # Verificar que se alertó al cambiar de estado
        mock_speak.assert_called_once()
        mock_bot.send_message.assert_called_once()

if __name__ == "__main__":
    unittest.main()
