import unittest
import os
import sys
from unittest.mock import patch, MagicMock, call

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import core.services as services


class TestServices(unittest.TestCase):

    @patch("core.ram_guard.start_ram_guard")
    @patch("gui.app.run_gui_in_background")
    @patch("core.telegram_bot.start_telegram_bot")
    @patch("core.network_sentinel.start_network_sentinel")
    @patch("core.api_sentinel.start_api_sentinel")
    @patch("core.vulnerability_patcher.start_vulnerability_patcher_daemon")
    @patch("core.jarvis_integrity.start_integrity_sentinel_daemon")
    @patch("core.test_watcher.start_test_watcher")
    @patch("core.scheduler.start_scheduler")
    def test_start_all_services_order(self, mock_sched, mock_watcher, mock_integ, mock_patch, mock_api, mock_net, mock_tg, mock_gui, mock_ram):
        """Valida que todos los servicios arranquen en el orden correcto."""
        manager = MagicMock()
        manager.attach_mock(mock_gui, "gui")
        manager.attach_mock(mock_tg, "telegram_bot")
        manager.attach_mock(mock_net, "network_sentinel")
        manager.attach_mock(mock_api, "api_sentinel")
        manager.attach_mock(mock_patch, "vulnerability_patcher")
        manager.attach_mock(mock_integ, "integrity_sentinel")
        manager.attach_mock(mock_watcher, "test_watcher")
        manager.attach_mock(mock_sched, "scheduler")
        manager.attach_mock(mock_ram, "ram_guard")

        with patch.dict(os.environ, {
            "JARVIS_TELEGRAM_ENABLED": "true",
            "JARVIS_SCHEDULER": "true",
        }):
            services.start_all_services()

        expected_calls = [
            call.gui(),
            call.telegram_bot(),
            call.network_sentinel(),
            call.api_sentinel(),
            call.vulnerability_patcher(),
            call.integrity_sentinel(),
            call.test_watcher(),
            call.scheduler(),
            call.ram_guard()
        ]
        self.assertEqual(manager.mock_calls, expected_calls)

    @patch("core.ram_guard.stop_ram_guard")
    @patch("core.scheduler.stop_scheduler")
    @patch("core.test_watcher.stop_test_watcher")
    @patch("core.jarvis_integrity.stop_integrity_sentinel_daemon")
    @patch("core.vulnerability_patcher.stop_vulnerability_patcher_daemon")
    @patch("core.api_sentinel.stop_api_sentinel")
    @patch("core.network_sentinel.stop_network_sentinel")
    @patch("core.telegram_bot.stop_telegram_bot")
    @patch("gui.app.stop_gui_monitor")
    @patch("core.privacy_sentinel.stop_privacy_monitor")
    def test_stop_all_services_order_and_robustness(self, mock_privacy, mock_gui_mon, mock_tg, mock_net, mock_api, mock_patch, mock_integ, mock_watcher, mock_sched, mock_ram):
        """Valida que los servicios se detengan en orden inverso y toleren fallos individuales."""
        manager = MagicMock()
        manager.attach_mock(mock_ram, "ram_guard")
        manager.attach_mock(mock_sched, "scheduler")
        manager.attach_mock(mock_watcher, "test_watcher")
        manager.attach_mock(mock_integ, "integrity_sentinel")
        manager.attach_mock(mock_patch, "vulnerability_patcher")
        manager.attach_mock(mock_api, "api_sentinel")
        manager.attach_mock(mock_net, "network_sentinel")
        manager.attach_mock(mock_tg, "telegram_bot")
        manager.attach_mock(mock_gui_mon, "gui_monitor")
        manager.attach_mock(mock_privacy, "privacy_monitor")

        # Hacer que uno falle para verificar robustez
        mock_patch.side_effect = Exception("Fallo simulado al detener patcher")

        services.stop_all_services()

        expected_calls = [
            call.ram_guard(),
            call.scheduler(),
            call.test_watcher(),
            call.integrity_sentinel(),
            call.vulnerability_patcher(),
            call.api_sentinel(),
            call.network_sentinel(),
            call.telegram_bot(),
            call.gui_monitor(),
            call.privacy_monitor()
        ]
        self.assertEqual(manager.mock_calls, expected_calls)

        # Confirmar que a pesar del fallo, todos intentaron detenerse
        mock_ram.assert_called_once()
        mock_sched.assert_called_once()
        mock_watcher.assert_called_once()
        mock_integ.assert_called_once()
        mock_patch.assert_called_once()
        mock_api.assert_called_once()
        mock_net.assert_called_once()
        mock_tg.assert_called_once()
        mock_gui_mon.assert_called_once()
        mock_privacy.assert_called_once()

    @patch("core.ram_guard.RAM_GUARD_THREAD")
    @patch("gui.app._gui_thread")
    @patch("core.telegram_bot.bot_thread")
    @patch("core.network_sentinel.sentinel_thread")
    @patch("core.api_sentinel.SENTINEL_THREAD")
    @patch("core.vulnerability_patcher.PATCHER_THREAD")
    @patch("core.jarvis_integrity.INTEGRITY_THREAD")
    @patch("core.test_watcher._watcher_thread")
    @patch("core.scheduler.is_scheduler_running")
    @patch("core.privacy_sentinel.MONITOR_THREAD")
    def test_get_services_status(self, mock_privacy_th, mock_sched_run, mock_watcher_th, mock_integ_th, mock_patch_th, mock_api_th, mock_net_th, mock_tg_th, mock_gui_th, mock_ram_th):
        """Valida get_services_status bajo distintas configuraciones."""
        
        # Caso 1: Todos arrancados y habilitados
        mock_gui_th.is_alive.return_value = True
        mock_tg_th.is_alive.return_value = True
        mock_net_th.is_alive.return_value = True
        mock_api_th.is_alive.return_value = True
        mock_patch_th.is_alive.return_value = True
        mock_integ_th.is_alive.return_value = True
        mock_watcher_th.is_alive.return_value = True
        mock_privacy_th.is_alive.return_value = True
        mock_sched_run.return_value = True
        mock_ram_th.is_alive.return_value = True

        env_dict = {
            "JARVIS_GUI_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "8870594184:valid_token",
            "JARVIS_TELEGRAM_ENABLED": "true",
            "JARVIS_SENTINEL_ENABLED": "True",
            "JARVIS_API_SENTINEL_ENABLED": "True",
            "JARVIS_VULNERABILITY_PATCHER_ENABLED": "True",
            "JARVIS_INTEGRITY_SENTINEL_ENABLED": "True",
            "JARVIS_TEST_WATCHER": "True",
            "JARVIS_SCHEDULER": "true",
            "JARVIS_PRIVACY_SCAN_INTERVAL": "900"
        }

        with patch.dict(os.environ, env_dict):
            status = services.get_services_status()
            
            self.assertEqual(status["web_gui"], "running")
            self.assertEqual(status["telegram_bot"], "running")
            self.assertEqual(status["network_sentinel"], "running")
            self.assertEqual(status["api_sentinel"], "running")
            self.assertEqual(status["vulnerability_patcher"], "running")
            self.assertEqual(status["integrity_sentinel"], "running")
            self.assertEqual(status["test_watcher"], "running")
            self.assertEqual(status["task_scheduler"], "running")
            self.assertEqual(status["ram_guard"], "running")
            self.assertEqual(status["privacy_monitor"], "running")

        # Caso 2: Todos deshabilitados
        mock_gui_th.is_alive.return_value = False
        mock_tg_th.is_alive.return_value = False
        mock_net_th.is_alive.return_value = False
        mock_api_th.is_alive.return_value = False
        mock_patch_th.is_alive.return_value = False
        mock_integ_th.is_alive.return_value = False
        mock_watcher_th.is_alive.return_value = False
        mock_privacy_th.is_alive.return_value = False
        mock_sched_run.return_value = False
        mock_ram_th.is_alive.return_value = False

        env_dict_disabled = {
            "JARVIS_GUI_ENABLED": "false",
            "TELEGRAM_BOT_TOKEN": "",
            "JARVIS_TELEGRAM_ENABLED": "false",
            "JARVIS_SENTINEL_ENABLED": "False",
            "JARVIS_API_SENTINEL_ENABLED": "False",
            "JARVIS_VULNERABILITY_PATCHER_ENABLED": "False",
            "JARVIS_INTEGRITY_SENTINEL_ENABLED": "False",
            "JARVIS_TEST_WATCHER": "false",
            "JARVIS_SCHEDULER": "false",
            "JARVIS_PRIVACY_SCAN_INTERVAL": "0"
        }

        with patch.dict(os.environ, env_dict_disabled):
            status = services.get_services_status()
            
            self.assertEqual(status["web_gui"], "disabled")
            self.assertEqual(status["telegram_bot"], "disabled")
            self.assertEqual(status["network_sentinel"], "disabled")
            self.assertEqual(status["api_sentinel"], "disabled")
            self.assertEqual(status["vulnerability_patcher"], "disabled")
            self.assertEqual(status["integrity_sentinel"], "disabled")
            self.assertEqual(status["test_watcher"], "disabled")
            self.assertEqual(status["task_scheduler"], "disabled")
            self.assertEqual(status["ram_guard"], "stopped")
            self.assertEqual(status["privacy_monitor"], "disabled")

    @patch("core.ram_guard.start_ram_guard")
    @patch("gui.app.run_gui_in_background")
    @patch("core.telegram_bot.start_telegram_bot")
    @patch("core.network_sentinel.start_network_sentinel")
    @patch("core.api_sentinel.start_api_sentinel")
    @patch("core.vulnerability_patcher.start_vulnerability_patcher_daemon")
    @patch("core.jarvis_integrity.start_integrity_sentinel_daemon")
    @patch("core.test_watcher.start_test_watcher")
    @patch("core.scheduler.start_scheduler")
    def test_disabled_services_not_started(self, mock_sched, mock_watcher, mock_integ, mock_patch, mock_api, mock_net, mock_tg, mock_gui, mock_ram):
        """Servicios desactivados por .env no deben arrancarse."""
        with patch.dict(os.environ, {
            "JARVIS_TELEGRAM_ENABLED": "false",
            "JARVIS_SCHEDULER": "false",
        }):
            services.start_all_services()

        mock_tg.assert_not_called()
        mock_sched.assert_not_called()
        # GUI y otros servicios que se controlan internamente sí se llaman
        mock_gui.assert_called_once()
        mock_ram.assert_called_once()


if __name__ == "__main__":
    unittest.main()
