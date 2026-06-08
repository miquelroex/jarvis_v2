import os
import logging
from pathlib import Path
from core.api_sentinel import is_internet_available
from core.llm_factory import get_llm

def extract_error_summary(stderr: str) -> str:
    """Extrae una descripción corta del error a partir del stderr o la salida."""
    if not stderr:
        return ""
    
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    if not lines:
        return ""
        
    # Si parece un traceback de Python, el error real suele estar al final
    last_line = lines[-1]
    
    # Si la última línea es corta y contiene ":", suele ser el tipo de excepción + mensaje
    if ":" in last_line:
        return last_line
        
    # Buscar hacia atrás alguna línea que contenga "Error" o "Exception"
    for line in reversed(lines):
        if "error" in line.lower() or "exception" in line.lower():
            return line
            
    return last_line[:200]

def search_error_solutions(error_msg: str) -> str:
    """Busca en internet soluciones para el mensaje de error."""
    if not is_internet_available():
        return "Conectividad a internet no disponible. No se pudo realizar la búsqueda."
        
    query = f"how to fix {error_msg}"
    logging.info(f"[Error Auto-Fixer] Buscando en internet: {query}")
    
    # Intentar usar Tavily primero
    try:
        from tools.tavily_search import tavily_search
        res = tavily_search.invoke({"query": query})
        if "No TAVILY_API_KEY found" not in res:
            return res
    except Exception as e:
        logging.error(f"[Error Auto-Fixer] Error al buscar con Tavily: {e}")
        
    # Fallback a DuckDuckGo
    try:
        from tools.duckduckgo import duckduckgo_search_tool
        return duckduckgo_search_tool.invoke({"query": query})
    except Exception as e:
        logging.error(f"[Error Auto-Fixer] Error al buscar con DuckDuckGo: {e}")
        return f"No se pudo completar la búsqueda en internet. Error: {e}"

def diagnose_and_suggest_fix(command: str, stdout: str, stderr: str) -> str:
    """
    Analiza el fallo de un comando, investiga en la red y propone una sugerencia de código.
    """
    # Verificar si está habilitado
    enabled = os.getenv("JARVIS_ERROR_AUTOFIX_ENABLED", "True").lower() in ("true", "1", "yes")
    if not enabled:
        return ""
        
    if not stderr and not stdout:
        return ""
        
    error_summary = extract_error_summary(stderr or stdout)
    if not error_summary:
        return ""
        
    logging.info(f"[Error Auto-Fixer] Iniciando auto-diagnóstico para: {error_summary}")
    
    # Realizar búsqueda web
    search_results = search_error_solutions(error_summary)
    
    # Consultar al LLM para obtener la sugerencia
    try:
        llm = get_llm()
        
        system_prompt = (
            "Eres el módulo de Auto-diagnóstico de Errores de Jarvis.\n"
            "Tu tarea es analizar la ejecución de un comando de consola fallido, su salida de error (stderr/stdout) "
            "y la información de internet recopilada sobre el error.\n"
            "Identifica la causa raíz del fallo en español y propón la corrección exacta del código.\n"
            "Reglas de formato:\n"
            "1. Explica brevemente el error y la causa en español.\n"
            "2. Proporciona el fragmento de código corregido de manera completa dentro de un bloque de código Markdown (especificando el lenguaje, ej. ```python o ```php).\n"
            "3. Si la corrección requiere instalar una dependencia, indica el comando a ejecutar.\n"
            "4. Sé sumamente preciso. No inventes soluciones."
        )
        
        prompt = (
            f"Comando ejecutado: {command}\n\n"
            f"Salida estándar (stdout):\n{stdout[-1000:]}\n\n"
            f"Salida de error (stderr):\n{stderr[-1500:]}\n\n"
            f"Resultados de la búsqueda web para '{error_summary}':\n{search_results[:3000]}\n\n"
            "Genera tu diagnóstico y propuesta de corrección en español:"
        )
        
        messages = [
            ("system", system_prompt),
            ("human", prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content if hasattr(response, 'content') else str(response)
        
        formatted_report = (
            "\n\n=========================================\n"
            "🔍 [AUTO-DIAGNÓSTICO DE ERRORES DE JARVIS]\n"
            f"{content}\n"
            "=========================================\n"
        )
        return formatted_report
        
    except Exception as e:
        logging.error(f"[Error Auto-Fixer] Error durante la consulta al LLM: {e}")
        return f"\n\n⚠️ [AUTO-DIAGNÓSTICO] No se pudo generar la propuesta de solución. Error: {e}\n"
