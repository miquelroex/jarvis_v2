"""Tests del Modo Gaming (core/game_mode.py).

Se prueba de forma aislada parcheando importlib.import_module e inyectando un
core.services falso, sin arrancar/parar servicios reales.
"""
import os
import sys
import types
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.game_mode as gm


class TestGameMode(unittest.TestCase):

    def setUp(self):
        gm._game_mode_active = False
        gm._paused_services = []

    def tearDown(self):
        gm._game_mode_active = False
        gm._paused_services = []

    def _fake_services(self, status):
        return types.SimpleNamespace(get_services_status=lambda: status)

    def test_enter_pauses_only_running(self):
        status = {
            "test_watcher": "running",
            "network_sentinel": "disabled",
            "task_scheduler": "running",
            "ram_guard": "running",  # no forma parte del modo gaming
        }
        with patch.dict(sys.modules, {"core.services": self._fake_services(status)}), \
             patch("core.game_mode.importlib.import_module", return_value=MagicMock()):
            result = gm.enter_game_mode()

        self.assertFalse(result["already_active"])
        self.assertEqual(set(result["paused"]), {"test_watcher", "task_scheduler"})
        self.assertTrue(gm.is_game_mode_active())
        self.assertEqual(set(gm.get_paused_services()), {"test_watcher", "task_scheduler"})

    def test_enter_calls_stop_function(self):
        status = {"test_watcher": "running"}
        mock_mod = MagicMock()
        with patch.dict(sys.modules, {"core.services": self._fake_services(status)}), \
             patch("core.game_mode.importlib.import_module", return_value=mock_mod):
            gm.enter_game_mode()
        mock_mod.stop_test_watcher.assert_called_once()

    def test_enter_idempotent(self):
        status = {"test_watcher": "running"}
        with patch.dict(sys.modules, {"core.services": self._fake_services(status)}), \
             patch("core.game_mode.importlib.import_module", return_value=MagicMock()):
            first = gm.enter_game_mode()
            second = gm.enter_game_mode()
        self.assertFalse(first["already_active"])
        self.assertTrue(second["already_active"])

    def test_exit_resumes_paused(self):
        status = {"test_watcher": "running", "api_sentinel": "running"}
        mock_mod = MagicMock()
        with patch.dict(sys.modules, {"core.services": self._fake_services(status)}), \
             patch("core.game_mode.importlib.import_module", return_value=mock_mod):
            gm.enter_game_mode()
            result = gm.exit_game_mode()

        self.assertTrue(result["was_active"])
        self.assertEqual(set(result["resumed"]), {"test_watcher", "api_sentinel"})
        self.assertFalse(gm.is_game_mode_active())
        self.assertEqual(gm.get_paused_services(), [])
        # Reanuda llamando a las funciones de arranque.
        mock_mod.start_test_watcher.assert_called_once()
        mock_mod.start_api_sentinel.assert_called_once()

    def test_exit_when_inactive(self):
        result = gm.exit_game_mode()
        self.assertFalse(result["was_active"])
        self.assertEqual(result["resumed"], [])

    def test_disabled_services_not_resumed(self):
        # Un servicio desactivado al entrar no debe reanudarse al salir.
        status = {"test_watcher": "running", "api_sentinel": "disabled"}
        mock_mod = MagicMock()
        with patch.dict(sys.modules, {"core.services": self._fake_services(status)}), \
             patch("core.game_mode.importlib.import_module", return_value=mock_mod):
            gm.enter_game_mode()
            result = gm.exit_game_mode()
        self.assertEqual(result["resumed"], ["test_watcher"])
        mock_mod.start_api_sentinel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
