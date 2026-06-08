from langchain.tools import tool

@tool
def run_vulnerability_audit(query: str = "") -> str:
    """
    Performs a security audit on the python dependencies listed in requirements.txt.
    It queries the OSV database, identifies vulnerabilities (CVEs) and returns a detailed Markdown report.
    Use this tool when the user asks to 'check dependencies', 'run security audit', 'find vulnerabilities', or 'scan requirements'.
    """
    from core.vulnerability_patcher import run_dependency_audit
    
    report = run_dependency_audit()
    findings = report.get("findings", [])
    
    if not findings:
        return "🟢 Excelente noticia, señor. No se encontraron dependencias vulnerables (CVEs) en su archivo requirements.txt."
        
    md = f"### 🔴 Reporte de Vulnerabilidades detectadas ({report.get('last_scan')}):\n\n"
    for idx, f in enumerate(findings, start=1):
        md += f"{idx}. **{f['package']}** (Versión actual: `{f['current_version']}` -> Recomendada: `{f['latest_version']}`)\n"
        md += f"   *Estado*: `{f['status'].upper()}`\n"
        md += "   *Vulnerabilidades encontradas*:\n"
        for v in f["vulnerabilities"]:
            md += f"     - **[{v['id']}]**: {v['summary']}\n"
        md += "\n"
        
    md += "Señor, puede aplicar la actualización automática en la GUI web o pidiéndome: 'actualiza la dependencia <nombre_paquete>'."
    return md

@tool
def apply_package_patch(package_name: str, target_version: str) -> str:
    """
    Applies a security patch to update a specific package to the target_version in requirements.txt and virtualenv.
    It automatically runs tests to validate regression and reverts the patch if they fail.
    Use this tool when the user asks to 'update package', 'patch dependency', or 'apply patch' for a package.
    """
    from core.vulnerability_patcher import apply_vulnerability_patch
    
    res = apply_vulnerability_patch(package_name, target_version)
    if res.get("success"):
        return f"✅ Señor, {res.get('message')}"
    else:
        return f"❌ Señor, falló la aplicación del parche: {res.get('error')}"
