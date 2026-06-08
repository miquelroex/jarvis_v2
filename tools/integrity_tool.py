from langchain.tools import tool

@tool
def run_jarvis_integrity_audit(query: str = "") -> str:
    """
    Performs a full integrity and health audit on the Jarvis codebase, including checking files syntax,
    verifying langchain tools imports, validating necessary environment variables in .env, and executing
    the local unit test suite.
    Use this tool when the user asks to 'check codebase health', 'run integrity audit', 'verify code',
    'check if everything is working correctly', or 'test jarvis'.
    """
    from core.jarvis_integrity import run_integrity_check
    
    report = run_integrity_check()
    status = report.get("status", "secure").upper()
    
    # Mapear estados a iconos y colores
    status_icon = "🟢"
    if status == "WARNING":
        status_icon = "🟡"
    elif status == "CRITICAL":
        status_icon = "🔴"
        
    md = f"### {status_icon} Reporte de Integridad de Jarvis (Estado: {status})\n"
    md += f"*Escaneado el*: `{report.get('last_scan')}`\n\n"
    
    # 1. Chequeo de sintaxis
    syntax_fails = report.get("syntax_failures", [])
    if not syntax_fails:
        md += "✔ **Análisis de Sintaxis**: Todos los archivos Python en `core/`, `tools/` y `gui/` son sintácticamente válidos.\n"
    else:
        md += f"❌ **Análisis de Sintaxis**: Se detectaron {len(syntax_fails)} errores:\n"
        for f in syntax_fails:
            md += f"  - `{f['file']}`: {f['error']}\n"
            
    # 2. Chequeo de carga de herramientas
    tools_fails = report.get("tools_failures", [])
    if not tools_fails:
        md += "✔ **Importación de Herramientas**: Todas las herramientas se importaron y registraron con éxito.\n"
    else:
        md += f"❌ **Importación de Herramientas**: Falló la carga de {len(tools_fails)} herramientas:\n"
        for f in tools_fails:
            md += f"  - `{f['file']}`: {f['error']}\n"
            
    # 3. Chequeo de entorno
    env_check = report.get("env_check", [])
    configured_count = sum(1 for item in env_check if item["configured"])
    md += f"✔ **Variables de Entorno**: {configured_count}/{len(env_check)} variables configuradas.\n"
    missing_critical = [item["name"] for item in env_check if not item["configured"] and item["name"] in ["OPENAI_API_KEY", "GOOGLE_API_KEY"]]
    if missing_critical:
        md += f"  - ⚠ *Faltan variables críticas*: {', '.join(missing_critical)}\n"
        
    # 4. Suite de pruebas
    tests = report.get("test_results", {})
    if tests.get("passed"):
        md += f"✔ **Pruebas Unitarias**: La suite de pruebas pasó con éxito (`{tests.get('ran')}/{tests.get('ran')}` tests OK).\n"
    else:
        md += f"❌ **Pruebas Unitarias**: Fallaron tests en la suite (`{tests.get('ran') - tests.get('failures') - tests.get('errors')}/{tests.get('ran')}` tests OK).\n"
        md += f"  - Detalle: {tests.get('failures')} fallos, {tests.get('errors')} errores.\n"
        
    return md
