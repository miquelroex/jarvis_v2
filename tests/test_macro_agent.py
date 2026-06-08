import sys
import os
import unittest
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.macro_agent import (
    log_terminal_command,
    analyze_repetitive_commands,
    HISTORY_FILE,
    LOGS_DIR
)
from tools.macro_tool import create_macro_shortcut, MACROS_DIR
from gui.app import app, socketio

class TestMacroAgent(unittest.TestCase):
    def setUp(self):
        # Hacer copia de seguridad de la historia real
        self.history_backup = None
        if HISTORY_FILE.exists():
            try:
                self.history_backup = HISTORY_FILE.read_text(encoding="utf-8")
                HISTORY_FILE.unlink()
            except Exception:
                pass
        else:
            LOGS_DIR.mkdir(exist_ok=True)

        self.created_macros = []

    def tearDown(self):
        # Limpiar macros creados en el test
        for macro_name in self.created_macros:
            macro_file = MACROS_DIR / f"{macro_name}.bat"
            if macro_file.exists():
                try:
                    macro_file.unlink()
                except Exception:
                    pass
        
        # Eliminar carpeta de macros si está vacía
        if MACROS_DIR.exists() and not any(MACROS_DIR.iterdir()):
            try:
                MACROS_DIR.rmdir()
            except Exception:
                pass

        # Restaurar la historia real
        if HISTORY_FILE.exists():
            try:
                HISTORY_FILE.unlink()
            except Exception:
                pass
        if self.history_backup is not None:
            try:
                HISTORY_FILE.write_text(self.history_backup, encoding="utf-8")
            except Exception:
                pass

    def test_log_terminal_command(self):
        # 1. Registrar unos cuantos comandos
        log_terminal_command("git status")
        log_terminal_command("git add .")
        
        self.assertTrue(HISTORY_FILE.exists())
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["command"], "git status")
        self.assertEqual(history[1]["command"], "git add .")

        # 2. Registrar más de 100 comandos para validar el límite (cap a 100)
        for i in range(120):
            log_terminal_command(f"cmd_{i}")
            
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        self.assertEqual(len(history), 100)
        self.assertEqual(history[0]["command"], "cmd_20")
        self.assertEqual(history[-1]["command"], "cmd_119")

    def test_heuristics_repetition(self):
        # Generar un historial con repeticiones consecutivas e idénticas
        # e.g., 'pytest' repetido 3 veces consecutivas
        log_terminal_command("pytest")
        log_terminal_command("pytest")
        log_terminal_command("pytest")
        
        # Secuencias de longitud 2 repetidas: 'git add .' -> 'git commit -m "update"'
        # Ejecutada dos veces (no consecutivas de forma que no sean idénticas consecutivas)
        log_terminal_command("git status")
        log_terminal_command("git add .")
        log_terminal_command("git commit -m \"update\"")
        log_terminal_command("git status")
        log_terminal_command("git add .")
        log_terminal_command("git commit -m \"update\"")

        analysis = analyze_repetitive_commands()
        
        # Debe haber detectado 'pytest' en repeats consecutivos
        self.assertIn("pytest", analysis["consecutive_repeats"])
        self.assertEqual(analysis["consecutive_repeats"]["pytest"], 3)
        
        # Debe haber detectado la secuencia de 2
        seqs_of_2 = [s["sequence"] for s in analysis["sequences"] if len(s["sequence"]) == 2]
        self.assertTrue(any(seq == ["git add .", "git commit -m \"update\""] for seq in seqs_of_2))

        # Debe haber detectado la secuencia de 3: 'git status' -> 'git add .' -> 'git commit -m "update"'
        seqs_of_3 = [s["sequence"] for s in analysis["sequences"] if len(s["sequence"]) == 3]
        self.assertTrue(any(seq == ["git status", "git add .", "git commit -m \"update\""] for seq in seqs_of_3))

    def test_create_macro_shortcut_tool(self):
        macro_name = "test_macro_run"
        self.created_macros.append(macro_name)
        
        commands = ["echo Hello", "echo World"]
        res = create_macro_shortcut.invoke({"name": macro_name, "commands": commands})
        
        self.assertIn("creado con éxito", res)
        
        # Verificar archivo físicamente
        macro_file = MACROS_DIR / f"{macro_name}.bat"
        self.assertTrue(macro_file.exists())
        
        content = macro_file.read_text(encoding="utf-8")
        self.assertIn("@echo off", content)
        self.assertIn("echo Hello", content)
        self.assertIn("echo World", content)

    def test_gui_run_batch_command(self):
        # Test de ejecución desde la GUI con el socket Flask-SocketIO
        client = socketio.test_client(app)
        
        # Limpiar eventos anteriores
        client.get_received()
        
        # Enviar petición de ejecución de script batch
        code = "@echo off\necho Macro Run Successful\n"
        client.emit("run_code_request", {
            "language": "bat",
            "code": code
        })
        
        received = client.get_received()
        
        # Validar que recibimos respuesta
        response_event = None
        for event in received:
            if event["name"] == "run_code_response":
                response_event = event["args"][0]
                break
                
        self.assertIsNotNone(response_event)
        self.assertIn("Macro Run Successful", response_event.get("stdout", ""))
        self.assertEqual(response_event.get("stderr", "").strip(), "")

if __name__ == "__main__":
    unittest.main()
