from langchain.tools import tool

@tool
def toggle_socratic_mode(active: bool) -> str:
    """
    Toggles the Socratic/Rubber-Ducking debugging mode for Jarvis.
    If active is True, Jarvis switches to Socratic Mode, asking questions and giving hints rather than direct solutions.
    If active is False, Jarvis goes back to conventional direct assistance.
    """
    from core.prompts import set_socratic_mode
    set_socratic_mode(active)
    
    # Recargar el agente para actualizar el prompt
    from core.agent_manager import reload_agent
    reload_agent()
    
    # Sincronizar con la interfaz web
    try:
        from gui.app import update_state
        update_state(status="idle", socratic_mode=active)
    except Exception:
        pass
        
    status = "ACTIVADO" if active else "DESACTIVADO"
    return f"El Modo Socrático de Depuración (Rubber Ducking) ha sido {status}."
