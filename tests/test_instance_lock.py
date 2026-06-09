"""Tests para el módulo de bloqueo de instancia única (core/instance_lock.py)."""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Asegurar que el workspace está en el path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.instance_lock import (
    acquire_instance_lock,
    release_instance_lock,
    _is_jarvis_process,
    LOCK_FILE,
)


class TestInstanceLock(unittest.TestCase):
    """Tests de adquisición, detección de duplicado y limpieza del lock."""

    def setUp(self):
        """Limpieza antes de cada test."""
        import core.instance_lock as mod
        mod._lock_acquired = False
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()

    def tearDown(self):
        """Limpieza después de cada test."""
        import core.instance_lock as mod
        mod._lock_acquired = False
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()

    def test_acquire_creates_lock_file(self):
        """acquire_instance_lock debe crear el archivo de lock con el PID actual."""
        result = acquire_instance_lock()
        self.assertTrue(result)
        self.assertTrue(LOCK_FILE.exists())
        stored_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
        self.assertEqual(stored_pid, os.getpid())

    def test_release_removes_lock_file(self):
        """release_instance_lock debe eliminar el archivo de lock."""
        acquire_instance_lock()
        self.assertTrue(LOCK_FILE.exists())
        release_instance_lock()
        self.assertFalse(LOCK_FILE.exists())

    def test_stale_lock_is_cleaned(self):
        """Un lock con PID inexistente debe ser eliminado y permitir adquisición."""
        # Escribir un lock con PID que seguramente no existe
        Path("logs").mkdir(exist_ok=True)
        fake_pid = 99999999
        LOCK_FILE.write_text(str(fake_pid), encoding="utf-8")

        with patch("psutil.pid_exists", return_value=False):
            result = acquire_instance_lock()
            self.assertTrue(result)

    @patch("core.instance_lock._is_jarvis_process", return_value=True)
    @patch("psutil.pid_exists", return_value=True)
    def test_active_jarvis_blocks_new_instance(self, mock_pid_exists, mock_is_jarvis):
        """Si hay un proceso Jarvis activo con el PID del lock, debe bloquear."""
        Path("logs").mkdir(exist_ok=True)
        fake_pid = 12345
        LOCK_FILE.write_text(str(fake_pid), encoding="utf-8")

        result = acquire_instance_lock()
        self.assertFalse(result)

    @patch("core.instance_lock._is_jarvis_process", return_value=False)
    @patch("psutil.pid_exists", return_value=True)
    def test_non_jarvis_pid_cleans_lock(self, mock_pid_exists, mock_is_jarvis):
        """Si el PID existe pero no es Jarvis, el lock debe limpiarse."""
        Path("logs").mkdir(exist_ok=True)
        fake_pid = 12345
        LOCK_FILE.write_text(str(fake_pid), encoding="utf-8")

        result = acquire_instance_lock()
        self.assertTrue(result)

    def test_corrupt_lock_file_is_handled(self):
        """Un lock file con contenido no numérico debe ser eliminado."""
        Path("logs").mkdir(exist_ok=True)
        LOCK_FILE.write_text("not_a_pid", encoding="utf-8")

        result = acquire_instance_lock()
        self.assertTrue(result)

    def test_idempotent_release(self):
        """Llamar release sin haber adquirido no debe fallar."""
        release_instance_lock()  # No debería lanzar excepción

    def test_is_jarvis_process_with_mock(self):
        """_is_jarvis_process debe retornar True si cmdline contiene 'main.py'."""
        mock_proc = MagicMock()
        mock_proc.cmdline.return_value = ["python", "main.py"]
        with patch("psutil.Process", return_value=mock_proc):
            self.assertTrue(_is_jarvis_process(os.getpid()))

    def test_is_jarvis_process_non_jarvis(self):
        """_is_jarvis_process debe retornar False si cmdline no tiene jarvis/main.py."""
        mock_proc = MagicMock()
        mock_proc.cmdline.return_value = ["python", "some_other_script.py"]
        with patch("psutil.Process", return_value=mock_proc):
            self.assertFalse(_is_jarvis_process(os.getpid()))


if __name__ == "__main__":
    unittest.main()
