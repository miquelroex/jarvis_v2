from langchain_core.callbacks import BaseCallbackHandler
import logging

class JarvisAgentCallbacks(BaseCallbackHandler):
    def on_agent_action(self, action, **kwargs):
        """Se ejecuta cuando el agente decide usar una herramienta."""
        tool_name = action.tool
        tool_input = action.tool_input
        thought = getattr(action, 'log', '')
        
        logging.info(f"[Callbacks] Agente usando tool: {tool_name} con input: {tool_input}")
        try:
            from gui.app import socketio
            socketio.emit("agent_thought", {
                "type": "tool_start",
                "tool": tool_name,
                "tool_input": str(tool_input),
                "thought": thought
            })
        except Exception as e:
            logging.error(f"[Callbacks] Error al emitir agent_thought start: {e}")

    def on_tool_end(self, output, **kwargs):
        """Se ejecuta cuando finaliza la ejecución de una herramienta."""
        logging.info(f"[Callbacks] Tool finalizada con salida: {str(output)[:200]}...")
        try:
            from gui.app import socketio
            socketio.emit("agent_thought", {
                "type": "tool_end",
                "output": str(output)
            })
        except Exception as e:
            logging.error(f"[Callbacks] Error al emitir agent_thought end: {e}")

    def on_agent_finish(self, finish, **kwargs):
        """Se ejecuta cuando el agente finaliza su ciclo de razonamiento."""
        logging.info("[Callbacks] Agente finalizado.")
        try:
            from gui.app import socketio
            socketio.emit("agent_thought", {
                "type": "agent_finish",
                "output": str(finish.return_values.get("output", ""))
            })
        except Exception as e:
            logging.error(f"[Callbacks] Error al emitir agent_thought finish: {e}")
