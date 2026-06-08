import os
import unittest
from unittest.mock import patch, MagicMock
from core.error_autofixer import extract_error_summary, diagnose_and_suggest_fix
from tools.terminal import run_terminal_command, PENDING_COMMAND_FILE

class TestErrorAutofixer(unittest.TestCase):
    
    def setUp(self):
        # Asegurar variables de entorno limpias
        self.original_env = os.environ.get("JARVIS_ERROR_AUTOFIX_ENABLED")
        os.environ["JARVIS_ERROR_AUTOFIX_ENABLED"] = "True"
        if PENDING_COMMAND_FILE.exists():
            try:
                PENDING_COMMAND_FILE.unlink()
            except Exception:
                pass

    def tearDown(self):
        if self.original_env is not None:
            os.environ["JARVIS_ERROR_AUTOFIX_ENABLED"] = self.original_env
        else:
            os.environ.pop("JARVIS_ERROR_AUTOFIX_ENABLED", None)
            
        if PENDING_COMMAND_FILE.exists():
            try:
                PENDING_COMMAND_FILE.unlink()
            except Exception:
                pass

    def test_extract_error_summary_traceback(self):
        tb = (
            "Traceback (most recent call last):\n"
            "  File \"test_script.py\", line 3, in <module>\n"
            "    print(1/0)\n"
            "ZeroDivisionError: division by zero\n"
        )
        summary = extract_error_summary(tb)
        self.assertEqual(summary, "ZeroDivisionError: division by zero")

    def test_extract_error_summary_generic_error(self):
        stderr = "make: *** [build] Error 2"
        summary = extract_error_summary(stderr)
        self.assertEqual(summary, "make: *** [build] Error 2")

        stderr_lines = "Some line\nAn error occurred on file.js:5\nSome other line"
        summary = extract_error_summary(stderr_lines)
        self.assertEqual(summary, "An error occurred on file.js:5")

    def test_diagnose_disabled(self):
        os.environ["JARVIS_ERROR_AUTOFIX_ENABLED"] = "False"
        res = diagnose_and_suggest_fix("python script.py", "", "ZeroDivisionError: division by zero")
        self.assertEqual(res, "")

    @patch("core.error_autofixer.is_internet_available")
    @patch("core.error_autofixer.get_llm")
    @patch("core.error_autofixer.search_error_solutions")
    def test_diagnose_and_suggest_fix_flow(self, mock_search, mock_get_llm, mock_is_internet):
        mock_is_internet.return_value = True
        mock_search.return_value = "Solución mockeada encontrada en internet."
        
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Explicación del error: División por cero.\n```python\n# Solución\nprint(1)\n```"
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm
        
        report = diagnose_and_suggest_fix("python script.py", "", "ZeroDivisionError: division by zero")
        
        self.assertIn("[AUTO-DIAGNÓSTICO DE ERRORES DE JARVIS]", report)
        self.assertIn("División por cero", report)
        self.assertIn("```python", report)
        
        # Verificar argumentos del LLM
        mock_llm.invoke.assert_called_once()
        called_args = mock_llm.invoke.call_args[0][0]
        self.assertEqual(called_args[0][0], "system")
        self.assertIn("Auto-diagnóstico de Errores", called_args[0][1])
        self.assertEqual(called_args[1][0], "human")
        self.assertIn("script.py", called_args[1][1])
        self.assertIn("ZeroDivisionError: division by zero", called_args[1][1])

    @patch("core.error_autofixer.is_internet_available")
    @patch("core.error_autofixer.get_llm")
    @patch("subprocess.run")
    def test_terminal_tool_attaches_diagnostics(self, mock_run, mock_get_llm, mock_is_internet):
        # Desactivar Modo Seguro para ejecutar directamente en tests
        with patch.dict(os.environ, {"JARVIS_SAFE_MODE": "False", "JARVIS_ERROR_AUTOFIX_ENABLED": "True"}):
            mock_is_internet.return_value = False
            
            # Simular ejecución fallida (exit code 1)
            mock_res = MagicMock()
            mock_res.returncode = 1
            mock_res.stdout = "Procesando..."
            mock_res.stderr = "Traceback (most recent call last):\n  File \"script.py\", line 1\nSyntaxError: invalid syntax"
            mock_run.return_value = mock_res
            
            # Simular respuesta LLM
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Error de sintaxis. Falta cerrar paréntesis."
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm
            
            output = run_terminal_command("python script.py")
            
            self.assertIn("SyntaxError: invalid syntax", output)
            self.assertIn("[AUTO-DIAGNÓSTICO DE ERRORES DE JARVIS]", output)
            self.assertIn("Error de sintaxis", output)

if __name__ == '__main__':
    unittest.main()
