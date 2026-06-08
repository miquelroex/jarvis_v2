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

from core.smart_recruiter import (
    scan_workspace_tech_stack,
    search_web_jobs,
    generate_tailored_cover_letter,
    TECH_PROFILE_FILE,
    JOB_OFFERS_FILE,
    COVER_LETTERS_DIR,
    LOGS_DIR
)
from tools.recruiter_tool import (
    scan_workspace_tech_profile,
    search_job_offers,
    generate_job_cover_letter
)

class TestSmartRecruiter(unittest.TestCase):
    def setUp(self):
        # Crear directorio de logs temporales si no existe
        LOGS_DIR.mkdir(exist_ok=True)
        
        # Copias de seguridad
        self.profile_backup = None
        if TECH_PROFILE_FILE.exists():
            try:
                self.profile_backup = TECH_PROFILE_FILE.read_text(encoding="utf-8")
                TECH_PROFILE_FILE.unlink()
            except Exception:
                pass
                
        self.jobs_backup = None
        if JOB_OFFERS_FILE.exists():
            try:
                self.jobs_backup = JOB_OFFERS_FILE.read_text(encoding="utf-8")
                JOB_OFFERS_FILE.unlink()
            except Exception:
                pass
                
        # Crear un directorio temporal para simular un repositorio de código
        self.test_workspace_dir = Path(__file__).resolve().parent / "temp_workspace_for_recruiter_test"
        if self.test_workspace_dir.exists():
            shutil.rmtree(self.test_workspace_dir)
        self.test_workspace_dir.mkdir(parents=True, exist_ok=True)
        
        self.created_cover_letters = []

    def tearDown(self):
        # Limpiar directorio temporal de workspace
        if self.test_workspace_dir.exists():
            shutil.rmtree(self.test_workspace_dir)
            
        # Limpiar cartas de presentación creadas
        for file in self.created_cover_letters:
            if file.exists():
                try:
                    file.unlink()
                except Exception:
                    pass
                    
        # Eliminar carpeta de cartas si está vacía
        if COVER_LETTERS_DIR.exists() and not any(COVER_LETTERS_DIR.iterdir()):
            try:
                COVER_LETTERS_DIR.rmdir()
            except Exception:
                pass

        # Restaurar copias de seguridad
        if TECH_PROFILE_FILE.exists():
            try:
                TECH_PROFILE_FILE.unlink()
            except Exception:
                pass
        if self.profile_backup is not None:
            try:
                TECH_PROFILE_FILE.write_text(self.profile_backup, encoding="utf-8")
            except Exception:
                pass
                
        if JOB_OFFERS_FILE.exists():
            try:
                JOB_OFFERS_FILE.unlink()
            except Exception:
                pass
        if self.jobs_backup is not None:
            try:
                JOB_OFFERS_FILE.write_text(self.jobs_backup, encoding="utf-8")
            except Exception:
                pass

    def test_scan_workspace_tech_stack(self):
        # 1. Crear estructura simulada con archivos y dependencias
        # package.json
        package_json = self.test_workspace_dir / "package.json"
        package_json.write_text(json.dumps({
            "dependencies": {
                "react": "^18.2.0",
                "express": "^4.18.2"
            },
            "devDependencies": {
                "typescript": "^5.0.4"
            }
        }), encoding="utf-8")
        
        # requirements.txt
        requirements_txt = self.test_workspace_dir / "requirements.txt"
        requirements_txt.write_text("flask>=2.0.0\npytest==7.1.0\n# Comentario\n  \n", encoding="utf-8")
        
        # Unos archivos dummy de Python y JS
        (self.test_workspace_dir / "app.py").write_text("# app code", encoding="utf-8")
        (self.test_workspace_dir / "index.js").write_text("// js code", encoding="utf-8")
        (self.test_workspace_dir / "style.css").write_text("body {color: red;}", encoding="utf-8")
        
        # Ejecutar escaneo
        profile = scan_workspace_tech_stack(str(self.test_workspace_dir))
        
        # Verificar resultados
        self.assertIn("Python", profile["file_counts"])
        self.assertIn("JavaScript", profile["file_counts"])
        self.assertIn("CSS", profile["file_counts"])
        self.assertEqual(profile["file_counts"]["Python"], 1)
        self.assertEqual(profile["file_counts"]["JavaScript"], 1)
        
        self.assertIn("npm", profile["dependencies"])
        self.assertIn("pip", profile["dependencies"])
        self.assertIn("react", profile["dependencies"]["npm"])
        self.assertIn("typescript", profile["dependencies"]["npm"])
        self.assertIn("flask", profile["dependencies"]["pip"])
        
        self.assertIn("Python", profile["summary"])
        self.assertIn("JavaScript", profile["summary"])

    @patch("core.smart_recruiter.get_llm")
    @patch("tavily.TavilyClient")
    def test_search_web_jobs_tavily(self, mock_tavily_client, mock_get_llm):
        # Configurar variables de entorno mockeadas
        with patch.dict(os.environ, {"TAVILY_API_KEY": "fake-key"}):
            # Mock de respuesta Tavily
            mock_client_instance = MagicMock()
            mock_tavily_client.return_value = mock_client_instance
            mock_client_instance.search.return_value = {
                "results": [
                    {
                        "title": "Python Software Engineer - Stark Industries",
                        "url": "https://stark.com/jobs/1",
                        "content": "Looking for a Python Backend Developer. Key skills: Python, Flask, SQL."
                    }
                ]
            }
            
            # Mock del LLM
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            mock_response = MagicMock()
            mock_response.content = """```json
            [
              {
                "company": "Stark Industries",
                "title": "Python Software Engineer",
                "url": "https://stark.com/jobs/1",
                "requirements": ["Python", "Flask", "SQL"],
                "description": "Looking for a Python Backend Developer."
              }
            ]
            ```"""
            mock_llm.invoke.return_value = mock_response
            
            # Llamar a search_web_jobs
            jobs = search_web_jobs("Python", limit=1)
            
            # Verificar
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["company"], "Stark Industries")
            self.assertEqual(jobs[0]["title"], "Python Software Engineer")
            self.assertEqual(jobs[0]["requirements"], ["Python", "Flask", "SQL"])
            self.assertTrue(JOB_OFFERS_FILE.exists())

    @patch("core.smart_recruiter.get_llm")
    def test_generate_tailored_cover_letter(self, mock_get_llm):
        # 1. Preparar datos de perfil y ofertas simuladas
        profile_data = {
            "file_counts": {"Python": 5, "JavaScript": 2},
            "dependencies": {"pip": ["flask", "pygame"], "npm": ["react"]},
            "summary": "Predominates Python and JavaScript."
        }
        TECH_PROFILE_FILE.write_text(json.dumps(profile_data), encoding="utf-8")
        
        job_data = [
            {
                "company": "Oscorp Industries",
                "title": "Junior Python Dev",
                "url": "https://oscorp.com/careers/2",
                "requirements": ["Python", "Flask"],
                "description": "Develop python backend services."
            }
        ]
        JOB_OFFERS_FILE.write_text(json.dumps(job_data), encoding="utf-8")
        
        # 2. Mock del LLM para retornar la carta
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_response = MagicMock()
        mock_response.content = "# Carta de Presentación\nEstimado equipo de Oscorp..."
        mock_llm.invoke.return_value = mock_response
        
        # 3. Generar la carta
        res = generate_tailored_cover_letter(0)
        
        # 4. Verificar que se ha creado la carta en disco y contiene el texto
        self.assertIn("Carta de presentación generada con éxito", res)
        
        letter_path = COVER_LETTERS_DIR / "carta_oscorpindustries_juniorpythondev.md"
        self.created_cover_letters.append(letter_path)
        self.assertTrue(letter_path.exists())
        self.assertIn("Estimado equipo de Oscorp", letter_path.read_text(encoding="utf-8"))

    def test_recruiter_tools_invocation(self):
        # Comprobar que las herramientas de recruiter_tool llaman a las funciones del core
        # y devuelven respuestas formateadas correctamente en Markdown.
        # Mock de scan_workspace_tech_stack
        with patch("tools.recruiter_tool.scan_workspace_tech_stack") as mock_scan:
            mock_scan.return_value = {
                "summary": "Stack de prueba.",
                "file_counts": {"Rust": 4},
                "dependencies": {"cargo": ["serde"]}
            }
            report = scan_workspace_tech_profile.invoke({})
            self.assertIn("PERFIL TECNOLÓGICO DEL REPOSITORIO", report)
            self.assertIn("Rust", report)
            self.assertIn("serde", report)

        # Mock de search_web_jobs
        with patch("tools.recruiter_tool.search_web_jobs") as mock_search:
            mock_search.return_value = [
                {
                    "company": "Wayne Enterprises",
                    "title": "Rust Developer",
                    "url": "https://wayne.com/1",
                    "requirements": ["Rust", "Actix-web"],
                    "description": "Build systems."
                }
            ]
            report = search_job_offers.invoke({"query": "Rust", "limit": 1})
            self.assertIn("OFERTAS DE EMPLEO DETECTADAS PARA", report)
            self.assertIn("Wayne Enterprises", report)
            self.assertIn("Rust Developer", report)

        # Mock de generate_tailored_cover_letter
        with patch("tools.recruiter_tool.generate_tailored_cover_letter") as mock_gen:
            mock_gen.return_value = "🟢 Carta generada exitosamente en Markdown"
            report = generate_job_cover_letter.invoke({"job_index": 0})
            self.assertIn("Carta generada exitosamente", report)

if __name__ == "__main__":
    unittest.main()
