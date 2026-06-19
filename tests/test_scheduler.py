import unittest
import os
import sys
import tempfile
import sqlite3
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.memory import set_db_path, init_db, db_get_active_tasks
from core.scheduler import (
    add_reminder,
    cancel_task,
    get_active_tasks,
    execute_reminder_task
)

class TestScheduler(unittest.TestCase):
    def setUp(self):
        # Crear base de datos temporal
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.test_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        
        set_db_path(self.test_db_path)
        init_db(self.test_db_path)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_add_and_cancel_reminder(self):
        # 1. Agregar recordatorio
        success = add_reminder("reminder_test_1", "Hacer ejercicio", seconds_delay=10, interval_seconds=0)
        self.assertTrue(success)

        # Verificar en base de datos
        tasks = get_active_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["name"], "reminder_test_1")
        self.assertEqual(tasks[0]["target"], "Hacer ejercicio")
        self.assertEqual(tasks[0]["interval_seconds"], 0)
        self.assertEqual(tasks[0]["enabled"], 1)

        # 2. Cancelar recordatorio
        cancel_success = cancel_task("reminder_test_1")
        self.assertTrue(cancel_success)
        
        # Verificar eliminación
        tasks_after = get_active_tasks()
        self.assertEqual(len(tasks_after), 0)

    @patch("core.scheduler.speak")
    @patch("core.scheduler.send_push_notification")
    def test_execute_reminder_task_single_run(self, mock_push, mock_speak):
        # Programar recordatorio de ejecución única
        add_reminder("reminder_single", "Comprar pan", seconds_delay=1, interval_seconds=0)
        
        tasks = get_active_tasks()
        task = tasks[0]
        
        # Ejecutar tarea manualmente
        execute_reminder_task(task)
        
        # Debe llamar a speak y push
        mock_speak.assert_called_with("Disculpe la interrupción, señor. Me he tomado la libertad de recordarle que: Comprar pan")
        mock_push.assert_called_once()
        
        # Al ser ejecución única, debe eliminarse de la BD tras su ejecución
        tasks_post = get_active_tasks()
        self.assertEqual(len(tasks_post), 0)

    @patch("core.scheduler.speak")
    @patch("core.scheduler.send_push_notification")
    def test_execute_reminder_task_periodic(self, mock_push, mock_speak):
        # Programar recordatorio periódico (cada 60 segundos)
        add_reminder("reminder_periodic", "Beber agua", seconds_delay=1, interval_seconds=60)
        
        tasks = get_active_tasks()
        task = tasks[0]
        
        # Ejecutar
        execute_reminder_task(task)
        
        # Debe actualizar campos en la BD (last_run, last_result, next_run)
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT last_run, last_result, next_run FROM scheduled_tasks WHERE name='reminder_periodic'")
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertIsNotNone(row[0]) # last_run
        self.assertEqual(row[1], "success") # last_result
        self.assertIsNotNone(row[2]) # next_run (debe estar en el futuro)
        
        # Debe seguir estando activa
        tasks_post = get_active_tasks()
        self.assertEqual(len(tasks_post), 1)

if __name__ == "__main__":
    unittest.main()
