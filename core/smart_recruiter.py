import os
import json
import re
import logging
from pathlib import Path
from core.llm_factory import get_llm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
COVER_LETTERS_DIR = PROJECT_ROOT / "cover_letters"
TECH_PROFILE_FILE = LOGS_DIR / "tech_profile.json"
JOB_OFFERS_FILE = LOGS_DIR / "job_offers.json"

def scan_workspace_tech_stack(workspace_path: str = None) -> dict:
    """
    Analiza el espacio de trabajo en busca de lenguajes, frameworks y dependencias.
    Persiste y retorna el perfil tecnológico en logs/tech_profile.json.
    """
    if workspace_path is None:
        root = PROJECT_ROOT
    else:
        root = Path(workspace_path)
        
    LOGS_DIR.mkdir(exist_ok=True)
    
    languages = {}
    dependencies = {
        "npm": [],
        "pip": [],
        "composer": [],
        "cargo": [],
        "go": []
    }
    
    # Extensiones de interés
    ext_mapping = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript (React)",
        ".ts": "TypeScript",
        ".tsx": "TypeScript (React)",
        ".rs": "Rust",
        ".go": "Go",
        ".php": "PHP",
        ".html": "HTML",
        ".css": "CSS",
        ".sql": "SQL",
        ".java": "Java",
        ".cpp": "C++",
        ".c": "C",
        ".sh": "Shell Script",
        ".bat": "Batch Script"
    }
    
    file_counts = {}
    
    # Recorrer directorios de manera segura
    exclude_dirs = {
        '.venv', 'venv', 'node_modules', '.git', 'logs', 'cover_letters',
        '__pycache__', 'dist', 'build', '.gemini', 'brain', '.idea', '.vscode'
    }
    
    for r_dir, dirs, files in os.walk(root):
        # Excluir directorios pesados
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            p = Path(r_dir) / file
            ext = p.suffix.lower()
            if ext in ext_mapping:
                lang = ext_mapping[ext]
                file_counts[lang] = file_counts.get(lang, 0) + 1
                
            # Parsea dependencias de archivos conocidos
            if file == "package.json":
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    deps = data.get("dependencies", {})
                    dev_deps = data.get("devDependencies", {})
                    for dep in list(deps.keys()) + list(dev_deps.keys()):
                        if dep not in dependencies["npm"]:
                            dependencies["npm"].append(dep)
                except Exception:
                    pass
            elif file == "requirements.txt":
                try:
                    for line in p.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Limpiar versión
                            dep_name = re.split(r'==|>=|<=|>|<|~=', line)[0].strip()
                            if dep_name and dep_name not in dependencies["pip"]:
                                dependencies["pip"].append(dep_name)
                except Exception:
                    pass
            elif file == "composer.json":
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    reqs = data.get("require", {})
                    reqs_dev = data.get("require-dev", {})
                    for dep in list(reqs.keys()) + list(reqs_dev.keys()):
                        if dep not in dependencies["composer"]:
                            dependencies["composer"].append(dep)
                except Exception:
                    pass
            elif file == "Cargo.toml":
                try:
                    content = p.read_text(encoding="utf-8")
                    in_deps = False
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("[dependencies]"):
                            in_deps = True
                            continue
                        elif line.startswith("[") and in_deps:
                            in_deps = False
                        if in_deps and line and not line.startswith("#"):
                            parts = line.split("=")
                            dep_name = parts[0].strip()
                            if dep_name and dep_name not in dependencies["cargo"]:
                                dependencies["cargo"].append(dep_name)
                except Exception:
                    pass
            elif file == "go.mod":
                try:
                    for line in p.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line.startswith("require") or (line and not line.startswith("module") and not line.startswith("go") and not line.startswith("require") and not line.startswith(")") and not line.startswith("(")):
                            parts = line.replace("require", "").strip().split()
                            if parts:
                                dep_name = parts[0].strip()
                                if dep_name and dep_name not in dependencies["go"]:
                                    dependencies["go"].append(dep_name)
                except Exception:
                    pass

    # Generar un resumen general a partir del perfil
    summary_parts = []
    if file_counts:
        top_langs = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        lang_strs = [f"{lang} ({count} archivos)" for lang, count in top_langs]
        summary_parts.append(f"Lenguajes predominantes: {', '.join(lang_strs)}.")
        
    active_deps = []
    for manager, dep_list in dependencies.items():
        if dep_list:
            active_deps.append(f"{len(dep_list)} dependencias de {manager.upper()}")
    if active_deps:
        summary_parts.append(f"Detectadas {', '.join(active_deps)}.")
        
    summary = " ".join(summary_parts) if summary_parts else "No se detectaron tecnologías predominantes en el espacio de trabajo actual."
    
    profile = {
        "file_counts": file_counts,
        "dependencies": {k: v for k, v in dependencies.items() if v},
        "summary": summary
    }
    
    try:
        TECH_PROFILE_FILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logging.error(f"[Smart Recruiter] Error writing tech profile file: {e}")
        
    return profile

def search_web_jobs(query: str, limit: int = 5) -> list[dict]:
    """
    Busca ofertas de empleo usando Tavily o DuckDuckGo y las parsea a JSON estructurado.
    Guarda el resultado en logs/job_offers.json.
    """
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    search_results = []
    
    if tavily_api_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=tavily_api_key)
            response = client.search(
                query=f"{query} job postings",
                search_depth="advanced",
                max_results=limit
            )
            results = response.get("results", [])
            for r in results:
                search_results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")
                })
        except Exception as e:
            logging.error(f"[Smart Recruiter] Tavily search error: {e}")
            
    if not search_results:
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = ddgs.text(f"{query} job postings", max_results=limit)
                for r in list(results):
                    search_results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "content": r.get("body", "")
                    })
        except Exception as e:
            logging.error(f"[Smart Recruiter] DuckDuckGo search error: {e}")
            
    if not search_results:
        return []
        
    try:
        llm = get_llm()
        system_prompt = (
            "Eres el agente Smart Recruiter de Jarvis.\n"
            "Tu tarea es analizar los resultados de búsqueda web sobre ofertas de empleo y extraer la información de forma estructurada en formato JSON.\n"
            "Debes retornar UNICAMENTE un arreglo JSON válido con hasta 5 objetos. Cada objeto debe tener exactamente las siguientes llaves:\n"
            "- 'company': Nombre de la empresa.\n"
            "- 'title': Nombre o título del puesto.\n"
            "- 'url': Enlace original a la oferta.\n"
            "- 'requirements': Lista de strings con las tecnologías, lenguajes o requisitos clave.\n"
            "- 'description': Resumen breve (2 oraciones) de las responsabilidades o el puesto.\n"
            "\n"
            "Ejemplo de formato esperado:\n"
            "[\n"
            "  {\n"
            "    \"company\": \"Stark Industries\",\n"
            "    \"title\": \"Senior Python Developer\",\n"
            "    \"url\": \"https://stark.com/careers/123\",\n"
            "    \"requirements\": [\"Python\", \"Django\", \"Git\"],\n"
            "    \"description\": \"Diseñar sistemas de control y automatización para trajes Stark en Django...\"\n"
            "  }\n"
            "]\n"
            "Si un dato no está disponible, infiérelo de forma razonable o déjalo como string vacío o lista vacía. No agregues texto explicativo fuera del JSON."
        )
        
        user_prompt = f"Resultados de búsqueda web de ofertas de trabajo:\n{json.dumps(search_results, indent=2)}\n\nExtrae y estructura las ofertas de empleo en JSON:"
        
        messages = [
            ("system", system_prompt),
            ("human", user_prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content if hasattr(response, 'content') else str(response)
        
        json_match = re.search(r"```json\s*([\s\S]*?)```", content)
        if json_match:
            content = json_match.group(1).strip()
        else:
            content = content.strip()
            
        jobs = json.loads(content)
        
        LOGS_DIR.mkdir(exist_ok=True)
        JOB_OFFERS_FILE.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
        
        return jobs
    except Exception as e:
        logging.error(f"[Smart Recruiter] Error parsing jobs with LLM: {e}")
        basic_jobs = []
        for idx, r in enumerate(search_results):
            basic_jobs.append({
                "company": "Compañía Desconocida",
                "title": r["title"][:60],
                "url": r["url"],
                "requirements": [],
                "description": r["content"][:200]
            })
        try:
            JOB_OFFERS_FILE.write_text(json.dumps(basic_jobs, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        return basic_jobs

def generate_tailored_cover_letter(job_index: int) -> str:
    """
    Genera una carta de presentación a medida a partir del perfil tecnológico y la oferta elegida.
    La carta se guarda en la carpeta cover_letters/ y se devuelve como texto Markdown.
    """
    if not JOB_OFFERS_FILE.exists():
        return "Error: No se han buscado ofertas de empleo recientemente. Por favor, realiza una búsqueda primero."
        
    try:
        jobs = json.loads(JOB_OFFERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return "Error al leer las ofertas de empleo almacenadas en logs/job_offers.json."
        
    if job_index < 0 or job_index >= len(jobs):
        return f"Error: Índice de trabajo inválido. Por favor, selecciona un índice entre 0 y {len(jobs)-1}."
        
    job = jobs[job_index]
    
    profile = {}
    if TECH_PROFILE_FILE.exists():
        try:
            profile = json.loads(TECH_PROFILE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
            
    if not profile:
        profile = scan_workspace_tech_stack()
        
    try:
        llm = get_llm()
        system_prompt = (
            "Eres el agente Smart Recruiter de Jarvis, un asistente experto en redactar cartas de presentación y captar talento tecnológico.\n"
            "Tu tarea es redactar una carta de presentación (cover letter) profesional y altamente persuasiva en español.\n"
            "Pautas de redacción:\n"
            "1. Tono profesional, entusiasta pero sobrio, destacando soluciones y adaptabilidad.\n"
            "2. Usa el perfil técnico del desarrollador para justificar por qué es el candidato idóneo para el puesto.\n"
            "3. Enlaza los requisitos del puesto con las tecnologías reales que usa el desarrollador en su espacio de trabajo.\n"
            "4. Sé directo, evita rodeos, y redacta la carta lista para enviar (usa placeholders como [Tu Nombre], [Fecha], etc. si es necesario).\n"
            "5. Responde con formato Markdown claro."
        )
        
        user_prompt = (
            f"Perfil Técnico del Desarrollador:\n{json.dumps(profile, indent=2, ensure_ascii=False)}\n\n"
            f"Detalles del Puesto de Trabajo Seleccionado:\n{json.dumps(job, indent=2, ensure_ascii=False)}\n\n"
            "Por favor, genera la carta de presentación personalizada en Markdown:"
        )
        
        messages = [
            ("system", system_prompt),
            ("human", user_prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content if hasattr(response, 'content') else str(response)
        
        COVER_LETTERS_DIR.mkdir(exist_ok=True)
        
        # Sanitizar nombre de archivo
        clean_company = re.sub(r'[^a-zA-Z0-9_]', '', job.get("company", "desconocida")).lower().strip()
        clean_title = re.sub(r'[^a-zA-Z0-9_]', '', job.get("title", "puesto")).lower().strip()
        filename = f"carta_{clean_company}_{clean_title}.md"
        
        letter_file = COVER_LETTERS_DIR / filename
        letter_file.write_text(content, encoding="utf-8")
        
        rel_path = letter_file.relative_to(PROJECT_ROOT).as_posix()
        
        report = (
            f"🟢 **Carta de presentación generada con éxito**\n\n"
            f"Se ha guardado la carta personalizada en `{rel_path}` para la oferta de **{job.get('title')}** en **{job.get('company')}**.\n\n"
            "Puedes revisarla y copiarla directamente desde el panel de artefactos:\n"
            f"```markdown\n"
            f"{content}\n"
            f"```"
        )
        return report
    except Exception as e:
        logging.error(f"[Smart Recruiter] Error generating cover letter: {e}")
        return f"Error al generar la carta de presentación: {e}"
