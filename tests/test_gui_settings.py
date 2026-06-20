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
        
        # Guardar valor original de las variables de entorno
        self.original_model = os.environ.get("JARVIS_WHISPER_MODEL")
        self.original_sentinel = os.environ.get("JARVIS_SENTINEL_ENABLED")

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
                
        # Restaurar variables de entorno originales
        if self.original_model is not None:
            os.environ["JARVIS_WHISPER_MODEL"] = self.original_model
        elif "JARVIS_WHISPER_MODEL" in os.environ:
            del os.environ["JARVIS_WHISPER_MODEL"]

        if self.original_sentinel is not None:
            os.environ["JARVIS_SENTINEL_ENABLED"] = self.original_sentinel
        elif "JARVIS_SENTINEL_ENABLED" in os.environ:
            del os.environ["JARVIS_SENTINEL_ENABLED"]

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

    def test_get_services_config(self):
        client = socketio.test_client(app)
        client.get_received()
        
        client.emit("get_services_config")
        received = client.get_received()
        
        response_event = None
        for event in received:
            if event["name"] == "services_config_response":
                response_event = event["args"][0]
                break
                
        self.assertIsNotNone(response_event)
        self.assertIn("network_sentinel", response_event)
        self.assertIn("api_sentinel", response_event)
        self.assertIn("vulnerability_patcher", response_event)

    @patch("core.network_sentinel.start_network_sentinel")
    @patch("core.network_sentinel.stop_network_sentinel")
    def test_toggle_service(self, mock_stop, mock_start):
        # Configurar env inicial
        os.environ["JARVIS_SENTINEL_ENABLED"] = "false"
        if self.env_path.exists():
            self.env_path.write_text("JARVIS_SENTINEL_ENABLED=false\n", encoding="utf-8")
            
        client = socketio.test_client(app)
        client.get_received()
        
        # Activar el servicio
        client.emit("toggle_service", {"service": "network_sentinel", "enable": True})
        received = client.get_received()
        
        response_event = None
        for event in received:
            if event["name"] == "services_config_response":
                response_event = event["args"][0]
                break
                
        self.assertIsNotNone(response_event)
        # Verificar que se llamó a la función de inicio
        mock_start.assert_called_once()
        # Verificar que se actualizó el env
        self.assertEqual(os.environ.get("JARVIS_SENTINEL_ENABLED"), "true")
        
        # Verificar que se escribió en .env
        env_content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("JARVIS_SENTINEL_ENABLED=true", env_content)
        
        # Desactivar el servicio
        client.emit("toggle_service", {"service": "network_sentinel", "enable": False})
        mock_stop.assert_called_once()
        self.assertEqual(os.environ.get("JARVIS_SENTINEL_ENABLED"), "false")

if __name__ == "__main__":
    unittest.main()
