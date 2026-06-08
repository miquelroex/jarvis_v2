import os
import json
import re
import socket
import logging
import requests
import time
from pathlib import Path
from core.llm_factory import get_llm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
SANDBOX_FILE = LOGS_DIR / "api_sandbox.html"

def scan_project_endpoints(workspace_path: str = None) -> list[dict]:
    """
    Escanea el espacio de trabajo de forma estática buscando definiciones de endpoints
    en proyectos de Python (FastAPI/Flask) y Node.js (Express).
    """
    if workspace_path is None:
        root = PROJECT_ROOT
    else:
        root = Path(workspace_path)
        
    endpoints = []
    
    exclude_dirs = {
        '.venv', 'venv', 'node_modules', '.git', 'logs', 'cover_letters',
        '__pycache__', 'dist', 'build', '.gemini', 'brain', '.idea', '.vscode'
    }
    
    # Expresiones regulares para detectar rutas
    # 1. FastAPI/Flask: @app.get('/path'), @router.post("/path"), @app.route("/path", methods=["POST"])
    py_route_pattern = re.compile(
        r'@(?:app|router|api)\.(get|post|put|delete|patch|route)\(\s*["\']([^"\']+)["\']'
    )
    # 2. Express: app.get('/path'), router.post("/path")
    js_route_pattern = re.compile(
        r'(?:app|router|route)\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']'
    )
    
    for r_dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            p = Path(r_dir) / file
            if file.endswith(".py"):
                try:
                    content = p.read_text(encoding="utf-8")
                    for match in py_route_pattern.finditer(content):
                        decorator_type = match.group(1)
                        path = match.group(2)
                        
                        # Determinar método
                        method = "GET"
                        if decorator_type != "route":
                            method = decorator_type.upper()
                        else:
                            start_idx = match.start()
                            line_end = content.find("\n", start_idx)
                            line_text = content[start_idx:line_end]
                            methods_match = re.search(r'methods\s*=\s*\[\s*["\']([^"\']+)["\']', line_text)
                            if methods_match:
                                method = methods_match.group(1).upper()
                                
                        endpoints.append({
                            "method": method,
                            "path": path,
                            "file": p.relative_to(root).as_posix(),
                            "framework": "FastAPI/Flask"
                        })
                except Exception:
                    pass
            elif file.endswith((".js", ".ts", ".tsx", ".jsx")):
                try:
                    content = p.read_text(encoding="utf-8")
                    for match in js_route_pattern.finditer(content):
                        method = match.group(1).upper()
                        path = match.group(2)
                        
                        endpoints.append({
                            "method": method,
                            "path": path,
                            "file": p.relative_to(root).as_posix(),
                            "framework": "Express"
                        })
                except Exception:
                    pass
                    
    return endpoints

def detect_active_dev_port() -> int:
    """Escanea puertos comunes localmente para identificar dónde está corriendo el servidor de desarrollo."""
    ports_to_check = [5000, 8000, 3000, 8080, 5001]
    for port in ports_to_check:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            result = s.connect_ex(('127.0.0.1', port))
            if result == 0:
                return port
    return 5000  # Fallback a 5000 si no se detecta ninguno activo

def test_local_endpoints(endpoints: list[dict], port: int) -> list[dict]:
    """Prueba las llamadas HTTP en local para verificar si responden correctamente."""
    results = []
    base_url = f"http://127.0.0.1:{port}"
    for ep in endpoints:
        method = ep["method"]
        path = ep["path"]
        
        # Ignorar rutas con parámetros dinámicos para pruebas automatizadas básicas
        if "{" in path or ":" in path or "<" in path:
            results.append({
                **ep,
                "status": "Ignorado (Ruta variable)",
                "latency_ms": 0,
                "online": True
            })
            continue
            
        test_url = base_url + path
        try:
            start_time = time.time()
            if method == "GET":
                r = requests.get(test_url, timeout=1.0)
            elif method == "POST":
                r = requests.post(test_url, json={}, timeout=1.0)
            elif method == "PUT":
                r = requests.put(test_url, json={}, timeout=1.0)
            elif method == "DELETE":
                r = requests.delete(test_url, timeout=1.0)
            else:
                r = requests.request(method, test_url, timeout=1.0)
                
            latency = int((time.time() - start_time) * 1000)
            results.append({
                **ep,
                "status": r.status_code,
                "latency_ms": latency,
                "online": True
            })
        except requests.RequestException:
            results.append({
                **ep,
                "status": "Offline",
                "latency_ms": 0,
                "online": False
            })
            
    return results

def generate_sandbox_html(endpoints: list[dict], target_port: int) -> Path:
    """Compila el playground HTML interactivo de APIs con los endpoints escaneados."""
    endpoints_json = json.dumps(endpoints, indent=2)
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Jarvis API Sandbox</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #080c14;
            --card-bg: rgba(15, 23, 42, 0.6);
            --border-color: rgba(0, 212, 255, 0.2);
            --cyan: #00d4ff;
            --pink: #ff3344;
            --green: #00ff88;
            --orange: #ff9f1c;
            --text-color: #cbd5e1;
            --text-muted: #64748b;
        }}
        
        body {{
            font-family: 'Outfit', sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 15px;
            overflow-x: hidden;
            background-image: 
                radial-gradient(at 0% 0%, rgba(0, 212, 255, 0.08) 0, transparent 50%),
                radial-gradient(at 100% 100%, rgba(255, 51, 68, 0.08) 0, transparent 50%);
            background-attachment: fixed;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 12px;
            margin-bottom: 15px;
        }}
        
        .header h1 {{
            font-size: 1.3rem;
            font-weight: 800;
            margin: 0;
            letter-spacing: 2px;
            color: #ffffff;
            text-shadow: 0 0 10px rgba(0, 212, 255, 0.3);
        }}
        
        .header h1 span {{
            color: var(--cyan);
        }}
        
        .config-bar {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        
        .config-bar label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }}
        
        .config-bar input {{
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: #ffffff;
            padding: 4px 8px;
            font-family: 'Fira Code', monospace;
            font-size: 0.8rem;
            outline: none;
            transition: border-color 0.2s;
        }}
        
        .config-bar input:focus {{
            border-color: var(--cyan);
        }}
        
        .container {{
            display: flex;
            gap: 15px;
            height: calc(100vh - 80px);
        }}
        
        .sidebar {{
            flex: 1;
            min-width: 250px;
            max-width: 320px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px;
            overflow-y: auto;
            backdrop-filter: blur(10px);
        }}
        
        .sidebar-title {{
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
            padding-left: 5px;
        }}
        
        .endpoint-list {{
            list-style: none;
            padding: 0;
            margin: 0;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        
        .endpoint-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px;
            border-radius: 5px;
            cursor: pointer;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid transparent;
            transition: all 0.2s;
        }}
        
        .endpoint-item:hover {{
            background: rgba(0, 212, 255, 0.04);
            border-color: rgba(0, 212, 255, 0.1);
        }}
        
        .endpoint-item.active {{
            background: rgba(0, 212, 255, 0.08);
            border-color: var(--cyan);
            box-shadow: 0 0 10px rgba(0, 212, 255, 0.1);
        }}
        
        .method {{
            font-family: 'Fira Code', monospace;
            font-size: 0.65rem;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
            min-width: 50px;
            text-align: center;
        }}
        
        .method.GET {{ background: rgba(0, 255, 136, 0.1); color: var(--green); border: 1px solid rgba(0, 255, 136, 0.2); }}
        .method.POST {{ background: rgba(0, 212, 255, 0.1); color: var(--cyan); border: 1px solid rgba(0, 212, 255, 0.2); }}
        .method.PUT {{ background: rgba(255, 159, 28, 0.1); color: var(--orange); border: 1px solid rgba(255, 159, 28, 0.2); }}
        .method.DELETE {{ background: rgba(255, 51, 68, 0.1); color: var(--pink); border: 1px solid rgba(255, 51, 68, 0.2); }}
        
        .path {{
            font-family: 'Fira Code', monospace;
            font-size: 0.8rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: #e2e8f0;
        }}
        
        .main-pane {{
            flex: 2.5;
            display: flex;
            flex-direction: column;
            gap: 15px;
            height: 100%;
        }}
        
        .section-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 15px;
            backdrop-filter: blur(10px);
        }}
        
        .pane-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        
        .pane-title {{
            font-size: 1rem;
            font-weight: 600;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .pane-source {{
            font-size: 0.7rem;
            color: var(--text-muted);
            font-family: 'Fira Code', monospace;
        }}
        
        .input-group {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 12px;
        }}
        
        .input-group label {{
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
        }}
        
        .input-group input, .input-group textarea {{
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: #ffffff;
            padding: 8px;
            outline: none;
            font-family: 'Fira Code', monospace;
            font-size: 0.85rem;
            transition: border-color 0.2s;
        }}
        
        .input-group input:focus, .input-group textarea:focus {{
            border-color: var(--cyan);
        }}
        
        .input-group textarea {{
            resize: vertical;
            min-height: 80px;
        }}
        
        .btn-send {{
            background: linear-gradient(135deg, var(--cyan), #00a4cc);
            border: none;
            border-radius: 6px;
            color: #0f172a;
            font-family: 'Outfit', sans-serif;
            font-size: 0.9rem;
            font-weight: bold;
            padding: 10px 20px;
            cursor: pointer;
            outline: none;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: 0 0 15px rgba(0, 212, 255, 0.3);
            transition: all 0.2s;
        }}
        
        .btn-send:hover {{
            transform: translateY(-1px);
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
        }}
        
        .btn-send:active {{
            transform: translateY(1px);
        }}
        
        .response-section {{
            flex: 1;
            display: flex;
            flex-direction: column;
            min-height: 200px;
        }}
        
        .response-meta {{
            display: flex;
            gap: 15px;
            font-size: 0.8rem;
            margin-bottom: 10px;
            color: var(--text-muted);
        }}
        
        .meta-badge {{
            background: rgba(255, 255, 255, 0.05);
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid var(--border-color);
        }}
        
        .meta-badge span {{
            font-weight: bold;
            color: #ffffff;
        }}
        
        .meta-badge.status-2xx span {{ color: var(--green); }}
        .meta-badge.status-4xx span, .meta-badge.status-5xx span {{ color: var(--pink); }}
        
        .console-box {{
            flex: 1;
            background: #020617;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 12px;
            font-family: 'Fira Code', monospace;
            font-size: 0.8rem;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
            color: var(--cyan);
        }}
        
        .placeholder-text {{
            color: var(--text-muted);
            text-align: center;
            padding-top: 50px;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>J.A.R.V.I.S. <span>API PLAYGROUND</span></h1>
        <div class="config-bar">
            <label for="base-url-input">Base URL</label>
            <input type="text" id="base-url-input" value="http://127.0.0.1:{target_port}">
            <label for="auth-input">Auth Token</label>
            <input type="text" id="auth-input" placeholder="Bearer token...">
        </div>
    </div>
    
    <div class="container">
        <div class="sidebar">
            <div class="sidebar-title">Rutas Detectadas ({len(endpoints)})</div>
            <ul class="endpoint-list" id="endpoint-list"></ul>
        </div>
        
        <div class="main-pane">
            <div class="section-card" id="editor-card">
                <div class="placeholder-text" id="placeholder-msg">Seleccione un endpoint en la barra lateral para comenzar las pruebas.</div>
                
                <div id="editor-content" style="display: none;">
                    <div class="pane-header">
                        <div class="pane-title" id="pane-title">
                            <span class="method" id="pane-method">GET</span>
                            <span id="pane-path">/api/route</span>
                        </div>
                        <span class="pane-source" id="pane-source">archivo.py</span>
                    </div>
                    
                    <div class="input-group" id="url-params-group">
                        <label>URL / Query Params (formato clave=valor, uno por línea)</label>
                        <textarea id="query-params-input" placeholder="id=1&#10;name=test"></textarea>
                    </div>
                    
                    <div class="input-group" id="req-body-group" style="display: none;">
                        <label>Cuerpo de la Petición (Request Body - JSON)</label>
                        <textarea id="req-body-input" rows="5" placeholder='{{\n  "key": "value"\n}}'></textarea>
                    </div>
                    
                    <button class="btn-send" id="btn-send">
                        ⚡ ENVIAR PETICIÓN
                    </button>
                </div>
            </div>
            
            <div class="section-card response-section">
                <div class="pane-title" style="margin-bottom:10px;">RESPUESTA DEL SERVIDOR</div>
                <div class="response-meta" id="response-meta" style="display: none;">
                    <div class="meta-badge" id="status-badge">Status: <span id="res-status">200</span></div>
                    <div class="meta-badge">Tiempo: <span id="res-time">0 ms</span></div>
                </div>
                <div class="console-box" id="console-box">Esperando petición...</div>
            </div>
        </div>
    </div>

    <script>
        const endpoints = {endpoints_json};
        let activeEndpointIndex = -1;
        
        const listEl = document.getElementById('endpoint-list');
        const placeholderEl = document.getElementById('placeholder-msg');
        const editorContentEl = document.getElementById('editor-content');
        const paneMethodEl = document.getElementById('pane-method');
        const panePathEl = document.getElementById('pane-path');
        const paneSourceEl = document.getElementById('pane-source');
        const queryParamsInputEl = document.getElementById('query-params-input');
        const reqBodyGroupEl = document.getElementById('req-body-group');
        const reqBodyInputEl = document.getElementById('req-body-input');
        const btnSendEl = document.getElementById('btn-send');
        const baseUrlInputEl = document.getElementById('base-url-input');
        const authInputEl = document.getElementById('auth-input');
        const consoleBoxEl = document.getElementById('console-box');
        const responseMetaEl = document.getElementById('response-meta');
        const statusBadgeEl = document.getElementById('status-badge');
        const resStatusEl = document.getElementById('res-status');
        const resTimeEl = document.getElementById('res-time');

        endpoints.forEach((ep, index) => {{
            const li = document.createElement('li');
            li.className = 'endpoint-item';
            li.innerHTML = `
                <span class="method ${{ep.method}}">${{ep.method}}</span>
                <span class="path">${{ep.path}}</span>
            `;
            li.addEventListener('click', () => selectEndpoint(index, li));
            listEl.appendChild(li);
        }});

        function selectEndpoint(index, element) {{
            document.querySelectorAll('.endpoint-item').forEach(el => el.classList.remove('active'));
            element.classList.add('active');
            
            activeEndpointIndex = index;
            const ep = endpoints[index];
            
            placeholderEl.style.display = 'none';
            editorContentEl.style.display = 'block';
            
            paneMethodEl.className = `method ${{ep.method}}`;
            paneMethodEl.textContent = ep.method;
            panePathEl.textContent = ep.path;
            paneSourceEl.textContent = `${{ep.framework}} | ${{ep.file}}`;
            
            queryParamsInputEl.value = '';
            reqBodyInputEl.value = '';
            
            if (ep.method === 'GET' || ep.method === 'DELETE') {{
                reqBodyGroupEl.style.display = 'none';
            }} else {{
                reqBodyGroupEl.style.display = 'flex';
                reqBodyInputEl.value = '{{\\n  \\n}}';
            }}
            
            consoleBoxEl.textContent = 'Listo para enviar petición...';
            consoleBoxEl.style.color = 'var(--cyan)';
            responseMetaEl.style.display = 'none';
        }}

        btnSendEl.addEventListener('click', async () => {{
            if (activeEndpointIndex === -1) return;
            
            const ep = endpoints[activeEndpointIndex];
            let baseUrl = baseUrlInputEl.value.trim();
            if (baseUrl.endsWith('/')) baseUrl = baseUrl.slice(0, -1);
            
            let path = ep.path;
            
            const queryParamsRaw = queryParamsInputEl.value.split('\\n');
            const queryParamsList = [];
            
            queryParamsRaw.forEach(line => {{
                const parts = line.split('=');
                if (parts.length >= 2) {{
                    const key = parts[0].trim();
                    const val = parts.slice(1).join('=').trim();
                    if (key) queryParamsList.push(`${{encodeURIComponent(key)}}=${{encodeURIComponent(val)}}`);
                }}
            }});
            
            if (queryParamsList.length > 0) {{
                path += (path.includes('?') ? '&' : '?') + queryParamsList.join('&');
            }}
            
            const fullUrl = baseUrl + path;
            
            const headers = {{}};
            const token = authInputEl.value.trim();
            if (token) {{
                headers['Authorization'] = token.startsWith('Bearer ') ? token : `Bearer ${{token}}`;
            }}
            
            const options = {{
                method: ep.method,
                headers: headers
            }};
            
            if (ep.method !== 'GET' && ep.method !== 'DELETE') {{
                const bodyText = reqBodyInputEl.value.trim();
                if (bodyText) {{
                    try {{
                        JSON.parse(bodyText);
                        options.body = bodyText;
                        headers['Content-Type'] = 'application/json';
                    }} catch(e) {{
                        consoleBoxEl.textContent = `[ERROR] El cuerpo de la petición no es un JSON válido:\\n${{e.message}}`;
                        consoleBoxEl.style.color = 'var(--pink)';
                        return;
                    }}
                }}
            }}
            
            consoleBoxEl.textContent = 'Enviando petición a ' + fullUrl + '...';
            consoleBoxEl.style.color = 'var(--cyan)';
            responseMetaEl.style.display = 'none';
            btnSendEl.disabled = true;
            btnSendEl.textContent = 'ENVIANDO...';

            const startTime = performance.now();
            try {{
                const res = await fetch(fullUrl, options);
                const duration = Math.round(performance.now() - startTime);
                
                const text = await res.text();
                
                responseMetaEl.style.display = 'flex';
                resStatusEl.textContent = res.status;
                resTimeEl.textContent = `${{duration}} ms`;
                
                statusBadgeEl.className = 'meta-badge';
                if (res.status >= 200 && res.status < 300) {{
                    statusBadgeEl.classList.add('status-2xx');
                    consoleBoxEl.style.color = 'var(--green)';
                }} else if (res.status >= 400) {{
                    statusBadgeEl.classList.add('status-4xx');
                    consoleBoxEl.style.color = 'var(--pink)';
                }} else {{
                    consoleBoxEl.style.color = 'var(--orange)';
                }}
                
                try {{
                    const parsedJson = JSON.parse(text);
                    consoleBoxEl.textContent = JSON.stringify(parsedJson, null, 2);
                }} catch(e) {{
                    consoleBoxEl.textContent = text || `[Respuesta vacía con código de estado ${{res.status}}]`;
                }}
                
            }} catch(err) {{
                const duration = Math.round(performance.now() - startTime);
                consoleBoxEl.textContent = `[ERROR DE CONEXIÓN] No se pudo conectar al servidor:\\n${{err.message}}\\n\\nVerifica que:\\n1. El servidor esté corriendo localmente en el puerto indicado.\\n2. Las políticas CORS de tu servidor local permitan peticiones desde esta interfaz.`;
                consoleBoxEl.style.color = 'var(--pink)';
            }} finally {{
                btnSendEl.disabled = false;
                btnSendEl.textContent = '⚡ ENVIAR PETICIÓN';
            }}
        }});
    </script>
</body>
</html>
"""
    try:
        LOGS_DIR.mkdir(exist_ok=True)
        SANDBOX_FILE.write_text(html, encoding="utf-8")
        return SANDBOX_FILE
    except Exception as e:
        logging.error(f"[API Sandbox] Error writing sandbox HTML: {e}")
        return None
