import sys
import os
import unittest
import json
import shutil
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.filesystem import write_workspace_file, WORKSPACE_ROOT
from core.pending_actions import PENDING_ACTION_FILE, clear_pending_action, execute_pending_action

class TestFilesystemSafety(unittest.TestCase):
    def setUp(self):
        clear_pending_action()
        # Limpiar backups de prueba
        self.backup_dir = Path(WORKSPACE_ROOT) / "logs" / "backup"
        if self.backup_dir.exists():
            try:
                shutil.rmtree(self.backup_dir)
            except Exception:
                pass
            
        # Crear un archivo de prueba no crítico
        self.test_file = "logs/test_safe_write_temp.txt"
        test_path = Path(WORKSPACE_ROOT) / self.test_file
        if test_path.exists():
            try:
                test_path.unlink()
            except Exception:
                pass
            
    def tearDown(self):
        clear_pending_action()
        test_path = Path(WORKSPACE_ROOT) / "logs/test_safe_write_temp.txt"
        if test_path.exists():
            try:
                test_path.unlink()
            except Exception:
                pass
        # Limpiar backups creados durante el test
        if self.backup_dir.exists():
            try:
                shutil.rmtree(self.backup_dir)
            except Exception:
                pass

    def test_non_critical_write_direct(self):
        # Escribir archivo no crítico
        res = write_workspace_file.invoke({"relative_path": self.test_file, "content": "Hello World"})
        self.assertIn("escrito", res)
        self.assertIn("test_safe_write_temp.txt", res)
        self.assertFalse(PENDING_ACTION_FILE.exists())
        
        # Verificar contenido
        path = Path(WORKSPACE_ROOT) / self.test_file
        self.assertTrue(path.exists())
        self.assertEqual(path.read_text(encoding="utf-8"), "Hello World")

    def test_backup_creation_on_overwrite(self):
        # Escribir primero
        write_workspace_file.invoke({"relative_path": self.test_file, "content": "Version 1"})
        
        # Sobrescribir
        res = write_workspace_file.invoke({"relative_path": self.test_file, "content": "Version 2"})
        self.assertIn("escrito", res)
        
        # Verificar que se creó backup
        self.assertTrue(self.backup_dir.exists())
        backups = list(self.backup_dir.glob("*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "Version 1")

    def test_critical_path_interception_and_confirm(self):
        critical_file = "core/test_filesystem_safety_mock.py"
        critical_path = Path(WORKSPACE_ROOT) / critical_file
        if critical_path.exists():
            try:
                critical_path.unlink()
            except Exception:
                pass
            
        try:
            # Intentar escribir
            res = write_workspace_file.invoke({"relative_path": critical_file, "content": "print('critical')"})
            
            # 1. Comprobar que intercepta y pide confirmación
            self.assertIn("requiere confirmación", res)
            self.assertTrue(PENDING_ACTION_FILE.exists())
            
            # 2. Comprobar que el archivo real no se creó todavía
            self.assertFalse(critical_path.exists())
            
            # 3. Confirmar acción
            confirm_res = execute_pending_action()
            self.assertIn("escrito", confirm_res)
            self.assertTrue(critical_path.exists())
            self.assertEqual(critical_path.read_text(encoding="utf-8"), "print('critical')")
            
        finally:
            if critical_path.exists():
                try:
                    critical_path.unlink()
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
