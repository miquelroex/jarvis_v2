from langchain.tools import tool

@tool
def plan_and_execute_task(task_description: str) -> str:
    """
    Plan and execute a complex multi-step task asynchronously.
    Use this tool when the user's request is complex, has multiple sequential steps
    (e.g., search info, extract data, write script, run commands, create macros, etc.),
    or when they explicitly ask to 'plan', 'execute autonomously', or 'resolve in steps'.
    This tool returns immediately, launching the task execution in the background.
    """
    from core.autonomous_agent import start_autonomous_execution
    
    # Lanzar de forma asíncrona en segundo plano
    start_autonomous_execution(task_description)
    
    return (
        "He iniciado la planificación y ejecución autónoma de la tarea en segundo plano. "
        "He trazado los pasos requeridos y los iré actualizando en tiempo real en la GUI web y en Telegram. "
        "Señor, puede continuar dándome órdenes o monitorear el progreso."
    )
