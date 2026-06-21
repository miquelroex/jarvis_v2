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

    def test_current_model_command(self):
        fake_am = types.SimpleNamespace(get_active_model=lambda: "deepseek/deepseek-v4-pro")
        with patch.dict(sys.modules, {"core.agent_manager": fake_am}):
            resp = handle_fast_command("que modelo estas usando")
        self.assertIsNotNone(resp)
        self.assertIn("deepseek/deepseek-v4-pro", resp)

    def test_change_model_command_success(self):
        applied = {}

        def fake_set(model_id):
            applied["id"] = model_id
            return model_id

        fake_mc = types.SimpleNamespace(
            resolve_model_alias=lambda a: "qwen/qwen3-coder" if a == "codigo" else None,
            available_aliases=lambda: ["codigo", "gemini"],
        )
        fake_am = types.SimpleNamespace(set_active_model=fake_set)
        with patch.dict(sys.modules, {"core.model_config": fake_mc, "core.agent_manager": fake_am}):
            resp = handle_fast_command("cambia al modelo codigo")
        self.assertEqual(applied["id"], "qwen/qwen3-coder")
        self.assertIn("qwen/qwen3-coder", resp)

    def test_change_model_command_unknown(self):
        fake_mc = types.SimpleNamespace(
            resolve_model_alias=lambda a: None,
            available_aliases=lambda: ["codigo", "gemini"],
        )
        with patch.dict(sys.modules, {"core.model_config": fake_mc}):
            resp = handle_fast_command("cambia al modelo inventado")
        self.assertIn("no reconozco", resp.lower())

    def test_inbox_add_command(self):
        added = []
        fake_inbox = types.SimpleNamespace(
            add_inbox_item=lambda c: (added.append(c) or True),
            get_inbox_items=lambda include_done=False: [],
            clear_inbox=lambda only_done=False: 0,
        )
        with patch.dict(sys.modules, {"core.inbox": fake_inbox}):
            resp = handle_fast_command("apunta en la bandeja comprar leche")
        self.assertEqual(added, ["comprar leche"])
        self.assertIn("comprar leche", resp)

    def test_inbox_add_preserves_original_case(self):
        added = []
        fake_inbox = types.SimpleNamespace(
            add_inbox_item=lambda c: (added.append(c) or True),
            get_inbox_items=lambda include_done=False: [],
            clear_inbox=lambda only_done=False: 0,
        )
        with patch.dict(sys.modules, {"core.inbox": fake_inbox}):
            handle_fast_command("Apunta en la bandeja Llamar a Mamá")
        self.assertEqual(added, ["Llamar a Mamá"])

    def test_inbox_list_command(self):
        fake_inbox = types.SimpleNamespace(
            add_inbox_item=lambda c: True,
            get_inbox_items=lambda include_done=False: [
                {"id": 1, "content": "comprar pan", "created_at": "", "done": False},
                {"id": 2, "content": "llamar al banco", "created_at": "", "done": False},
            ],
            clear_inbox=lambda only_done=False: 0,
        )
        with patch.dict(sys.modules, {"core.inbox": fake_inbox}):
            resp = handle_fast_command("que hay en mi bandeja")
        self.assertIn("2 nota", resp)
        self.assertIn("comprar pan", resp)
        self.assertIn("llamar al banco", resp)

    def test_inbox_list_empty(self):
        fake_inbox = types.SimpleNamespace(
            add_inbox_item=lambda c: True,
            get_inbox_items=lambda include_done=False: [],
            clear_inbox=lambda only_done=False: 0,
        )
        with patch.dict(sys.modules, {"core.inbox": fake_inbox}):
            resp = handle_fast_command("lista la bandeja")
        self.assertIn("vacía", resp.lower())

    def test_inbox_clear_command(self):
        fake_inbox = types.SimpleNamespace(
            add_inbox_item=lambda c: True,
            get_inbox_items=lambda include_done=False: [],
            clear_inbox=lambda only_done=False: 3,
        )
        with patch.dict(sys.modules, {"core.inbox": fake_inbox}):
            resp = handle_fast_command("vacia la bandeja")
        self.assertIn("3 nota", resp)

    def test_game_mode_on_command(self):
        fake_gm = types.SimpleNamespace(
            enter_game_mode=lambda: {"already_active": False, "paused": ["test_watcher", "task_scheduler"]},
            exit_game_mode=lambda: {"was_active": False, "resumed": []},
        )
        with patch.dict(sys.modules, {"core.game_mode": fake_gm}):
            resp = handle_fast_command("activa modo gaming")
        self.assertIn("activado", resp.lower())
        self.assertIn("2 servicios", resp)

    def test_game_mode_off_command(self):
        fake_gm = types.SimpleNamespace(
            enter_game_mode=lambda: {"already_active": False, "paused": []},
            exit_game_mode=lambda: {"was_active": True, "resumed": ["test_watcher"]},
        )
        # "desactiva modo gaming" debe ir a exit, no a enter, pese a contener "modo gaming".
        with patch.dict(sys.modules, {"core.game_mode": fake_gm}):
            resp = handle_fast_command("desactiva modo gaming")
        self.assertIn("desactivado", resp.lower())

    def test_game_mode_normal_alias_deactivates(self):
        fake_gm = types.SimpleNamespace(
            enter_game_mode=lambda: {"already_active": False, "paused": []},
            exit_game_mode=lambda: {"was_active": True, "resumed": []},
        )
        with patch.dict(sys.modules, {"core.game_mode": fake_gm}):
            resp = handle_fast_command("modo normal")
        self.assertIn("desactivado", resp.lower())

    def test_set_active_model_rebuilds_agent(self):
        # set_active_model recrea el LLM y reconstruye el agente. Import perezoso
        # para que la colección del archivo no arrastre langchain.
        import core.agent_manager as am
        prev_llm = am.llm
        try:
            with patch.object(am, "get_llm", return_value="FAKE_LLM"), \
                 patch.object(am, "reload_agent") as mock_reload, \
                 patch.dict(os.environ, {}, clear=False):
                result = am.set_active_model("test/model-x")
                self.assertEqual(result, "test/model-x")
                self.assertEqual(am.llm, "FAKE_LLM")
                mock_reload.assert_called_once()
                self.assertEqual(os.environ.get("JARVIS_MODEL_DEFAULT"), "test/model-x")
        finally:
            am.llm = prev_llm

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
