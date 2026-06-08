import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
from pathlib import Path

# Asegurar import de network_sentinel
from core.network_sentinel import (
    get_host_mac,
    load_known_devices,
    save_known_devices,
    trust_device,
    get_subnet_prefix,
    parse_arp_output,
    scan_network
)

class TestNetworkSentinel(unittest.TestCase):

    def test_get_host_mac_format(self):
        mac = get_host_mac()
        self.assertEqual(len(mac), 17)
        self.assertEqual(mac.count(":"), 5)

    @patch('subprocess.run')
    def test_parse_arp_output_windows(self, mock_run):
        # Simular salida típica de arp -a en Windows
        arp_output = (
            "\n"
            "Interfaz: 192.168.1.15 --- 0x14\n"
            "  Dirección de Internet          Dirección física      Tipo\n"
            "  192.168.1.1           e0-60-66-11-22-33     dinámico  \n"
            "  192.168.1.25          f4-a4-b5-44-55-66     dinámico  \n"
            "  192.168.1.255         ff-ff-ff-ff-ff-ff     estático  \n"
            "  224.0.0.22            01-00-5e-00-00-16     estático  \n"
        )
        mock_run.return_value.stdout = arp_output
        mock_run.return_value.returncode = 0

        devices = parse_arp_output()
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["ip"], "192.168.1.1")
        self.assertEqual(devices[0]["mac"], "e0:60:66:11:22:33")
        self.assertEqual(devices[1]["ip"], "192.168.1.25")
        self.assertEqual(devices[1]["mac"], "f4:a4:b5:44:55:66")

    @patch('subprocess.run')
    def test_parse_arp_output_unix(self, mock_run):
        # Simular salida típica de arp -a/an en Linux/Mac
        arp_output = (
            "? (192.168.1.1) at e0:60:66:11:22:33 [ether] on wlan0\n"
            "? (192.168.1.50) at a1:b2:c3:d4:e5:f6 [ether] on wlan0\n"
        )
        mock_run.return_value.stdout = arp_output
        mock_run.return_value.returncode = 0

        devices = parse_arp_output()
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["ip"], "192.168.1.1")
        self.assertEqual(devices[0]["mac"], "e0:60:66:11:22:33")
        self.assertEqual(devices[1]["ip"], "192.168.1.50")
        self.assertEqual(devices[1]["mac"], "a1:b2:c3:d4:e5:f6")

    @patch('core.network_sentinel.KNOWN_DEVICES_FILE')
    def test_load_known_devices_creation(self, mock_file_path):
        # Simular que el archivo no existe
        mock_file_path.exists.return_value = False
        
        data = load_known_devices()
        # Debería auto-agregar la MAC local
        local_mac = get_host_mac()
        self.assertIn(local_mac, data["known_macs"])
        self.assertEqual(data["device_names"][local_mac], "Servidor Jarvis (Este Equipo)")
        mock_file_path.write_text.assert_called_once()

    @patch('core.network_sentinel.KNOWN_DEVICES_FILE')
    def test_load_save_known_devices(self, mock_file_path):
        mock_file_path.exists.return_value = True
        dummy_data = {
            "known_macs": ["aa:bb:cc:dd:ee:ff"],
            "device_names": {"aa:bb:cc:dd:ee:ff": "Test Device"}
        }
        
        # Test loading
        mock_file_path.read_text.return_value = json.dumps(dummy_data)
        data = load_known_devices()
        self.assertEqual(data["known_macs"], ["aa:bb:cc:dd:ee:ff"])
        self.assertEqual(data["device_names"]["aa:bb:cc:dd:ee:ff"], "Test Device")
        mock_file_path.read_text.assert_called_once()
            
        # Test saving
        save_known_devices(dummy_data)
        mock_file_path.write_text.assert_called_once()
        written_arg = mock_file_path.write_text.call_args[0][0]
        self.assertIn("aa:bb:cc:dd:ee:ff", written_arg)

    @patch('core.network_sentinel.load_known_devices')
    @patch('core.network_sentinel.save_known_devices')
    @patch('core.network_sentinel.run_quick_scan')
    def test_trust_device(self, mock_quick_scan, mock_save, mock_load):
        mock_load.return_value = {
            "known_macs": ["00:11:22:33:44:55"],
            "device_names": {"00:11:22:33:44:55": "Local Host"}
        }

        trust_device("AA-BB-CC-DD-EE-FF", "Nuevo Movil")
        
        # Debe llamar a guardar con la nueva MAC en minúscula y colones
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        self.assertIn("aa:bb:cc:dd:ee:ff", saved_data["known_macs"])
        self.assertEqual(saved_data["device_names"]["aa:bb:cc:dd:ee:ff"], "Nuevo Movil")
        mock_quick_scan.assert_called_once()

    @patch('core.network_sentinel.get_subnet_prefix')
    @patch('core.network_sentinel.run_ping_sweep')
    @patch('core.network_sentinel.parse_arp_output')
    @patch('core.network_sentinel.load_known_devices')
    @patch('core.network_sentinel.notify_new_strange_devices')
    def test_scan_network_alerting(self, mock_notify, mock_load_known, mock_arp, mock_sweep, mock_prefix):
        # 1. Configurarmocks de red
        mock_prefix.return_value = ("192.168.1.15", "192.168.1.")
        
        # Dispositivos de arp: 192.168.1.1 (router, conocido), 192.168.1.50 (extraño)
        mock_arp.return_value = [
            {"ip": "192.168.1.1", "mac": "e0:60:66:11:22:33"},
            {"ip": "192.168.1.50", "mac": "aa:bb:cc:dd:ee:ff"},
            {"ip": "192.168.1.15", "mac": "00:00:00:00:00:00"}, # IP local de la interfaz, debe ignorarse
            {"ip": "192.168.2.1", "mac": "11:22:33:44:55:66"}  # Subred errónea, debe ignorarse
        ]
        
        # Lista de MACs de confianza (solo router)
        mock_load_known.return_value = {
            "known_macs": ["e0:60:66:11:22:33"],
            "device_names": {"e0:60:66:11:22:33": "Router"}
        }

        # Asegurar limpiar alertas por voz previas
        import core.network_sentinel
        core.network_sentinel.voiced_alerts.clear()

        # 2. Ejecutar escaneo
        results = scan_network()

        # 3. Comprobar que sólo escaneo 2 dispositivos de la subred excluyendo la IP local
        self.assertEqual(len(results), 2)
        
        # Router
        self.assertTrue(results[0]["known"])
        self.assertEqual(results[0]["name"], "Router")
        
        # Desconocido
        self.assertFalse(results[1]["known"])
        self.assertEqual(results[1]["name"], "Dispositivo Desconocido")
        
        # 4. Validar que se lanzó la notificación para el dispositivo extraño
        mock_notify.assert_called_once_with([{"ip": "192.168.1.50", "mac": "aa:bb:cc:dd:ee:ff"}])

    @patch('core.network_sentinel.get_subnet_prefix')
    @patch('core.network_sentinel.run_ping_sweep')
    @patch('core.network_sentinel.parse_arp_output')
    @patch('core.network_sentinel.load_known_devices')
    @patch('core.network_sentinel.notify_new_strange_devices')
    def test_scan_network_public_ip_aborts(self, mock_notify, mock_load_known, mock_arp, mock_sweep, mock_prefix):
        # 1. Configurar IP pública (no privada)
        mock_prefix.return_value = ("8.8.8.8", "8.8.8.")
        
        # 2. Ejecutar escaneo -> debe abortar y retornar vacío
        results = scan_network()
        self.assertEqual(len(results), 0)
        mock_sweep.assert_not_called()

    @patch('core.network_sentinel.scan_network')
    @patch('core.network_sentinel.time.sleep')
    @patch('core.network_sentinel.os.getenv')
    def test_network_sentinel_loop_interval_limit(self, mock_getenv, mock_sleep, mock_scan):
        # Configurar variables de entorno ficticias: habilitado=True, intervalo=10 (menor a 60)
        def getenv_side_effect(key, default=None):
            if key == "JARVIS_SENTINEL_INTERVAL":
                return "10"
            elif key == "JARVIS_SENTINEL_ENABLED":
                return "True"
            return default
            
        mock_getenv.side_effect = getenv_side_effect
        mock_scan.return_value = []
        
        # Simulamos que el loop corre una vez deteniendo con KeyboardInterrupt
        def sleep_side_effect(secs):
            if secs > 5:
                raise KeyboardInterrupt("Stop loop")
        mock_sleep.side_effect = sleep_side_effect
        
        from core.network_sentinel import network_sentinel_loop
        
        try:
            network_sentinel_loop()
        except KeyboardInterrupt:
            pass
            
        # El sleep debe haber sido llamado con 60 (límite mínimo), no con 10
        mock_sleep.assert_called_with(60)

    @patch('core.network_sentinel.get_subnet_prefix')
    @patch('core.network_sentinel.run_ping_sweep')
    @patch('core.network_sentinel.parse_arp_output')
    @patch('core.network_sentinel.load_known_devices')
    @patch('core.network_sentinel.notify_new_strange_devices')
    def test_scan_network_writes_json(self, mock_notify, mock_load_known, mock_arp, mock_sweep, mock_prefix):
        mock_prefix.return_value = ("192.168.1.15", "192.168.1.")
        mock_arp.return_value = [{"ip": "192.168.1.1", "mac": "e0:60:66:11:22:33"}]
        mock_load_known.return_value = {"known_macs": [], "device_names": {}}
        
        # Asegurar que no existe
        scan_json_path = Path("logs/last_network_scan.json")
        if scan_json_path.exists():
            scan_json_path.unlink()
            
        results = scan_network()
        
        # El archivo JSON debe haberse creado
        self.assertTrue(scan_json_path.exists())
        saved_data = json.loads(scan_json_path.read_text(encoding="utf-8"))
        self.assertEqual(len(saved_data), 1)
        self.assertEqual(saved_data[0]["ip"], "192.168.1.1")
        self.assertEqual(saved_data[0]["mac"], "e0:60:66:11:22:33")

if __name__ == '__main__':
    unittest.main()
