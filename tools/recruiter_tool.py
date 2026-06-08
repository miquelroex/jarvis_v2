import json
from langchain.tools import tool
from core.smart_recruiter import (
    scan_workspace_tech_stack,
    search_web_jobs,
    generate_tailored_cover_letter
)

@tool
def scan_workspace_tech_profile(path: str = None) -> str:
    """
    Scans the current workspace to profile the user's technology stack (languages and dependencies).
    Use this when the user asks to analyze their repository stack or profile their technical skills.
    """
    try:
        profile = scan_workspace_tech_stack(path)
        
        # Generar reporte en Markdown
        report = "📋 **PERFIL TECNOLÓGICO DEL REPOSITORIO**\n\n"
        report += f"**Resumen:** {profile.get('summary')}\n\n"
        
        # Archivos/Lenguajes
        if profile.get("file_counts"):
            report += "### 🗂️ Distribución de Archivos por Lenguaje\n"
            for lang, count in sorted(profile["file_counts"].items(), key=lambda x: x[1], reverse=True):
                report += f"- **{lang}**: {count} archivos\n"
            report += "\n"
            
        # Dependencias
        if profile.get("dependencies"):
            report += "### 📦 Dependencias y Módulos Detectados\n"
            for manager, deps in profile["dependencies"].items():
                if deps:
                    report += f"- **{manager.upper()}**: {', '.join(deps[:15])}"
                    if len(deps) > 15:
                        report += f" (y {len(deps) - 15} más)"
                    report += "\n"
                    
        return report
    except Exception as e:
        return f"Error al escanear el stack del espacio de trabajo: {e}"

@tool
def search_job_offers(query: str, limit: int = 5) -> str:
    """
    Searches online job portals for jobs matching the query.
    - query: Job title or keywords (e.g., 'React remote developer', 'Python backend Spain').
    - limit: Maximum number of job offers to return (default is 5).
    """
    try:
        jobs = search_web_jobs(query, limit)
        if not jobs:
            return f"No encontré ofertas de empleo relevantes para la consulta: \"{query}\"."
            
        report = f"🔍 **OFERTAS DE EMPLEO DETECTADAS PARA: \"{query}\"**\n\n"
        report += "Usa `generate_job_cover_letter` con el ID del trabajo para pre-redactar una carta de presentación.\n\n"
        report += "| ID | Empresa | Puesto | Requisitos | Enlace |\n"
        report += "| :--- | :--- | :--- | :--- | :--- |\n"
        
        for idx, job in enumerate(jobs):
            company = job.get("company", "Desconocida")
            title = job.get("title", "Puesto")
            url = job.get("url", "#")
            reqs = ", ".join(job.get("requirements", [])) if job.get("requirements") else "No especificados"
            
            # Formatear link
            link = f"[Ver Oferta]({url})" if url and url != "#" else "No disponible"
            report += f"| **{idx}** | {company} | {title} | {reqs} | {link} |\n"
            
        report += "\n*Señor, puede pedirme redactar una carta de presentación diciendo: 'redacta la carta para el ID X' o similar.*"
        return report
    except Exception as e:
        return f"Error al buscar ofertas de empleo: {e}"

@tool
def generate_job_cover_letter(job_index: int) -> str:
    """
    Generates a personalized cover letter (carta de presentación) matching the developer's tech profile
    to a selected job offer.
    - job_index: The numerical ID/index of the job offer returned by search_job_offers (e.g., 0, 1, 2).
    """
    try:
        # Validar entrada
        try:
            idx = int(job_index)
        except ValueError:
            return "Error: El índice del trabajo debe ser un número entero."
            
        return generate_tailored_cover_letter(idx)
    except Exception as e:
        return f"Error al procesar la generación de la carta: {e}"
