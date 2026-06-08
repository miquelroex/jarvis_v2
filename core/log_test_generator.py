import os
import re
import json
import uuid
import subprocess
import logging
import ast
from pathlib import Path
from core.llm_factory import get_llm

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def extract_referenced_files(error_text: str) -> list:
    """Busca archivos .py mencionados en tracebacks y retorna rutas relativas únicas."""
    # Expresión regular común para tracebacks de Python: File "path/to/file.py", line 12
    pattern = r'File "([^"]+\.py)"'
    matches = re.findall(pattern, error_text)
    
    unique_files = []
    for match in matches:
        # Normalizar la ruta y verificar si está dentro del workspace
        file_path = Path(match)
        if not file_path.is_absolute():
            file_path = PROJECT_ROOT / file_path
        
        try:
            # Asegurarse de que el archivo existe y está dentro del proyecto
            if file_path.exists() and file_path.is_file() and PROJECT_ROOT in file_path.resolve().parents:
                rel_path = file_path.resolve().relative_to(PROJECT_ROOT.resolve())
                rel_str = str(rel_path).replace("\\", "/")
                if rel_str not in unique_files and not rel_str.startswith("tests/"):
                    unique_files.append(rel_str)
        except Exception:
            pass
            
    return unique_files

def generate_reproduction_test(log_path: str = None) -> dict:
    """
    Analiza un log de error, carga el contexto del código involucrado,
    genera un test unitario que reproduce el fallo y verifica que falle de forma esperada.
    """
    if log_path is None:
        log_path = str(PROJECT_ROOT / "logs" / "last_exception.json")
        
    log_file = Path(log_path)
    if not log_file.exists():
        return {
            "success": False,
            "error": f"No se encontró el archivo de logs de error en: {log_path}"
        }
        
    try:
        data = json.loads(log_file.read_text(encoding="utf-8"))
        command = data.get("command", "")
        stdout = data.get("stdout", "")
        stderr = data.get("stderr", "")
    except Exception as e:
        return {
            "success": False,
            "error": f"Fallo al leer o parsear el archivo de logs: {e}"
        }
        
    combined_output = f"{stdout}\n{stderr}"
    referenced_files = extract_referenced_files(combined_output)
    
    # Cargar código de los archivos involucrados
    code_context = ""
    for rel_file in referenced_files:
        try:
            content = (PROJECT_ROOT / rel_file).read_text(encoding="utf-8")
            # Limitar longitud del archivo para no saturar tokens
            lines = content.splitlines()
            if len(lines) > 300:
                content = "\n".join(lines[:300]) + "\n... [truncado por longitud]"
            code_context += f"\n--- Archivo: {rel_file} ---\n{content}\n"
        except Exception as file_err:
            logging.warning(f"[Log-to-Test] No se pudo leer {rel_file}: {file_err}")

    # Consultar al LLM para generar el test
    try:
        llm = get_llm()
        system_prompt = (
            "Eres el módulo Auto-Generador de Pruebas de Jarvis (Log-to-Test Generator).\n"
            "Tu tarea es generar un archivo de prueba unitaria en Python (usando unittest.TestCase) "
            "que reproduzca fielmente el error/excepción detallado en el log.\n"
            "Reglas críticas:\n"
            "1. La prueba debe importar los módulos/clases del proyecto necesarios (ej. `from core.notifier import send_push_notification`).\n"
            "2. La prueba debe estar diseñada para FALLAR (levantar la misma excepción o error) para asegurar que el fallo ha sido replicado en local.\n"
            "3. Si la función interactúa con APIs externas, red, bases de datos o servicios del sistema, debes simularlos (mockearlos) apropiadamente usando `unittest.mock`.\n"
            "4. Responde ÚNICAMENTE con el bloque de código de Python encerrado en triple comilla simple o doble (ej. ```python ... ```).\n"
            "5. El código debe ser sintácticamente válido en Python 3.\n"
            "6. Mantén la simplicidad y claridad."
        )
        
        prompt = (
            f"Comando original ejecutado: {command}\n\n"
            f"Salida de Error / Traceback:\n{combined_output}\n\n"
            f"Contexto del Código Involucrado:\n{code_context}\n\n"
            "Genera el código de la prueba unitaria (unittest) en Python que reproduzca este fallo:"
        )
        
        messages = [
            ("system", system_prompt),
            ("human", prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Extraer el bloque de código
        code_match = re.search(r"```python\s*([\s\S]*?)```", content)
        if code_match:
            test_code = code_match.group(1).strip()
        else:
            test_code = content.strip()
            # Si tiene markdown adicional, limpiarlo
            test_code = re.sub(r"^```python|```$", "", test_code).strip()
            
        # Validar sintaxis
        try:
            ast.parse(test_code)
        except SyntaxError as syntax_err:
            return {
                "success": False,
                "error": f"El código de prueba generado contiene errores de sintaxis: {syntax_err}",
                "generated_raw": content
            }
            
        # Crear la carpeta tests si no existe y guardar el archivo físico
        tests_dir = PROJECT_ROOT / "tests"
        tests_dir.mkdir(exist_ok=True)
        
        unique_id = uuid.uuid4().hex[:8]
        test_filename = f"test_reproduce_{unique_id}.py"
        test_file_path = tests_dir / test_filename
        
        test_file_path.write_text(test_code, encoding="utf-8")
        logging.info(f"[Log-to-Test] Test de reproducción guardado en: {test_file_path}")
        
        # Ejecutar el test generado para verificar si reproduce el error (esperamos que falle)
        test_cmd = f".venv\\Scripts\\python.exe -m unittest tests/{test_filename}"
        res = subprocess.run(
            test_cmd,
            shell=True,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15
        )
        
        # El test "reproduce con éxito" si falla (retorna diferente de 0)
        reproduced = res.returncode != 0
        
        explanation = (
            f"Se ha analizado el error y se ha creado una prueba de reproducción en `tests/{test_filename}`.\n\n"
            f"**Resultado de la Reproducción**: "
            f"{'✅ ÉXITO (El test falló como se esperaba replicando el error)' if reproduced else '❌ FALLO (El test se ejecutó pero pasó con éxito, no se pudo replicar el error en local)'}.\n\n"
            f"**Salida del Test ejecutado**:\n```\n{res.stdout or res.stderr}\n```"
        )
        
        return {
            "success": True,
            "test_file": str(test_file_path),
            "test_code": test_code,
            "reproduced": reproduced,
            "test_output": f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}",
            "explanation": explanation
        }
        
    except Exception as e:
        logging.error(f"[Log-to-Test] Error durante la generación del test: {e}")
        return {
            "success": False,
            "error": f"Fallo en la generación o ejecución del test de reproducción. Detalles: {e}"
        }
