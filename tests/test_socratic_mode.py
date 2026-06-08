import os
import unittest
from unittest.mock import patch, MagicMock
from core.prompts import (
    set_socratic_mode,
    is_socratic_mode_active,
    get_compiled_system_prompt,
    SOCRATIC_FILE
)
from tools.socratic_tool import toggle_socratic_mode

class TestSocraticMode(unittest.TestCase):
    def setUp(self):
        # Asegurar un estado limpio antes de cada test
        if SOCRATIC_FILE.exists():
            try:
                SOCRATIC_FILE.unlink()
            except Exception:
                pass

    def tearDown(self):
        # Limpiar después de cada test
        if SOCRATIC_FILE.exists():
            try:
                SOCRATIC_FILE.unlink()
            except Exception:
                pass

    def test_socratic_mode_activation_and_deactivation(self):
        # 1. Por defecto está desactivado
        self.assertFalse(is_socratic_mode_active())
        self.assertNotIn("MODO SOCRÁTICO ACTIVADO", get_compiled_system_prompt())
        
        # 2. Activar modo socrático
        set_socratic_mode(True)
        self.assertTrue(is_socratic_mode_active())
        self.assertIn("MODO SOCRÁTICO ACTIVADO", get_compiled_system_prompt())
        
        # 3. Desactivar de nuevo
        set_socratic_mode(False)
        self.assertFalse(is_socratic_mode_active())
        self.assertNotIn("MODO SOCRÁTICO ACTIVADO", get_compiled_system_prompt())

    @patch('core.agent_manager.reload_agent')
    @patch('gui.app.update_state')
    def test_toggle_socratic_mode_tool(self, mock_update_state, mock_reload):
        # Activar mediante la herramienta
        res = toggle_socratic_mode.invoke({"active": True})
        self.assertIn("ha sido ACTIVADO", res)
        self.assertTrue(is_socratic_mode_active())
        
        # Verificar llamadas
        mock_reload.assert_called_once()
        mock_update_state.assert_called_once_with(status="idle", socratic_mode=True)
        
        # Desactivar mediante la herramienta
        mock_reload.reset_mock()
        mock_update_state.reset_mock()
        
        res_off = toggle_socratic_mode.invoke({"active": False})
        self.assertIn("ha sido DESACTIVADO", res_off)
        self.assertFalse(is_socratic_mode_active())
        mock_reload.assert_called_once()
        mock_update_state.assert_called_once_with(status="idle", socratic_mode=False)

    @patch('core.agent_manager.get_llm')
    @patch('core.agent_manager.reload_agent')
    def test_agent_manager_compiles_socratic_prompt(self, mock_reload, mock_get_llm):
        import core.agent_manager
        
        # Resetear variables globales del manager para forzar inicialización
        core.agent_manager.executor = None
        core.agent_manager.llm = None
        core.agent_manager.prompt = None
        
        mock_get_llm.return_value = MagicMock()
        
        # Simular modo socrático activo
        set_socratic_mode(True)
        
        core.agent_manager.init_agent()
        
        # El prompt del sistema compilado debe tener las reglas del modo socrático
        compiled_messages = core.agent_manager.prompt.messages
        system_content = compiled_messages[0].prompt.template
        self.assertIn("MODO SOCRÁTICO ACTIVADO", system_content)

if __name__ == '__main__':
    unittest.main()
