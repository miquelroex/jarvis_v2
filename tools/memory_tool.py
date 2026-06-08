from langchain.tools import tool
from core.memory import save_memory, search_memories, delete_memory_by_content

@tool("save_memory")
def save_memory_tool(content: str, category: str = "general") -> str:
    """
    Guarda un hecho, dato, preferencia o recuerdo sobre el usuario en la base de datos persistente.
    Úsalo cuando el usuario te pida explícita o implícitamente recordar algo (ej. "Acuérdate de que mañana tengo médico", "Mi color favorito es el azul").
    """
    try:
        saved = save_memory(content, category=category, source="agent_tool")
        if saved:
            return f"He recordado correctamente: '{content}' en la categoría '{category}', señor."
        else:
            return f"Señor, ese recuerdo ya estaba registrado en mi memoria."
    except Exception as e:
        return f"Error al guardar el recuerdo: {str(e)}"

@tool("search_memories")
def search_memories_tool(query: str) -> str:
    """
    Busca recuerdos guardados en la memoria persistente que contengan la palabra o frase de consulta.
    Úsalo cuando el usuario te pregunte por cosas que deberías recordar y no estén presentes directamente en tu prompt de sistema.
    """
    try:
        results = search_memories(query)
        if results:
            formatted = "\n".join(f"- {m['content']} (Categoría: {m['category']})" for m in results)
            return f"He encontrado los siguientes recuerdos relacionados con '{query}', señor:\n{formatted}"
        else:
            return f"No encontré ningún recuerdo relacionado con '{query}', señor."
    except Exception as e:
        return f"Error al buscar recuerdos: {str(e)}"

@tool("delete_memory")
def delete_memory_tool(query: str) -> str:
    """
    Elimina recuerdos de la memoria persistente que coincidan parcial o totalmente con el texto de consulta.
    Úsalo cuando el usuario te pida olvidar, borrar o limpiar algún dato de la memoria.
    """
    try:
        deleted = delete_memory_by_content(query)
        if deleted:
            return f"He olvidado con éxito todo lo relacionado con '{query}', señor."
        else:
            return f"No he encontrado ningún recuerdo relacionado con '{query}' para borrar, señor."
    except Exception as e:
        return f"Error al eliminar recuerdos: {str(e)}"
