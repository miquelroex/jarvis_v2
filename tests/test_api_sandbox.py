import sys
import os
import unittest
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.api_sandbox import (
    scan_project_endpoints,
    detect_active_dev_port,
    test_local_endpoints,
    generate_sandbox_html,
    SANDBOX_FILE,
    LOGS_DIR
)
from tools.api_sandbox_tool import scan_and_generate_api_sandbox, run_api_health_check

class TestApiSandbox(unittest.TestCase):
    def setUp(self):
        # Asegurar directorio logs
        LOGS_DIR.mkdir(exist_ok=True)
        
        # Copia de seguridad del sandbox real si existe
        self.sandbox_backup = None
        if SANDBOX_FILE.exists():
            try:
                self.sandbox_backup = SANDBOX_FILE.read_text(encoding="utf-8")
                SANDBOX_FILE.unlink()
            except Exception:
                pass
                
        # Crear un directorio temporal para código mock
        self.test_workspace_dir = Path(__file__).resolve().parent / "temp_workspace_for_sandbox_test"
        if self.test_workspace_dir.exists():
            shutil.rmtree(self.test_workspace_dir)
        self.test_workspace_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Limpiar directorio temporal
        if self.test_workspace_dir.exists():
            shutil.rmtree(self.test_workspace_dir)
            
        # Restaurar copia de seguridad
        if SANDBOX_FILE.exists():
            try:
                SANDBOX_FILE.unlink()
            except Exception:
                pass
        if self.sandbox_backup is not None:
            try:
                SANDBOX_FILE.write_text(self.sandbox_backup, encoding="utf-8")
            except Exception:
                pass

    def test_scan_project_endpoints(self):
        # 1. Crear un script de Python con FastAPI/Flask routes
        app_py = self.test_workspace_dir / "app.py"
        app_py.write_text(
            "@app.get('/users')\n"
            "def get_users(): pass\n\n"
            "@router.post(\"/items\")\n"
            "def post_items(): pass\n\n"
            "@app.route('/legacy', methods=['POST'])\n"
            "def legacy(): pass\n",
            encoding="utf-8"
        )
        
        # 2. Crear un script de Node.js con Express routes
        routes_js = self.test_workspace_dir / "routes.js"
        routes_js.write_text(
            "app.get('/api/v1/info', (req, res) => {})\n"
            "router.put('/api/v1/update', auth, (req, res) => {})\n",
            encoding="utf-8"
        )
        
        # Escanear
        endpoints = scan_project_endpoints(str(self.test_workspace_dir))
        
        # Verificar FastAPI/Flask
        py_endpoints = [ep for ep in endpoints if ep["framework"] == "FastAPI/Flask"]
        self.assertEqual(len(py_endpoints), 3)
        self.assertTrue(any(ep["path"] == "/users" and ep["method"] == "GET" for ep in py_endpoints))
        self.assertTrue(any(ep["path"] == "/items" and ep["method"] == "POST" for ep in py_endpoints))
        self.assertTrue(any(ep["path"] == "/legacy" and ep["method"] == "POST" for ep in py_endpoints))
        
        # Verificar Express
        js_endpoints = [ep for ep in endpoints if ep["framework"] == "Express"]
        self.assertEqual(len(js_endpoints), 2)
        self.assertTrue(any(ep["path"] == "/api/v1/info" and ep["method"] == "GET" for ep in js_endpoints))
        self.assertTrue(any(ep["path"] == "/api/v1/update" and ep["method"] == "PUT" for ep in js_endpoints))

    def test_generate_sandbox_html(self):
        endpoints = [
            {"method": "GET", "path": "/users", "file": "app.py", "framework": "FastAPI/Flask"},
            {"method": "POST", "path": "/items", "file": "app.py", "framework": "FastAPI/Flask"}
        ]
        
        sandbox_path = generate_sandbox_html(endpoints, 8000)
        self.assertIsNotNone(sandbox_path)
        self.assertTrue(sandbox_path.exists())
        
        content = sandbox_path.read_text(encoding="utf-8")
        self.assertIn("J.A.R.V.I.S. <span>API PLAYGROUND</span>", content)
        self.assertIn("/users", content)
        self.assertIn("/items", content)
        self.assertIn("http://127.0.0.1:8000", content)

    @patch("requests.get")
    @patch("requests.post")
    def test_test_local_endpoints(self, mock_post, mock_get):
        endpoints = [
            {"method": "GET", "path": "/users", "file": "app.py", "framework": "FastAPI/Flask"},
            {"method": "POST", "path": "/items", "file": "app.py", "framework": "FastAPI/Flask"},
            {"method": "GET", "path": "/users/{id}", "file": "app.py", "framework": "FastAPI/Flask"} # Dinámico
        ]
        
        # Mock de las respuestas HTTP
        mock_res_get = MagicMock()
        mock_res_get.status_code = 200
        mock_get.return_value = mock_res_get
        
        mock_res_post = MagicMock()
        mock_res_post.status_code = 201
        mock_post.return_value = mock_res_post
        
        results = test_local_endpoints(endpoints, 5000)
        
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["status"], 200)
        self.assertEqual(results[1]["status"], 201)
        self.assertEqual(results[2]["status"], "Ignorado (Ruta variable)")
        self.assertTrue(results[0]["online"])
        self.assertTrue(results[1]["online"])

    def test_tools_invocation(self):
        # Mockear las funciones core internas para testear las langchain tools de forma aislada
        with patch("tools.api_sandbox_tool.scan_project_endpoints") as mock_scan, \
             patch("tools.api_sandbox_tool.generate_sandbox_html") as mock_gen, \
             patch("tools.api_sandbox_tool.test_local_endpoints") as mock_test:
             
            mock_scan.return_value = [
                {"method": "GET", "path": "/users", "file": "app.py", "framework": "FastAPI/Flask"}
            ]
            mock_gen.return_value = SANDBOX_FILE
            
            # Escribir sandbox temporal para el tool read_text
            SANDBOX_FILE.write_text("<html>Playground</html>", encoding="utf-8")
            
            # 1. Probar scan_and_generate_api_sandbox
            res = scan_and_generate_api_sandbox.invoke({"port": 5000})
            self.assertIn("API Sandbox generado con éxito", res)
            self.assertIn("<html>Playground</html>", res)
            
            # 2. Probar run_api_health_check
            mock_test.return_value = [
                {
                    "method": "GET",
                    "path": "/users",
                    "file": "app.py",
                    "framework": "FastAPI/Flask",
                    "status": 200,
                    "latency_ms": 15,
                    "online": True
                }
            ]
            health_res = run_api_health_check.invoke({"port": 5000})
            self.assertIn("REPORTE DE SALUD DE API LOCAL", health_res)
            self.assertIn("/users", health_res)
            self.assertIn("ONLINE", health_res)

if __name__ == "__main__":
    unittest.main()
