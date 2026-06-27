import os
import sys
import logging
import importlib
import inspect
from pathlib import Path
from langchain_core.tools import BaseTool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from core.llm_factory import get_llm
from core.prompts import get_compiled_system_prompt

# Estado global del agente
executor = None
memory = None
llm = None
prompt = None
tools = []
# Herramientas que fallaron al cargarse en la última ejecución de load_all_tools().
# Cada entrada: {"file": "tools/<nombre>.py", "error": "<mensaje>"}
failed_tools = []

def load_all_tools() -> list:
    """Escanea el directorio tools/ y carga/recarga dinámicamente las herramientas de LangChain."""
    global tools, failed_tools
    new_tools = []
    failures = []
    
    # Encontrar la carpeta de herramientas relativa a este archivo
    tools_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
    
    if not os.path.exists(tools_dir):
        logging.error(f"❌ La carpeta de herramientas no existe: {tools_dir}")
        return tools
        
    for filename in os.listdir(tools_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"tools.{filename[:-3]}"
            try:
                # Recargar el módulo si ya fue importado previamente
                if module_name in sys.modules:
                    module = importlib.reload(sys.modules[module_name])
                else:
                    module = importlib.import_module(module_name)
                
                # Escanear miembros de tipo BaseTool
                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, BaseTool) and obj not in new_tools:
                        new_tools.append(obj)
            except Exception as e:
                logging.error(f"❌ Error al cargar/recargar herramienta {filename}: {e}")
                failures.append({"file": f"tools/{filename}", "error": str(e)})

    tools = new_tools
    failed_tools = failures

    # Coraza universal: resiliencia + telemetría + circuit breaker a TODAS las
    # herramientas de un golpe (core/tool_armor). Activado por defecto.
    try:
        if os.getenv("JARVIS_TOOL_ARMOR", "true").lower() in ("true", "1", "yes"):
            from core.tool_armor import armor_all
            armor_all(tools)
    except Exception as e:
        logging.error(f"❌ Error al aplicar la coraza de herramientas: {e}")

    return tools

def get_tools_load_report() -> dict:
    """Reporte seguro del estado de carga de tools, sin reimportar ni recargar nada.

    Lee el resultado de la última ejecución de load_all_tools() ya almacenado en
    los globales del módulo. Pensado para consumidores como el healthcheck.

    Returns:
        dict: {"loaded": <int>, "failed": [{"file", "error"}, ...]}
    """
    return {
        "loaded": len(tools),
        "failed": list(failed_tools),
    }

def reload_agent() -> None:
    """Recarga las herramientas en caliente y recrea el AgentExecutor manteniendo el historial de conversación."""
    global executor, memory, llm, prompt, tools
    
    logging.info("Recargando herramientas del sistema en caliente...")
    load_all_tools()
    
    if llm is None:
        raise ValueError("El LLM debe estar inicializado.")
        
    # Recrear el template del prompt de forma dinámica según el modo activo
    from core.prompts import get_compiled_system_prompt
    compiled_prompt = get_compiled_system_prompt()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", compiled_prompt + "\n/no_think"),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    # Recrear el agente con la nueva lista de herramientas
    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
    
    # Recrear el executor conservando el objeto memory para mantener el historial
    from core.agent_callbacks import JarvisAgentCallbacks
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        callbacks=[JarvisAgentCallbacks()]
    )
    logging.info(f"¡Agente recargado con éxito! Total herramientas registradas: {len(tools)}")

def init_agent() -> None:
    """Inicializa la primera carga del agente, el LLM, los prompts y la memoria."""
    global executor, memory, llm, prompt
    
    if executor is not None:
        return
        
    logging.info("Inicializando el motor central de Jarvis...")
    llm = get_llm()
    
    # Inicializar la memoria de conversación
    memory = ConversationBufferWindowMemory(k=5, memory_key="chat_history", return_messages=True)
    
    # Crear el template del prompt inicial de forma dinámica
    from core.prompts import get_compiled_system_prompt
    compiled_prompt = get_compiled_system_prompt()
    prompt = ChatPromptTemplate.from_messages([
        ("system", compiled_prompt + "\n/no_think"),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    # Cargar herramientas y crear el executor inicial
    reload_agent()

def clear_conversation_memory() -> None:
    """Limpia el historial de conversación del agente de forma segura.
    No falla si el agente todavía no ha sido inicializado."""
    global memory
    try:
        if memory is not None:
            memory.clear()
    except Exception as e:
        logging.error(f"Error al limpiar la memoria de conversación: {e}")

def get_executor() -> AgentExecutor:
    """Retorna la instancia activa del AgentExecutor de Jarvis."""
    global executor
    if executor is None:
        init_agent()
    return executor

def get_active_model() -> str:
    """Devuelve el ID del modelo actualmente activo para el agente principal."""
    return os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v4-pro")

def set_active_model(model_id: str) -> str:
    """Cambia en caliente el modelo del agente principal.

    Recrea el LLM con el nuevo modelo y reconstruye el executor (conservando la
    memoria de conversación). El cambio es solo para la sesión actual (actualiza
    JARVIS_MODEL_DEFAULT en el entorno del proceso). Si algo falla, restaura el
    LLM anterior y relanza la excepción para no dejar el agente en mal estado.

    Returns:
        str: el model_id aplicado.
    """
    global llm
    if not model_id:
        raise ValueError("model_id vacío")

    prev_llm = llm
    try:
        llm = get_llm(model_id)
        reload_agent()
        os.environ["JARVIS_MODEL_DEFAULT"] = model_id
        logging.info(f"Modelo activo cambiado a: {model_id}")
        return model_id
    except Exception as e:
        llm = prev_llm
        logging.error(f"No se pudo cambiar el modelo activo a {model_id}: {e}")
        raise
