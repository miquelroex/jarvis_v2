import sys
import os
import unittest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.autonomous_agent import generate_plan, start_autonomous_execution, ACTIVE_PLAN_FILE
from core.agent_callbacks import JarvisAgentCallbacks

class TestAutonomousAgent(unittest.TestCase):
    def setUp(self):
        # Limpieza de archivo previo si existe
        if ACTIVE_PLAN_FILE.exists():
            try:
                ACTIVE_PLAN_FILE.unlink()
            except Exception:
                pass

    def tearDown(self):
        # Limpieza final
        if ACTIVE_PLAN_FILE.exists():
            try:
                ACTIVE_PLAN_FILE.unlink()
            except Exception:
                pass

    @patch("core.autonomous_agent.get_llm")
    def test_generate_plan_success(self, mock_get_llm):
        # Mock de la respuesta del LLM
        mock_response = MagicMock()
        mock_response.content = """
        {
          "goal": "Test Task",
          "steps": [
            {"id": 1, "description": "Step A"},
            {"id": 2, "description": "Step B"}
          ]
        }
        """
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm_instance

        plan = generate_plan("Test Task")
        self.assertEqual(plan["goal"], "Test Task")
        self.assertEqual(len(plan["steps"]), 2)
        self.assertEqual(plan["steps"][0]["id"], 1)
        self.assertEqual(plan["steps"][0]["description"], "Step A")
        self.assertEqual(plan["steps"][0]["status"], "pending")

    @patch("core.autonomous_agent.get_llm")
    def test_generate_plan_failure_fallback(self, mock_get_llm):
        # Simulamos que el LLM devuelve un texto no JSON (error de parseo)
        mock_response = MagicMock()
        mock_response.content = "Texto corrupto no parseable"
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm_instance

        plan = generate_plan("Test Task")
        self.assertEqual(plan["goal"], "Test Task")
        self.assertEqual(len(plan["steps"]), 1)
        self.assertTrue("Ejecutar y resolver directamente" in plan["steps"][0]["description"])

    @patch("core.autonomous_agent.speak")
    @patch("core.autonomous_agent.socketio.emit")
    @patch("core.autonomous_agent.generate_plan")
    @patch("core.autonomous_agent.threading.Thread")
    def test_start_autonomous_execution(self, mock_thread, mock_generate_plan, mock_emit, mock_speak):
        mock_generate_plan.return_value = {
            "goal": "Test Task",
            "steps": [
                {"id": 1, "description": "Step A", "status": "pending", "output": ""}
            ]
        }

        start_autonomous_execution("Test Task")

        # Comprobar que se persistió el plan en el disco
        self.assertTrue(ACTIVE_PLAN_FILE.exists())
        saved_data = json.loads(ACTIVE_PLAN_FILE.read_text(encoding="utf-8"))
        self.assertEqual(saved_data["goal"], "Test Task")

        # Comprobar llamadas a voz y socket
        mock_speak.assert_called_once()
        mock_emit.assert_called_once_with('plan_update', saved_data)
        # Comprobar inicio del hilo secundario
        mock_thread.assert_called_once()

    @patch("gui.app.socketio.emit")
    def test_callbacks_emit_thought_events(self, mock_emit):
        callbacks = JarvisAgentCallbacks()
        
        # 1. Simular inicio de herramienta
        mock_action = MagicMock()
        mock_action.tool = "test_tool"
        mock_action.tool_input = {"arg": 1}
        mock_action.log = "Thought text"
        
        callbacks.on_agent_action(mock_action)
        mock_emit.assert_any_call("agent_thought", {
            "type": "tool_start",
            "tool": "test_tool",
            "tool_input": "{'arg': 1}",
            "thought": "Thought text"
        })

        # 2. Simular fin de herramienta
        callbacks.on_tool_end("Tool success output")
        mock_emit.assert_any_call("agent_thought", {
            "type": "tool_end",
            "output": "Tool success output"
        })

        # 3. Simular fin del agente
        mock_finish = MagicMock()
        mock_finish.return_values = {"output": "Agent final response"}
        
        callbacks.on_agent_finish(mock_finish)
        mock_emit.assert_any_call("agent_thought", {
            "type": "agent_finish",
            "output": "Agent final response"
        })

if __name__ == "__main__":
    unittest.main()
