"""Tests para la herramienta de diagnóstico system_health (tools/system_health.py)."""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.system_health import system_health_report, _get_dir_size_mb


class TestSystemHealth(unittest.TestCase):
    """Tests de generación de reporte, formato y métricas."""

    def test_report_returns_string(self):
        """El reporte debe ser un string no vacío."""
        result = system_health_report.invoke({})
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_report_contains_process_ram(self):
        """El reporte debe incluir info de RAM del proceso."""
        result = system_health_report.invoke({})
        self.assertIn("RAM de Jarvis", result)
        self.assertIn("RSS", result)

    def test_report_contains_system_ram(self):
        """El reporte debe incluir RAM del sistema."""
        result = system_health_report.invoke({})
        self.assertIn("RAM del Sistema", result)
        self.assertIn("Total", result)
        self.assertIn("Disponible", result)

    def test_report_contains_threads(self):
        """El reporte debe listar hilos activos."""
        result = system_health_report.invoke({})
        self.assertIn("Hilos activos", result)

    def test_report_contains_services(self):
        """El reporte debe mostrar estado de servicios."""
        result = system_health_report.invoke({})
        self.assertIn("Servicios", result)

    def test_report_contains_python_processes(self):
        """El reporte debe listar procesos Python."""
        result = system_health_report.invoke({})
        self.assertIn("Procesos Python", result)

    def test_report_contains_sizes(self):
        """El reporte debe incluir tamaños de logs y db."""
        result = system_health_report.invoke({})
        self.assertIn("logs/", result)
        self.assertIn("jarvis.db", result)

    def test_get_dir_size_nonexistent(self):
        """_get_dir_size_mb de un directorio inexistente debe retornar 0."""
        result = _get_dir_size_mb("/path/that/does/not/exist")
        self.assertEqual(result, 0.0)

    def test_report_does_not_read_large_files(self):
        """El reporte no debe leer contenidos de archivos, solo tamaños (via stat)."""
        # Si el reporte ejecuta sin error y en menos de 5 segundos, pasa
        import time
        start = time.time()
        result = system_health_report.invoke({})
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, "El reporte tardó demasiado, posible lectura de archivos grandes")

    def test_report_contains_ram_guard_status(self):
        """El reporte debe incluir estado del RAM Guard."""
        result = system_health_report.invoke({})
        self.assertIn("RAM Guard", result)


if __name__ == "__main__":
    unittest.main()
