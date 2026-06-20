import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gui.app import app, socketio

class TestGuiSettings(unittest.TestCase):
    def setUp(self):
        # Hacer copia de seguridad de .env real
        self.env_path = Path(".env")
        self.env_backup = None
        if self.env_path.exists():
            try:
                self.env_backup = self.env_path.read_text(encoding="utf-8")
            except Exception:
                pass
        
        # Guardar valor original de la variable de entorno
        self.original_model = os.environ.get("JARVIS_WHISPER_MODEL")

    def tearDown(self):
        # Restaurar .env real
        if self.env_backup is not None:
            try:
                self.env_path.write_text(self.env_backup, encoding="utf-8")
            except Exception:
                pass
        elif self.env_path.exists():
            try:
                self.env_path.unlink()
            except Exception:
                pass
                
        # Restaurar variable de entorno original
        if self.original_model is not None:
            os.environ["JARVIS_WHISPER_MODEL"] = self.original_model
        elif "JARVIS_WHISPER_MODEL" in os.environ:
            del os.environ["JARVIS_WHISPER_MODEL"]

    def test_get_whisper_config(self):
        client = socketio.test_client(app)
        client.get_received()  # Limpiar eventos de conexión
        
        client.emit("get_whisper_config")
        received = client.get_received()
        
        response_event = None
        for event in received:
            if event["name"] == "whisper_config_response":
                response_event = event["args"][0]
                break
                
        self.assertIsNotNone(response_event)
        self.assertIn("configured_model", response_event)
        self.assertIn("loaded", response_event)
        self.assertIn("model_name", response_event)
        self.assertIn("device", response_event)

    def test_set_whisper_model(self):
        # Forzar un modelo inicial
        os.environ["JARVIS_WHISPER_MODEL"] = "tiny"
        if self.env_path.exists():
            # Crear un env dummy
            self.env_path.write_text("JARVIS_WHISPER_MODEL=tiny\n", encoding="utf-8")
            
        client = socketio.test_client(app)
        client.get_received()
        
        # Cambiar a medium
        client.emit("set_whisper_model", {"model": "medium"})
        received = client.get_received()
        
        response_event = None
        for event in received:
            if event["name"] == "whisper_config_response":
                response_event = event["args"][0]
                break
                
        self.assertIsNotNone(response_event)
        self.assertEqual(response_event.get("configured_model"), "medium")
        self.assertEqual(os.environ.get("JARVIS_WHISPER_MODEL"), "medium")
        
        # Verificar que se escribió en .env
        env_content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("JARVIS_WHISPER_MODEL=medium", env_content)

if __name__ == "__main__":
    unittest.main()
