import ast
import difflib
import os
import logging
from tools.model_delegate import ask_code_model

def scan_file_for_undocumented_elements(file_path: str) -> list[dict]:
    """
    Analiza un archivo Python y busca clases, funciones, métodos y endpoints sin documentar.
    Retorna una lista de diccionarios con la telemetría del elemento.
    """
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code)
    except Exception as e:
        logging.error(f"[Code Documenter] Error al parsear el archivo {file_path}: {e}")
        return []

    undocumented = []
    
    class CodeVisitor(ast.NodeVisitor):
        def __init__(self):
            self.current_class = None
            
        def visit_ClassDef(self, node):
            doc = ast.get_docstring(node)
            if not doc or not doc.strip():
                undocumented.append({
                    "name": node.name,
                    "type": "class",
                    "line": node.lineno,
                    "parent_class": None
                })
            
            prev_class = self.current_class
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = prev_class
            
        def visit_FunctionDef(self, node):
            self._check_function(node)
            
        def visit_AsyncFunctionDef(self, node):
            self._check_function(node)
            
        def _check_function(self, node):
            doc = ast.get_docstring(node)
            if not doc or not doc.strip():
                # Determinar si es un endpoint
                is_endpoint = False
                for dec in node.decorator_list:
                    dec_name = ""
                    if isinstance(dec, ast.Call):
                        func = dec.func
                    else:
                        func = dec
                        
                    if isinstance(func, ast.Attribute):
                        dec_name = func.attr
                    elif isinstance(func, ast.Name):
                        dec_name = func.id
                        
                    if dec_name in ("route", "get", "post", "put", "delete", "patch"):
                        is_endpoint = True
                        break
                
                elem_type = "endpoint" if is_endpoint else ("method" if self.current_class else "function")
                undocumented.append({
                    "name": node.name,
                    "type": elem_type,
                    "line": node.lineno,
                    "parent_class": self.current_class
                })
            self.generic_visit(node)
            
    visitor = CodeVisitor()
    visitor.visit(tree)
    return undocumented

def find_node_by_name(tree, target_name: str, parent_class: str = None):
    """Busca el nodo AST de clase o función que coincide con el nombre y clase padre."""
    class Finder(ast.NodeVisitor):
        def __init__(self):
            self.current_class = None
            self.found_node = None
            
        def visit_ClassDef(self, node):
            if node.name == target_name and parent_class is None:
                self.found_node = node
                return
            prev_class = self.current_class
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = prev_class
            
        def visit_FunctionDef(self, node):
            self._check_func(node)
            
        def visit_AsyncFunctionDef(self, node):
            self._check_func(node)
            
        def _check_func(self, node):
            if node.name == target_name:
                if parent_class == self.current_class:
                    self.found_node = node
                    
    finder = Finder()
    finder.visit(tree)
    return finder.found_node

def generate_docstring_for_element(file_path: str, target_name: str, parent_class: str = None) -> tuple[str, str, str]:
    """
    Genera el docstring PEP 257 para un elemento específico.
    Retorna una tupla (codigo_modificado, diff_unificado, error_msg).
    """
    if not os.path.exists(file_path):
        return "", "", f"El archivo '{file_path}' no existe."
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_code = f.read()
        tree = ast.parse(original_code)
    except Exception as e:
        return "", "", f"Error al parsear el archivo original: {str(e)}"
        
    node = find_node_by_name(tree, target_name, parent_class)
    if not node:
        return "", "", f"No se encontró el elemento '{target_name}' en {file_path}."
        
    # Obtener el código fuente exacto del elemento
    try:
        source_segment = ast.get_source_segment(original_code, node)
    except Exception as e:
        return "", "", f"Error al extraer el código fuente del elemento: {str(e)}"
        
    # Llamar al modelo de código para generar el docstring
    prompt = f"""Genera un docstring PEP 257 profesional en español usando el estilo de Google para la siguiente función/clase/método en Python.
El docstring debe describir qué hace el elemento de forma concisa, detallar los parámetros (Args) si existen, el valor de retorno (Returns) si lo hay, y excepciones (Raises) si aplica.

Devuelve ÚNICAMENTE el bloque del docstring (incluyendo las triples comillas dobles al inicio y al final) sin código de la función ni explicaciones adicionales.

Código fuente del elemento:
\"\"\"
{source_segment}
\"\"\"
"""
    try:
        docstring = ask_code_model(prompt).strip()
        
        # Limpiar bloques de código markdown que el LLM pueda devolver
        if docstring.startswith("```"):
            lines_doc = docstring.splitlines()
            if lines_doc[0].startswith("```"):
                lines_doc = lines_doc[1:]
            if lines_doc and lines_doc[-1].startswith("```"):
                lines_doc = lines_doc[:-1]
            docstring = "\n".join(lines_doc).strip()
            
        # Asegurar que empieza y termina con comillas de docstring triples
        if not docstring.startswith('"""'):
            if docstring.startswith("'''"):
                docstring = '"""' + docstring[3:]
            else:
                docstring = '"""' + docstring
        if not docstring.endswith('"""'):
            if docstring.endswith("'''"):
                docstring = docstring[:-3] + '"""'
            else:
                docstring = docstring + '"""'
    except Exception as e:
        return "", "", f"Error al invocar el modelo de código: {str(e)}"

    # Insertar el docstring en el código original
    lines = original_code.splitlines(keepends=True)
    
    # Determinar si ya tiene un docstring (la primera sentencia del cuerpo es un Constant/Expr String)
    has_existing = False
    doc_node = None
    if node.body:
        first_node = node.body[0]
        # En Python 3.8+, docstring es Expr con Constant de tipo str
        if isinstance(first_node, ast.Expr) and isinstance(first_node.value, ast.Constant) and isinstance(first_node.value.value, str):
            has_existing = True
            doc_node = first_node
            
    # Obtener la indentación del primer nodo del cuerpo
    first_body_line_num = node.body[0].lineno
    first_body_line = lines[first_body_line_num - 1]
    indentation = ""
    for char in first_body_line:
        if char in (' ', '\t'):
            indentation += char
        else:
            break
            
    # Indentar el docstring generado
    indented_doc_lines = []
    for line in docstring.splitlines():
        if line.strip():
            indented_doc_lines.append(indentation + line + "\n")
        else:
            indented_doc_lines.append("\n")
            
    modified_lines = list(lines)
    
    if has_existing:
        # Reemplazar docstring existente
        start_idx = doc_node.lineno - 1
        end_idx = doc_node.end_lineno
        modified_lines[start_idx:end_idx] = indented_doc_lines
    else:
        # Insertar docstring antes del primer statement del cuerpo
        insert_idx = node.body[0].lineno - 1
        modified_lines[insert_idx:insert_idx] = indented_doc_lines
        
    modified_code = "".join(modified_lines)
    
    # Generar diff unificado
    file_name = os.path.basename(file_path)
    diff = "".join(difflib.unified_diff(
        lines,
        modified_lines,
        fromfile=f"a/{file_name}",
        tofile=f"b/{file_name}"
    ))
    
    return modified_code, diff, ""

def write_documenter_changes(file_path: str, modified_code: str) -> bool:
    """Escribe los cambios documentados en el archivo original."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(modified_code)
        return True
    except Exception as e:
        logging.error(f"[Code Documenter] Error al escribir cambios en {file_path}: {e}")
        return False
