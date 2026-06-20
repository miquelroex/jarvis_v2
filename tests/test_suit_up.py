import unittest
import os
import sys
from unittest.mock import patch, MagicMock, call

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mockear psutil antes de que se importe en cualquier sitio
mock_psutil = MagicMock()
sys.modules['psutil'] = mock_psutil

# Importar explícitamente los módulos de core para evitar AttributeErrors durante patch
import core.services
import core.privacy_sentinel
import core.vulnerability_patcher
import core.suit_up as suit_up


class TestSuitUp(unittest.TestCase):

    def test_collect_core_init(self):
        """Prueba que la Fase 1 devuelva los campos básicos de CORE INIT."""
        data = suit_up._collect_core_init()
        self.assertEqual(data["phase"], 1)
        self.assertEqual(data["title"], "CORE INIT")
        labels = [item["label"] for item in data["items"]]
        self.assertIn("PYTHON", labels)
        self.assertIn("PID", labels)
        self.assertIn("PLATFORM", labels)

    def test_collect_memory_scan_ok(self):
        """Prueba la recopilación de datos de memoria cuando psutil está disponible."""
        mock_proc_inst = MagicMock()
        mock_proc_inst.memory_info.return_value.rss = 100 * 1024 * 1024  # 100MB
        mock_psutil.Process.return_value = mock_proc_inst

        mock_vmem_inst = MagicMock()
        mock_vmem_inst.percent = 45.0
        mock_vmem_inst.used = 8 * 1024**3
        mock_vmem_inst.total = 16 * 1024**3
        mock_psutil.virtual_memory.return_value = mock_vmem_inst

        mock_swap_inst = MagicMock()
        mock_swap_inst.percent = 10.0
        mock_psutil.swap_memory.return_value = mock_swap_inst

        mock_psutil.cpu_percent.return_value = 15.0

        data = suit_up._collect_memory_scan()
        self.assertEqual(data["phase"], 2)
        self.assertEqual(data["title"], "MEMORY SCAN")
        
        # Validar items
        labels = {item["label"]: item for item in data["items"]}
        self.assertEqual(labels["JARVIS PROCESS"]["value"], "100.0 MB")
        self.assertEqual(labels["JARVIS PROCESS"]["status"], "ok")
        self.assertIn("45.0%", labels["SYSTEM RAM"]["value"])
        self.assertEqual(labels["CPU LOAD"]["value"], "15.0%")

    def test_collect_memory_scan_error(self):
        """Prueba de robustez ante fallos en psutil durante MEMORY SCAN."""
        mock_psutil.Process.side_effect = Exception("psutil error")
        try:
            data = suit_up._collect_memory_scan()
            self.assertEqual(data["phase"], 2)
            self.assertEqual(data["items"][0]["label"], "MEMORY")
            self.assertEqual(data["items"][0]["status"], "error")
        finally:
            mock_psutil.Process.side_effect = None

    @patch("core.services.get_services_status")
    def test_collect_services_check(self, mock_get_status):
        """Prueba el escaneo de servicios."""
        mock_get_status.return_value = {
            "test_watcher": "running",
            "telegram_bot": "disabled"
        }
        data = suit_up._collect_services_check()
        self.assertEqual(data["phase"], 3)
        labels = {item["label"]: item for item in data["items"]}
        self.assertEqual(labels["TEST WATCHER"]["value"], "ONLINE")
        self.assertEqual(labels["TEST WATCHER"]["status"], "ok")
        self.assertEqual(labels["TELEGRAM BOT"]["value"], "OFFLINE")
        self.assertEqual(labels["TELEGRAM BOT"]["status"], "warning")

    @patch("socket.socket")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_collect_network_recon(self, mock_read_text, mock_exists, mock_socket):
        """Prueba el reconocimiento de red local."""
        mock_exists.return_value = True
        mock_read_text.return_value = '[{"mac": "00:11:22:33:44:55", "known": true}, {"mac": "55:44:33:22:11:00", "known": false}]'

        data = suit_up._collect_network_recon()
        self.assertEqual(data["phase"], 4)
        labels = {item["label"]: item for item in data["items"]}
        self.assertEqual(labels["KNOWN DEVICES"]["value"], "1")
        self.assertEqual(labels["UNKNOWN DEVICES"]["value"], "1")
        self.assertEqual(labels["UNKNOWN DEVICES"]["status"], "warning")

    @patch("core.vulnerability_patcher.REPORT_FILE.exists")
    @patch("core.vulnerability_patcher.REPORT_FILE.read_text")
    @patch("core.privacy_sentinel.get_privacy_status")
    def test_collect_final_status_nominal(self, mock_privacy_status, mock_read_text, mock_exists):
        """Prueba la Fase 5 con estado NOMINAL."""
        mock_exists.return_value = True
        mock_read_text.return_value = '{"vulnerabilities": []}'
        mock_privacy_status.return_value = {"exposed_count": 0}

        data = suit_up._collect_final_status()
        self.assertEqual(data["phase"], 5)
        self.assertEqual(data["level"], "NOMINAL")
        labels = {item["label"]: item for item in data["items"]}
        self.assertEqual(labels["SYSTEM STATUS"]["value"], "NOMINAL")
        self.assertEqual(labels["SYSTEM STATUS"]["status"], "ok")

    @patch("core.vulnerability_patcher.REPORT_FILE.exists")
    @patch("core.vulnerability_patcher.REPORT_FILE.read_text")
    @patch("core.privacy_sentinel.get_privacy_status")
    def test_collect_final_status_warning(self, mock_privacy_status, mock_read_text, mock_exists):
        """Prueba la Fase 5 con estado ADVISORY."""
        mock_exists.return_value = True
        mock_read_text.return_value = '{"vulnerabilities": [{"package": "pip"}]}'
        mock_privacy_status.return_value = {"exposed_count": 2}

        data = suit_up._collect_final_status()
        self.assertEqual(data["phase"], 5)
        self.assertEqual(data["level"], "ADVISORY")
        labels = {item["label"]: item for item in data["items"]}
        self.assertEqual(labels["SYSTEM STATUS"]["value"], "ADVISORY")
        self.assertEqual(labels["SYSTEM STATUS"]["status"], "warning")

    def test_run_suit_up_sequence_complete(self):
        """Prueba que run_suit_up_sequence emita todas las fases e inicio/fin."""
        mock_socketio = MagicMock()
        
        # Ejecutamos con delay_multiplier muy bajo para que no tarde en los tests
        suit_up.run_suit_up_sequence(mock_socketio, delay_multiplier=0.001)

        # Verificar llamadas
        calls = mock_socketio.emit.mock_calls
        self.assertEqual(calls[0], call("suitup_start", {"total_phases": 5}))
        
        # Debe haber 5 fases
        phases = [c[1][1]["phase"] for c in calls if c[1][0] == "suitup_phase"]
        self.assertEqual(phases, [1, 2, 3, 4, 5])
        
        # Última llamada debe ser suitup_complete
        self.assertEqual(calls[-1], call("suitup_complete", {"status": "ready"}))

    def test_run_suit_up_sequence_cancel(self):
        """Prueba que cancel_suit_up aborte la secuencia en curso de forma inmediata."""
        mock_socketio = MagicMock()
        
        # Simulamos que cancelamos a mitad de la secuencia llamando a cancel_suit_up
        # en la segunda emisión del socket
        def side_effect(event, data=None):
            if event == "suitup_phase" and data and data.get("phase") == 2:
                suit_up.cancel_suit_up()

        mock_socketio.emit.side_effect = side_effect

        suit_up.run_suit_up_sequence(mock_socketio, delay_multiplier=0.01)

        # Verificar que se detuvo antes de la fase 5
        calls = mock_socketio.emit.mock_calls
        phases = [c[1][1]["phase"] for c in calls if c[1][0] == "suitup_phase"]
        self.assertNotIn(5, phases)
        
        # Debe haberse emitido el evento suitup_cancelled
        cancelled_events = [c for c in calls if c[1][0] == "suitup_cancelled"]
        self.assertTrue(len(cancelled_events) > 0)


if __name__ == "__main__":
    unittest.main()
