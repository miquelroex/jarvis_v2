from langchain.tools import tool
from core.log_test_generator import generate_reproduction_test

@tool
def generate_test_from_error(log_path: str = None) -> str:
    """
    Analyzes the most recent failed command or exception log, reads the source code context,
    and automatically generates a reproducing Python unit test (unittest) under tests/ that is expected to fail.
    You can optionally provide a custom log_path.
    Use this tool when the user asks you to recreate a failing test scenario from logs or to generate a reproducer test.
    """
    res = generate_reproduction_test(log_path)
    if not res.get("success", False):
        return f"Error: {res.get('error', 'Ocurrió un error inesperado al generar el test.')}"
        
    return res.get("explanation", "Prueba de reproducción generada con éxito.")
