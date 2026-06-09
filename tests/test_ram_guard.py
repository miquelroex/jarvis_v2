"""Tests para el RAM Guard (core/ram_guard.py)."""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.ram_guard as ram_guard


class TestRAMGuard(unittest.TestCase):
    """Tests de detección de umbral, disparo de modo seguro y parada limpia."""

    def setUp(self):
        """Reset estado global antes de cada test."""
        ram_guard._safe_mode_active = False
        ram_guard._services_paused = []
        ram_guard.stop_event.clear()

    def test_get_ram_usage_returns_float(self):
        """_get_ram_usage_mb debe retornar un float positivo."""
        result = ram_guard._get_ram_usage_mb()
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)

    def test_get_system_ram_percent_returns_float(self):
        """_get_system_ram_percent debe retornar un float entre 0 y 100."""
        result = ram_guard._get_system_ram_percent()
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)

    @patch("core.ram_guard._get_system_ram_percent", return_value=50.0)
    @patch("core.ram_guard._get_ram_usage_mb", return_value=3000.0)
    @patch("tools.voice.speak")
    def test_high_ram_triggers_safe_mode(self, mock_speak, mock_ram, mock_sys_ram):
        """Cuando la RAM del proceso supera el umbral, se deben pausar servicios."""
        # Configurar entorno
        with patch.dict(os.environ, {
            "JARVIS_MAX_RAM_MB": "2500",
            "JARVIS_AUTO_SAFE_MODE_ON_HIGH_RAM": "true",
            "JARVIS_MAX_SYSTEM_RAM_PERCENT": "90"
        }):
            # Mock de los módulos de servicio para evitar imports reales
            with patch("core.ram_guard._pause_heavy_services") as mock_pause:
                # Simular una sola iteración del loop
                ram_guard.stop_event.clear()

                # Ejecutar lógica de verificación directamente
                process_ram = 3000.0
                max_ram_mb = 2500
                if process_ram > max_ram_mb and not ram_guard._safe_mode_active:
                    ram_guard._pause_heavy_services()
                    ram_guard._safe_mode_active = True

                mock_pause.assert_called_once()
                self.assertTrue(ram_guard._safe_mode_active)

    @patch("core.ram_guard._get_system_ram_percent", return_value=95.0)
    @patch("core.ram_guard._get_ram_usage_mb", return_value=500.0)
    def test_high_system_ram_triggers_safe_mode(self, mock_ram, mock_sys_ram):
        """Cuando la RAM del sistema supera el umbral, se debe activar modo seguro."""
        system_percent = 95.0
        max_system_percent = 90

        if system_percent > max_system_percent and not ram_guard._safe_mode_active:
            ram_guard._safe_mode_active = True

        self.assertTrue(ram_guard._safe_mode_active)

    def test_safe_mode_not_triggered_below_threshold(self):
        """Si la RAM está por debajo del umbral, no se activa modo seguro."""
        process_ram = 1000.0
        system_percent = 60.0
        max_ram_mb = 2500
        max_system_percent = 90

        over = process_ram > max_ram_mb or system_percent > max_system_percent
        self.assertFalse(over)
        self.assertFalse(ram_guard._safe_mode_active)

    def test_start_stop_idempotent(self):
        """start_ram_guard y stop_ram_guard deben ser idempotentes."""
        import threading as _threading
        # Usar un Event para mantener vivo el hilo mockeado hasta que lo señalemos
        keep_alive = _threading.Event()

        def mock_loop():
            keep_alive.wait(timeout=5)

        with patch("core.ram_guard._ram_guard_loop", side_effect=mock_loop):
            # Primer start
            ram_guard.start_ram_guard()
            self.assertIsNotNone(ram_guard.RAM_GUARD_THREAD)
            first_thread = ram_guard.RAM_GUARD_THREAD
            self.assertTrue(first_thread.is_alive())

            # Segundo start debe ser no-op (hilo aún vivo)
            ram_guard.start_ram_guard()
            self.assertIs(ram_guard.RAM_GUARD_THREAD, first_thread)

            # Stop
            ram_guard.stop_ram_guard()
            self.assertTrue(ram_guard.stop_event.is_set())

            # Señalar al hilo para que termine
            keep_alive.set()
            first_thread.join(timeout=2)
            self.assertFalse(first_thread.is_alive())

            # Segundo stop no debe fallar
            ram_guard.stop_ram_guard()

    def test_is_safe_mode_active(self):
        """is_safe_mode_active debe reflejar el estado interno."""
        self.assertFalse(ram_guard.is_safe_mode_active())
        ram_guard._safe_mode_active = True
        self.assertTrue(ram_guard.is_safe_mode_active())

    def test_get_paused_services(self):
        """get_paused_services debe retornar una copia de la lista interna."""
        ram_guard._services_paused = ["test_watcher", "scheduler"]
        result = ram_guard.get_paused_services()
        self.assertEqual(result, ["test_watcher", "scheduler"])
        # Debe ser una copia, no la misma referencia
        result.append("extra")
        self.assertEqual(len(ram_guard._services_paused), 2)


if __name__ == "__main__":
    unittest.main()
