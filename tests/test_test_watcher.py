import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.test_watcher import (
    determine_test_module,
    run_test,
    _test_states
)

class TestTestWatcher(unittest.TestCase):
    def setUp(self):
        # Limpiar el registro de estados de tests antes de cada prueba
        _test_states.clear()

    @patch("os.path.exists")
    def test_determine_test_module(self, mock_exists):
        workspace = "C:/mock_workspace"
        
        # Caso 1: Archivo de test directo
        res = determine_test_module("C:/mock_workspace/tests/test_memory.py", workspace)
        self.assertEqual(res, "tests.test_memory")
        
        # Caso 2: Archivo de código en core/ que tiene test correspondiente
        mock_exists.side_effect = lambda path: "test_memory.py" in path
        res2 = determine_test_module("C:/mock_workspace/core/memory.py", workspace)
        self.assertEqual(res2, "tests.test_memory")
        
        # Caso 3: Archivo de código que no tiene test correspondiente
        mock_exists.side_effect = lambda path: False
        res3 = determine_test_module("C:/mock_workspace/core/unknown.py", workspace)
        self.assertIsNone(res3)

    @patch("subprocess.run")
    @patch("core.test_watcher.speak")
    def test_run_test_state_changes_and_voice_alerts(self, mock_speak, mock_run):
        # 1. Primer ejecución: Pasa (estado inicial desconocido, no debería hablar)
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""
        mock_process.stdout = "OK"
        mock_run.return_value = mock_process
        
        res = run_test("tests.test_dummy")
        self.assertTrue(res)
        mock_speak.assert_not_called()
        self.assertEqual(_test_states.get("tests.test_dummy"), "pass")

        # 2. Segunda ejecución: Pasa -> Pasa (no debería hablar)
        mock_speak.reset_mock()
        res = run_test("tests.test_dummy")
        self.assertTrue(res)
        mock_speak.assert_not_called()
        self.assertEqual(_test_states.get("tests.test_dummy"), "pass")

        # 3. Tercera ejecución: Pasa -> Falla (debería alertar por voz)
        mock_speak.reset_mock()
        mock_process.returncode = 1
        res = run_test("tests.test_dummy")
        self.assertFalse(res)
        mock_speak.assert_called_once()
        self.assertIn("fallando", mock_speak.call_args[0][0])
        self.assertEqual(_test_states.get("tests.test_dummy"), "fail")

        # 4. Cuarta ejecución: Falla -> Falla (no debería hablar de nuevo)
        mock_speak.reset_mock()
        res = run_test("tests.test_dummy")
        self.assertFalse(res)
        mock_speak.assert_not_called()
        self.assertEqual(_test_states.get("tests.test_dummy"), "fail")

        # 5. Quinta ejecución: Falla -> Pasa (debería notificar recuperación por voz)
        mock_speak.reset_mock()
        mock_process.returncode = 0
        res = run_test("tests.test_dummy")
        self.assertTrue(res)
        mock_speak.assert_called_once()
        self.assertIn("vuelven a pasar", mock_speak.call_args[0][0])
        self.assertEqual(_test_states.get("tests.test_dummy"), "pass")

if __name__ == "__main__":
    unittest.main()
