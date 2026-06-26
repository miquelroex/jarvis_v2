"""Tests del Informe de Daños (core/damage_report.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.damage_report as dr


class TestStatusWords(unittest.TestCase):
    def test_status_word(self):
        self.assertEqual(dr._status_word(10), "nominal")
        self.assertEqual(dr._status_word(80), "elevado")
        self.assertEqual(dr._status_word(95), "crítico")

    def test_status_word_bad(self):
        self.assertEqual(dr._status_word(None), "desconocido")

    def test_temp_word(self):
        self.assertEqual(dr._temp_word(50), "nominales")
        self.assertEqual(dr._temp_word(75), "elevados")
        self.assertEqual(dr._temp_word(90), "críticos")


class TestBuildReport(unittest.TestCase):
    def test_all_nominal(self):
        m = {"cpu": 12, "ram": 40, "temp": 45, "services_running": 20, "services_down": 0, "threat": "green"}
        r = dr.build_damage_report(m)
        self.assertIn("Informe de daños", r)
        self.assertIn("12%", r)
        self.assertIn("todos en línea", r)
        self.assertIn("Todos los sistemas nominales", r)

    def test_critical_ram(self):
        m = {"cpu": 30, "ram": 95, "services_running": 20, "services_down": 0, "threat": "green"}
        r = dr.build_damage_report(m)
        self.assertIn("crítico", r)
        self.assertIn("intervención inmediata", r)

    def test_services_down(self):
        m = {"cpu": 10, "ram": 30, "services_running": 18, "services_down": 2, "threat": "green"}
        r = dr.build_damage_report(m)
        self.assertIn("2 subsistemas fuera de línea de 20", r)
        self.assertIn("intervención inmediata", r)  # un servicio caído es crítico

    def test_one_service_down_singular(self):
        m = {"cpu": 10, "ram": 30, "services_running": 19, "services_down": 1, "threat": "green"}
        r = dr.build_damage_report(m)
        self.assertIn("1 subsistema fuera de línea", r)

    def test_threat_amber_is_warning(self):
        m = {"cpu": 10, "ram": 30, "services_running": 20, "services_down": 0, "threat": "amber"}
        r = dr.build_damage_report(m)
        self.assertIn("ámbar", r)
        self.assertIn("bajo carga", r)

    def test_threat_red_is_critical(self):
        m = {"cpu": 10, "ram": 30, "services_running": 20, "services_down": 0, "threat": "red"}
        r = dr.build_damage_report(m)
        self.assertIn("intervención inmediata", r)

    def test_no_temp(self):
        m = {"cpu": 10, "ram": 30, "temp": None, "services_running": 20, "services_down": 0, "threat": "green"}
        r = dr.build_damage_report(m)
        self.assertIn("Telemetría térmica no disponible", r)

    def test_hot_temp_critical(self):
        m = {"cpu": 10, "ram": 30, "temp": 88, "services_running": 20, "services_down": 0, "threat": "green"}
        r = dr.build_damage_report(m)
        self.assertIn("críticos", r)
        self.assertIn("intervención inmediata", r)


class TestGetReport(unittest.TestCase):
    def test_get_uses_gathered_metrics(self):
        fake = {"cpu": 5, "ram": 5, "temp": None, "services_running": 3, "services_down": 0, "threat": "green"}
        with patch.object(dr, "_gather_metrics", return_value=fake):
            r = dr.get_damage_report()
        self.assertIn("Todos los sistemas nominales", r)


if __name__ == "__main__":
    unittest.main()
