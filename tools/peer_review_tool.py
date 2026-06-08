import os
import re
import html
import logging
from pathlib import Path
from langchain.tools import tool
from tools.filesystem import _is_path_safe, WORKSPACE_ROOT
from core.llm_factory import get_llm

PEER_REVIEW_HTML = Path("logs/peer_review.html")

@tool
def audit_code_architecture(file_path: str) -> str:
    """
    Performs an architectural peer review of a code file by simulating a debate between two agents with opposite philosophies:
    - The Purist (Clean Code, SOLID, OOP patterns)
    - The Pragmatist (Simplicity, Performance, YAGNI, anti-overengineering)
    It creates an interactive cyberpunk HTML report at logs/peer_review.html and previews it in the UI.
    Use this tool when the user asks to "audit", "review architecture", "do peer review", or "debate design" of a file.
    """
    target_path = os.path.join(WORKSPACE_ROOT, file_path)
    
    if not _is_path_safe(target_path):
        return "Acceso denegado: No se permite auditar archivos fuera de la carpeta del proyecto, señor."
        
    if not os.path.exists(target_path):
        return f"El archivo '{file_path}' no existe en el espacio de trabajo, señor."
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            code_content = f.read()
    except Exception as e:
        return f"Error al leer el archivo para la auditoría: {e}"

    logging.info(f"[Peer Review] Iniciando auditoría y debate de doble agente para: {file_path}")
    
    # 1. Crítica del Purista
    llm = get_llm(temperature=0.3)
    prompt_purista = f"""Eres el 'Agente Purista' de Jarvis, un ingeniero de software senior experto que aboga de forma intransigente por SOLID, Clean Code, patrones de diseño clásicos, acoplamiento débil y testabilidad absoluta.
Analiza el siguiente código del archivo '{file_path}':
```
{code_content[:12000]}
```

Realiza una crítica arquitectónica detallada del diseño de este código. Señala acoplamiento, responsabilidades difusas o ineficiencias de Clean Code y propone cómo lo estructurarías teóricamente. Escribe tu respuesta en español, en tono analítico, formal y profesional.
"""
    try:
        critica_purista = llm.invoke(prompt_purista).content.strip()
    except Exception as e:
        return f"Error durante la fase del Purista: {e}"

    # 2. Réplica del Pragmático
    prompt_pragmatico = f"""Eres el 'Agente Pragmático' de Jarvis, un desarrollador de sistemas enfocado en simplicidad, rendimiento óptimo y velocidad de entrega (YAGNI). Aborreces la sobreingeniería y las abstracciones innecesarias.
Lee el código de '{file_path}' y la crítica teórica del Agente Purista:
--- CRÍTICA PURISTA ---
{critica_purista}

Responde directamente al Purista argumentando por qué su enfoque estructurado deClean Code podría resultar en sobreingeniería o ineficiencia práctica en este caso. Propón un enfoque más pragmático y simple. Escribe tu respuesta en español, con tono directo y profesional.
"""
    try:
        critica_pragmatico = llm.invoke(prompt_pragmatico).content.strip()
    except Exception as e:
        return f"Error durante la fase del Pragmático: {e}"

    # 3. Contra-réplica del Purista
    prompt_replica = f"""Eres el 'Agente Purista'. Lee la réplica del Agente Pragmático:
--- RÉPLICA PRAGMÁTICA ---
{critica_pragmatico}

Escribe una contra-réplica muy concisa (1 o 2 párrafos) defendiendo por qué el coste de un diseño desacoplado y mantenible a largo plazo supera con creces el ahorro inmediato de una solución rápida. Escribe en español de forma analítica y firme.
"""
    try:
        replica_purista = llm.invoke(prompt_replica).content.strip()
    except Exception as e:
        return f"Error durante la fase de réplica del Purista: {e}"

    # 4. Veredicto y síntesis de Jarvis
    prompt_veredicto = f"""Eres el moderador Jarvis. Has presenciado el debate entre el Agente Purista y el Agente Pragmático sobre el archivo '{file_path}':
- Debate:
Purista: {critica_purista}
Pragmático: {critica_pragmatico}
Purista (Contra-réplica): {replica_purista}

Genera un veredicto consolidado en español. Concilia ambas posturas y propón una solución equilibrada (Clean Code práctico sin sobreingeniería).
Finalmente, entrega el código refactorizado sugerido.
Devuelve estrictamente dos secciones bien delimitadas en tu texto:
VEREDICTO: (Tu resumen y explicación)
CODIGO REFACTORIZADO: (Solo el bloque de código refactorizado correspondiente)
"""
    try:
        veredicto_raw = llm.invoke(prompt_veredicto).content.strip()
    except Exception as e:
        return f"Error durante la fase de veredicto: {e}"

    # Separar veredicto y código refactorizado
    veredicto_txt = ""
    codigo_refac = ""
    
    if "CODIGO REFACTORIZADO:" in veredicto_raw:
        parts = veredicto_raw.split("CODIGO REFACTORIZADO:")
        veredicto_txt = parts[0].replace("VEREDICTO:", "").strip()
        codigo_refac = parts[1].strip()
        # Limpiar posibles delimitadores markdown del código de veredicto
        match_code = re.search(r"```[a-zA-Z]*\n([\s\S]*?)```", codigo_refac)
        if match_code:
            codigo_refac = match_code.group(1).strip()
    else:
        veredicto_txt = veredicto_raw
        codigo_refac = "# No se pudo extraer el código refactorizado de forma estructurada."

    # Escapar contenido HTML para evitar inyecciones e interferencias de renderizado
    critica_purista_esc = html.escape(critica_purista).replace("\n", "<br>")
    critica_pragmatico_esc = html.escape(critica_pragmatico).replace("\n", "<br>")
    replica_purista_esc = html.escape(replica_purista).replace("\n", "<br>")
    veredicto_txt_esc = html.escape(veredicto_txt).replace("\n", "<br>")
    codigo_refac_esc = html.escape(codigo_refac)

    # 5. Generar maquetación HTML cyberpunk
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body {{
      background: #020b14;
      color: #00d4ff;
      font-family: 'Consolas', 'Courier New', monospace;
      padding: 25px;
      margin: 0;
      line-height: 1.4rem;
    }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
      border: 1px solid rgba(0, 212, 255, 0.25);
      border-radius: 8px;
      padding: 25px;
      background: rgba(0, 25, 40, 0.7);
      box-shadow: 0 0 25px rgba(0, 212, 255, 0.15);
    }}
    .header {{
      text-align: center;
      border-bottom: 2px dashed rgba(0, 212, 255, 0.3);
      padding-bottom: 15px;
      margin-bottom: 30px;
    }}
    .header h1 {{
      font-size: 1.6rem;
      letter-spacing: 0.2rem;
      text-shadow: 0 0 10px #00d4ff;
      margin: 0 0 10px 0;
    }}
    .header .subtitle {{
      font-size: 0.8rem;
      color: #888888;
    }}
    .dialog-stream {{
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}
    .bubble {{
      display: flex;
      flex-direction: column;
      max-width: 85%;
      border-radius: 8px;
      padding: 14px 20px;
      box-sizing: border-box;
    }}
    .purista {{
      background: rgba(255, 0, 127, 0.05);
      border: 1px solid rgba(255, 0, 127, 0.35);
      color: #ffa6d2;
      align-self: flex-start;
      box-shadow: 0 0 12px rgba(255, 0, 127, 0.08);
    }}
    .purista .name {{
      color: #ff007f;
      font-weight: bold;
      font-size: 0.8rem;
      margin-bottom: 6px;
      text-shadow: 0 0 5px #ff007f;
      text-transform: uppercase;
      letter-spacing: 0.05rem;
    }}
    .pragmatico {{
      background: rgba(0, 243, 255, 0.05);
      border: 1px solid rgba(0, 243, 255, 0.35);
      color: #a6f5ff;
      align-self: flex-end;
      box-shadow: 0 0 12px rgba(0, 243, 255, 0.08);
    }}
    .pragmatico .name {{
      color: #00f3ff;
      font-weight: bold;
      font-size: 0.8rem;
      margin-bottom: 6px;
      text-shadow: 0 0 5px #00f3ff;
      text-transform: uppercase;
      letter-spacing: 0.05rem;
    }}
    .veredicto {{
      background: rgba(0, 255, 136, 0.05);
      border: 1px solid rgba(0, 255, 136, 0.3);
      color: #a6ffd2;
      margin-top: 20px;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 0 15px rgba(0, 255, 136, 0.12);
    }}
    .veredicto h2 {{
      font-size: 1.1rem;
      color: #00ff88;
      margin: 0 0 12px 0;
      text-shadow: 0 0 5px #00ff88;
      text-transform: uppercase;
      letter-spacing: 0.1rem;
      border-bottom: 1px dashed rgba(0, 255, 136, 0.3);
      padding-bottom: 6px;
    }}
    .code-section {{
      background: #000205;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 6px;
      padding: 15px;
      overflow-x: auto;
      margin-top: 15px;
      font-size: 0.8rem;
      color: #e6e6e6;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>TWIN-AGENT PEER REVIEW</h1>
      <div class="subtitle">Debate de Arquitectura para: {file_path}</div>
    </div>
    
    <div class="dialog-stream">
      <div class="bubble purista">
        <div class="name">🔍 AGENTE PURISTA (Clean Code & SOLID)</div>
        <div>{critica_purista_esc}</div>
      </div>
      
      <div class="bubble pragmatico">
        <div class="name">⚡ AGENTE PRAGMÁTICO (Simplicidad & YAGNI)</div>
        <div>{critica_pragmatico_esc}</div>
      </div>

      <div class="bubble purista">
        <div class="name">🔍 AGENTE PURISTA (Contra-Réplica)</div>
        <div>{replica_purista_esc}</div>
      </div>

      <div class="veredicto">
        <h2>🤖 VEREDICTO MODERADOR JARVIS</h2>
        <div>{veredicto_txt_esc}</div>
        <div style="margin-top: 18px; font-weight: bold; color: #00ff88; font-size: 0.85rem; text-transform: uppercase;">Propuesta Definitiva Refactorizada:</div>
        <pre class="code-section"><code>{codigo_refac_esc}</code></pre>
      </div>
    </div>
  </div>
</body>
</html>
"""
    
    # Escribir el reporte HTML
    try:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        PEER_REVIEW_HTML.write_text(html_content, encoding="utf-8")
    except Exception as e:
        return f"Error al persistir el HTML del debate: {e}"

    # Retornar bloque interactivo para que la GUI lo previsualice de inmediato
    markdown_response = f"""Señor, he realizado una revisión de arquitectura en formato de debate de pares con doble agente para **{file_path}**.

He compilado el debate completo en el artefacto interactivo. A continuación tienes el veredicto del moderador y la propuesta sugerida.

### 🤖 VEREDICTO DE AUDITORÍA
{veredicto_txt}

Aquí tienes la interfaz interactiva para revisar el debate cruzado entre el Agente Purista y el Agente Pragmático. Puedes copiar el código refactorizado desde el panel de la derecha:

```html
{html_content}
```
"""
    return markdown_response
