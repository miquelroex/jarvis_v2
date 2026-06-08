from langchain.tools import tool

@tool
def run_privacy_scan(force: bool = False) -> str:
    """
    Runs a workspace security/privacy scan to check for exposed API keys, tokens, or hardcoded passwords.
    Returns a Markdown formatted report of findings or confirms the codebase is secure.
    """
    from core.privacy_sentinel import scan_workspace_privacy
    
    try:
        findings = scan_workspace_privacy()
    except Exception as e:
        return f"Error al ejecutar el escaneo de privacidad: {e}"
        
    if not findings:
        return "🟢 Excelente noticia, señor. He escaneado el espacio de trabajo y no he detectado ninguna clave de API o secreto expuesto."
        
    report = "🔴 **ALERTA DE SEGURIDAD: Llaves y secretos expuestos detectados**\n\n"
    report += "He detectado los siguientes secretos en el espacio de trabajo que deberían ser protegidos o agregados a `.gitignore`:\n\n"
    
    for idx, f in enumerate(findings, start=1):
        report += (
            f"{idx}. **Tipo**: {f['type']}\n"
            f"   - **Archivo**: `{f['file']}` (Línea {f['line']})\n"
            f"   - **Valor censurado**: `{f['snippet']}`\n"
            f"   - **Hash**: `{f['hash']}`\n\n"
        )
        
    report += "Señor, le recomiendo encarecidamente mover estas llaves a un archivo `.env` o agregarlas a la lista de ignorados de la GUI si son falsos positivos."
    return report
