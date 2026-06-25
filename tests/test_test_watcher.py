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
    @patch("core.reactions.react")
    def test_run_test_state_changes_and_voice_alerts(self, mock_react, mock_run):
        # 1. Primer ejecución: Pasa (estado inicial desconocido, no debería reaccionar)
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""
        mock_process.stdout = "OK"
        mock_run.return_value = mock_process

        res = run_test("tests.test_dummy")
        self.assertTrue(res)
        mock_react.assert_not_called()
        self.assertEqual(_test_states.get("tests.test_dummy"), "pass")

        # 2. Segunda ejecución: Pasa -> Pasa (no debería reaccionar)
        mock_react.reset_mock()
        res = run_test("tests.test_dummy")
        self.assertTrue(res)
        mock_react.assert_not_called()
        self.assertEqual(_test_states.get("tests.test_dummy"), "pass")

        # 3. Tercera ejecución: Pasa -> Falla (reacción "test_broken")
        mock_react.reset_mock()
        mock_process.returncode = 1
        res = run_test("tests.test_dummy")
        self.assertFalse(res)
        mock_react.assert_called_once()
        self.assertEqual(mock_react.call_args[0][0], "test_broken")
        self.assertEqual(_test_states.get("tests.test_dummy"), "fail")

        # 4. Cuarta ejecución: Falla -> Falla (no debería reaccionar de nuevo)
        mock_react.reset_mock()
        res = run_test("tests.test_dummy")
        self.assertFalse(res)
        mock_react.assert_not_called()
        self.assertEqual(_test_states.get("tests.test_dummy"), "fail")

        # 5. Quinta ejecución: Falla -> Pasa (reacción "test_recovered" con la racha)
        mock_react.reset_mock()
        mock_process.returncode = 0
        res = run_test("tests.test_dummy")
        self.assertTrue(res)
        mock_react.assert_called_once()
        self.assertEqual(mock_react.call_args[0][0], "test_recovered")
        # El contexto debe traer la racha de fallos previa (2 fallos en pasos 3 y 4).
        self.assertEqual(mock_react.call_args[0][1].get("fails"), 2)
        self.assertEqual(_test_states.get("tests.test_dummy"), "pass")

if __name__ == "__main__":
    unittest.main()
