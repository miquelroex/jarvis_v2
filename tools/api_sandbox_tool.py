import os
from langchain.tools import tool
from core.api_sandbox import (
    scan_project_endpoints,
    detect_active_dev_port,
    test_local_endpoints,
    generate_sandbox_html,
    SANDBOX_FILE
)

@tool
def scan_and_generate_api_sandbox(port: int = None) -> str:
    """
    Scans the codebase for local API endpoints (Flask, FastAPI, Express), auto-detects
    the active local port, and generates an interactive, styled HTML playground.
    The generated sandbox is saved locally and returned as a code block.
    """
    try:
        endpoints = scan_project_endpoints()
        if not endpoints:
            return "No se encontraron endpoints locales definidos en el código del espacio de trabajo."
            
        target_port = port if port is not None else detect_active_dev_port()
        
        # Generar sandbox HTML
        sandbox_path = generate_sandbox_html(endpoints, target_port)
        if not sandbox_path or not sandbox_path.exists():
            return "Error al compilar la interfaz del API Sandbox."
            
        html_code = sandbox_path.read_text(encoding="utf-8")
        project_root = Path(__file__).resolve().parent.parent
        rel_path = sandbox_path.relative_to(project_root).as_posix()
        
        report = (
            f"🟢 **API Sandbox generado con éxito**\n\n"
            f"Se ha guardado la interfaz interactiva en `{rel_path}` configurada para el puerto **{target_port}**.\n"
            f"Se detectaron un total de **{len(endpoints)}** endpoints en el proyecto.\n\n"
            f"Puedes ver la interfaz interactiva y enviar peticiones reales desde el panel de artefactos a la derecha:\n"
            f"```html\n"
            f"{html_code}\n"
            f"```"
        )
        return report
    except Exception as e:
        return f"Error al generar el API Sandbox: {e}"

@tool
def run_api_health_check(port: int = None) -> str:
    """
    Runs an active, automated health check of your local development server endpoints.
    It queries all static endpoints locally and returns an operational scorecard.
    """
    try:
        endpoints = scan_project_endpoints()
        if not endpoints:
            return "No se encontraron endpoints locales en el proyecto para verificar."
            
        target_port = port if port is not None else detect_active_dev_port()
        
        # Ejecutar peticiones locales en segundo plano
        results = test_local_endpoints(endpoints, target_port)
        
        report = f"🏥 **REPORTE DE SALUD DE API LOCAL (Puerto: {target_port})**\n\n"
        report += "| Método | Ruta | Estado / Código | Latencia | Estado |\n"
        report += "| :--- | :--- | :--- | :--- | :--- |\n"
        
        online_count = 0
        for r in results:
            method = r["method"]
            path = r["path"]
            status = r["status"]
            latency = f"{r['latency_ms']} ms" if r["latency_ms"] > 0 else "-"
            
            # Formatear indicador
            if r["online"] and isinstance(status, int) and status < 400:
                indicator = "🟢 ONLINE"
                online_count += 1
            elif r["online"] and status == "Ignorado (Ruta variable)":
                indicator = "🟡 VARIABLE"
                online_count += 1
            elif r["online"] and isinstance(status, int) and status >= 400:
                indicator = "🟡 ERR_STATUS"
                online_count += 1
            else:
                indicator = "🔴 OFFLINE"
                
            report += f"| **{method}** | `{path}` | {status} | {latency} | {indicator} |\n"
            
        total = len(results)
        report += f"\n**Resumen de salud:** {online_count}/{total} endpoints respondiendo u operacionales."
        return report
    except Exception as e:
        return f"Error al realizar la validación de salud de la API: {e}"

# Importar Path de forma segura
from pathlib import Path
