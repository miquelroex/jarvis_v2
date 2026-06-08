import os
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.privacy_sentinel import (
    scan_workspace_privacy,
    load_ignored_hashes,
    save_ignored_hash,
    IGNORED_FILE,
    is_path_ignored,
    is_false_positive
)
from tools.privacy_tool import run_privacy_scan

class TestPrivacySentinel(unittest.TestCase):
    
    def setUp(self):
        # Asegurar un estado limpio para IGNORED_FILE
        self.ignored_backup = None
        if IGNORED_FILE.exists():
            try:
                self.ignored_backup = IGNORED_FILE.read_text(encoding="utf-8")
                IGNORED_FILE.unlink()
            except Exception:
                pass
                
        # Crear carpeta de test temporal fuera de logs/ para evitar ignorado por defecto
        self.test_dir = Path(__file__).resolve().parent.parent / "privacy_test_temp"
        self.test_dir.mkdir(exist_ok=True)
        
    def tearDown(self):
        # Restaurar IGNORED_FILE
        if IGNORED_FILE.exists():
            try:
                IGNORED_FILE.unlink()
            except Exception:
                pass
        if self.ignored_backup is not None:
            try:
                IGNORED_FILE.write_text(self.ignored_backup, encoding="utf-8")
            except Exception:
                pass
                
        # Eliminar carpeta temporal y archivos de test
        if self.test_dir.exists():
            for f in self.test_dir.iterdir():
                try:
                    f.unlink()
                except Exception:
                    pass
            try:
                self.test_dir.rmdir()
            except Exception:
                pass

    def test_regex_matching_keys(self):
        # Crear archivos de test con llaves de longitud exacta
        file_openai = self.test_dir / "test_openai.py"
        file_openai.write_text(f"openai_key = 'sk-proj-{'a'*48}'", encoding="utf-8")
        
        file_google = self.test_dir / "test_google.js"
        file_google.write_text(f"const KEY = \"AIzaSy{'a'*33}\";", encoding="utf-8")
        
        file_tavily = self.test_dir / "test_tavily.py"
        file_tavily.write_text(f"tavily_api_key = \"tvly-{'a'*32}\"", encoding="utf-8")
        
        file_telegram = self.test_dir / "test_telegram.py"
        file_telegram.write_text("token = '777888999:abcdefghijklmnopqrstuvwxyzABCDEFGHIJK1234'", encoding="utf-8")
        
        # Ejecutar escaneo apuntando a nuestra carpeta temporal de prueba
        with patch("core.privacy_sentinel.PROJECT_ROOT", self.test_dir):
            findings = scan_workspace_privacy()
            
        types = {f["type"] for f in findings}
        self.assertIn("OpenAI API Key", types)
        self.assertIn("Google API Key", types)
        self.assertIn("Tavily API Key", types)
        self.assertIn("Telegram Bot Token", types)

    def test_false_positive_filtering(self):
        self.assertTrue(is_false_positive("OpenAI API Key", "sk-your_openai_api_key_here_some_long_key_abcdef"))
        self.assertTrue(is_false_positive("Hardcoded Password / Secret", "short"))
        self.assertFalse(is_false_positive("OpenAI API Key", f"sk-proj-{'a'*48}"))

    def test_ignore_mechanism(self):
        # Simular un hallazgo de longitud exacta de 64 caracteres de OpenRouter y guardarlo como ignorado
        secret_val = f"sk-or-v1-{'a'*64}"
        
        file_openrouter = self.test_dir / "test_or.py"
        file_openrouter.write_text(f"key = '{secret_val}'", encoding="utf-8")
        
        # Con el archivo no ignorado
        with patch("core.privacy_sentinel.PROJECT_ROOT", self.test_dir):
            findings = scan_workspace_privacy()
            self.assertEqual(len(findings), 1)
            
            # Guardar hash de ignorado
            save_ignored_hash(findings[0]["hash"])
            
            # Con el archivo ahora ignorado
            findings_after = scan_workspace_privacy()
            self.assertEqual(len(findings_after), 0)

    def test_is_path_ignored(self):
        gitignore_patterns = ["*.log", "temp/", "build/"]
        
        # Rutas por defecto ignoradas
        import core.privacy_sentinel
        base = core.privacy_sentinel.PROJECT_ROOT.as_posix()

        # Rutas por defecto ignoradas
        self.assertTrue(is_path_ignored(f"{base}/.venv/lib/site-packages/pkg.py", gitignore_patterns))
        self.assertTrue(is_path_ignored(f"{base}/logs/model_usage.log", gitignore_patterns))
        self.assertTrue(is_path_ignored(f"{base}/.env", gitignore_patterns))
        
        # Rutas de gitignore
        self.assertTrue(is_path_ignored(f"{base}/temp/debug.txt", gitignore_patterns))
        self.assertTrue(is_path_ignored(f"{base}/build/main.exe", gitignore_patterns))
        self.assertTrue(is_path_ignored(f"{base}/debug.log", gitignore_patterns))
        
        # Ruta no ignorada
        self.assertFalse(is_path_ignored(f"{base}/core/main.py", gitignore_patterns))

    @patch("core.privacy_sentinel.scan_workspace_privacy")
    def test_privacy_tool_outputs(self, mock_scan):
        # 1. Caso sin hallazgos
        mock_scan.return_value = []
        res = run_privacy_scan.invoke({})
        self.assertIn("no he detectado", res)
        
        # 2. Caso con hallazgos
        mock_scan.return_value = [{
            "file": "main.py",
            "line": 10,
            "type": "OpenAI API Key",
            "snippet": "sk-pr...bcde",
            "hash": "1234abcd"
        }]
        res_vuln = run_privacy_scan.invoke({})
        self.assertIn("ALERTA DE SEGURIDAD", res_vuln)
        self.assertIn("main.py", res_vuln)
        self.assertIn("OpenAI API Key", res_vuln)

if __name__ == '__main__':
    unittest.main()
