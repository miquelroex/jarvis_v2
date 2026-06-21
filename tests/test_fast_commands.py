import sys
import os
import types
import unittest
import tempfile
from unittest.mock import patch

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.fast_commands import handle_fast_command
from core.memory import set_db_path, init_db

class TestFastCommands(unittest.TestCase):
    def setUp(self):
        # Configurar base de datos temporal para los comandos rápidos en los tests
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.test_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        set_db_path(self.test_db_path)
        init_db(self.test_db_path)

    def tearDown(self):
        # Limpiar base de datos temporal
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    def test_time_command(self):
        resp = handle_fast_command("que hora es")
        self.assertIsNotNone(resp)
        self.assertTrue(resp.startswith("Son las"))
        
        resp_alt = handle_fast_command("dime la hora")
        self.assertIsNotNone(resp_alt)
        self.assertTrue(resp_alt.startswith("Son las"))

    def test_date_command(self):
        resp = handle_fast_command("que dia es")
        self.assertIsNotNone(resp)
        self.assertTrue(resp.startswith("Hoy es"))
        
        resp_alt = handle_fast_command("fecha de hoy")
        self.assertIsNotNone(resp_alt)
        self.assertTrue(resp_alt.startswith("Hoy es"))

    @patch("webbrowser.open")
    def test_website_command(self, mock_open):
        resp = handle_fast_command("abre youtube")
        self.assertEqual(resp, "Abriendo youtube, señor.")
        mock_open.assert_called_once_with("https://www.youtube.com")

        resp_gmail = handle_fast_command("abrir gmail")
        self.assertEqual(resp_gmail, "Abriendo gmail, señor.")
        mock_open.assert_any_call("https://mail.google.com")

    @patch("os.system")
    def test_apps_command(self, mock_system):
        resp = handle_fast_command("abre calculadora")
        self.assertEqual(resp, "Abriendo calculadora, señor.")
        mock_system.assert_called_once_with("start calc")

    def test_no_match(self):
        resp = handle_fast_command("cual es el sentido de la vida")
        self.assertIsNone(resp)

    def _services_status_with(self, status_dict, phrase="estado de los servicios"):
        # Inyectamos un core.services falso para no importar el real (que arrastra
        # gui.app -> tools.voice y, en local, el crash de OpenSSL).
        fake_services = types.SimpleNamespace(get_services_status=lambda: status_dict)
        with patch.dict(sys.modules, {"core.services": fake_services}):
            return handle_fast_command(phrase)

    def test_services_status_command(self):
        status = {
            "web_gui": "running",
            "telegram_bot": "disabled",
            "ram_guard": "running",
            "network_sentinel": "stopped",
        }
        resp = self._services_status_with(status)
        self.assertIsNotNone(resp)
        # Conteo: 2 activos, 1 detenido, 1 desactivado.
        self.assertIn("2 activos", resp)
        self.assertIn("1 detenidos", resp)
        self.assertIn("1 desactivados", resp)
        # Lista los activos y detenidos con nombres legibles (sin guiones bajos).
        self.assertIn("web gui", resp)
        self.assertIn("ram guard", resp)
        self.assertIn("network sentinel", resp)

    def test_services_status_command_alias(self):
        # Otra de las frases disparadoras debe funcionar igual.
        resp = self._services_status_with({"web_gui": "running"}, phrase="informe de servicios")
        self.assertIsNotNone(resp)
        self.assertIn("1 activos", resp)

    def test_daily_digest_command(self):
        # Inyectamos un core.daily_digest falso para no arrastrar imports pesados.
        fake_digest = types.SimpleNamespace(
            generate_daily_digest=lambda: "Resumen del día, señor (test)."
        )
        with patch.dict(sys.modules, {"core.daily_digest": fake_digest}):
            resp = handle_fast_command("dame el resumen del dia")
            resp_alias = handle_fast_command("que he hecho hoy")
        self.assertEqual(resp, "Resumen del día, señor (test).")
        self.assertEqual(resp_alias, "Resumen del día, señor (test).")

    def test_memory_save_command(self):
        resp = handle_fast_command("recuerda que me gusta la lasaña")
        self.assertIsNotNone(resp)
        self.assertIn("He guardado en mi memoria: me gusta la lasaña", resp)

        # Duplicado
        resp_dup = handle_fast_command("recuerda que me gusta la lasaña")
        self.assertIn("ya estaba registrado en mi memoria", resp_dup)

    def test_memory_query_and_delete_commands(self):
        # Guardar algunos registros
        handle_fast_command("recuerda que mi perro es Toby")
        handle_fast_command("recuerda que mi coche es rojo")

        # Consulta específica
        resp_query = handle_fast_command("que recuerdas de mi perro")
        self.assertIn("mi perro es Toby", resp_query)

        # Consulta general
        resp_all = handle_fast_command("dime mis recuerdos")
        self.assertIn("mi perro es Toby", resp_all)
        self.assertIn("mi coche es rojo", resp_all)

        # Olvidar
        resp_del = handle_fast_command("olvida mi coche")
        self.assertIn("He olvidado lo relacionado con: mi coche", resp_del)

        # Consulta después de olvidar
        resp_query_post = handle_fast_command("que recuerdas de mi coche")
        self.assertIn("No tengo recuerdos relacionados con 'mi coche'", resp_query_post)

if __name__ == "__main__":
    unittest.main()
