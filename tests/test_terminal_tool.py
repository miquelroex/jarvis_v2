import sys
import os
import unittest
import json
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.terminal import run_terminal_command, PENDING_COMMAND_FILE
from tools.model_delegate import confirm_pending_model, cancel_pending_model

class TestTerminalTool(unittest.TestCase):
    def setUp(self):
        # Limpiar solicitudes pendientes
        if PENDING_COMMAND_FILE.exists():
            try:
                PENDING_COMMAND_FILE.unlink()
            except Exception:
                pass
        self.original_safe_mode = os.environ.get("JARVIS_SAFE_MODE")

    def tearDown(self):
        # Limpiar después de la prueba
        if PENDING_COMMAND_FILE.exists():
            try:
                PENDING_COMMAND_FILE.unlink()
            except Exception:
                pass
        if self.original_safe_mode is not None:
            os.environ["JARVIS_SAFE_MODE"] = self.original_safe_mode
        elif "JARVIS_SAFE_MODE" in os.environ:
            del os.environ["JARVIS_SAFE_MODE"]

    def test_blacklist_rejection(self):
        # Intentar ejecutar un comando prohibido
        res = run_terminal_command.invoke("del /f /q main.py")
        self.assertIn("bloqueado por seguridad", res)
        self.assertFalse(PENDING_COMMAND_FILE.exists())

        # Otra variante con palabra de lista negra completa
        res2 = run_terminal_command.invoke("sc query type= driver")
        self.assertIn("bloqueado por seguridad", res2)

    def test_safe_mode_pending_and_confirm(self):
        os.environ["JARVIS_SAFE_MODE"] = "True"
        
        # 1. Ejecutar comando
        cmd = "python -c \"print('Hello Test')\""
        res = run_terminal_command.invoke(cmd)
        
        # Debe pedir confirmación
        self.assertIn("requiere confirmación de seguridad", res)
        self.assertTrue(PENDING_COMMAND_FILE.exists())
        
        # Comprobar contenido
        data = json.loads(PENDING_COMMAND_FILE.read_text(encoding="utf-8"))
        self.assertEqual(data["command"], cmd)
        
        # 2. Confirmar comando
        confirm_res = confirm_pending_model.invoke("adelante")
        self.assertIn("Hello Test", confirm_res)
        self.assertFalse(PENDING_COMMAND_FILE.exists())

    def test_safe_mode_cancel(self):
        os.environ["JARVIS_SAFE_MODE"] = "True"
        
        cmd = "python -c \"print('Hello Cancel')\""
        res = run_terminal_command.invoke(cmd)
        self.assertTrue(PENDING_COMMAND_FILE.exists())
        
        # Cancelar
        cancel_res = cancel_pending_model.invoke("cancela")
        self.assertIn("Cancelado", cancel_res)
        self.assertIn("comando de terminal", cancel_res)
        self.assertFalse(PENDING_COMMAND_FILE.exists())

    def test_autonomous_mode(self):
        os.environ["JARVIS_SAFE_MODE"] = "False"
        
        cmd = "python -c \"print('Hello Auto')\""
        res = run_terminal_command.invoke(cmd)
        
        # Debe ejecutarse directamente y devolver la salida
        self.assertIn("Hello Auto", res)
        self.assertFalse(PENDING_COMMAND_FILE.exists())

if __name__ == "__main__":
    unittest.main()
