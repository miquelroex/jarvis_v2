import unittest
import os
import sys
import tempfile
import sqlite3
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Root of the project in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.memory import set_db_path, init_db, db_get_active_tasks
from core.scheduler import (
    is_private_ip,
    add_url_monitor,
    execute_url_monitor,
    reactivate_url_monitor,
    get_active_tasks,
    cancel_task
)
from core.pending_actions import PENDING_ACTION_FILE, clear_pending_action, execute_pending_action

class TestUrlMonitor(unittest.TestCase):
    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.test_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        
        set_db_path(self.test_db_path)
        init_db(self.test_db_path)
        clear_pending_action()

    def tearDown(self):
        clear_pending_action()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    def test_is_private_ip(self):
        self.assertTrue(is_private_ip("127.0.0.1"))
        self.assertTrue(is_private_ip("10.0.0.5"))
        self.assertTrue(is_private_ip("172.16.42.1"))
        self.assertTrue(is_private_ip("192.168.1.100"))
        self.assertTrue(is_private_ip("169.254.10.10"))
        self.assertFalse(is_private_ip("8.8.8.8"))
        self.assertFalse(is_private_ip("142.250.184.238"))
        self.assertFalse(is_private_ip("not-an-ip"))

    @patch("socket.gethostbyname")
    def test_add_url_monitor_validation(self, mock_gethostbyname):
        # 1. Invalid protocol
        res = add_url_monitor("mon_ftp", "ftp://example.com", 300)
        self.assertIn("Error: Protocolo 'ftp' no permitido", res)
        
        # 2. Public IP
        mock_gethostbyname.return_value = "8.8.8.8"
        res = add_url_monitor("mon_public", "https://example.com", 300)
        self.assertIn("registrado con éxito", res)
        
        tasks = get_active_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["name"], "mon_public")
        self.assertEqual(tasks[0]["interval_seconds"], 300)
        
        # 3. Local IP, allow_local_network=False
        mock_gethostbyname.return_value = "192.168.1.10"
        res = add_url_monitor("mon_local_blocked", "http://192.168.1.10", 300, allow_local_network=False)
        self.assertIn("Error: No se permite monitorear URLs de la red local", res)
        
        # 4. Local IP, allow_local_network=True
        res = add_url_monitor("mon_local_pending", "http://192.168.1.10", 400, allow_local_network=True)
        self.assertIn("Confirmación requerida", res)
        
        # Verify pending action file exists
        self.assertTrue(PENDING_ACTION_FILE.exists())
        
    def test_pending_action_confirmation(self):
        # Setup a pending action manually or via add_url_monitor
        with patch("socket.gethostbyname") as mock_dns:
            mock_dns.return_value = "127.0.0.1"
            add_url_monitor("mon_confirm", "http://127.0.0.1/status", 300, allow_local_network=True)
            
        # Execute confirmation
        confirm_res = execute_pending_action()
        self.assertIn("Acción confirmada", confirm_res)
        
        # Verify the task was registered in the database with allow_local_network=True
        tasks = get_active_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["name"], "mon_confirm")
        
        metadata = json.loads(tasks[0]["metadata"])
        self.assertTrue(metadata["allow_local_network"])
        self.assertFalse(metadata["alerted"])

    @patch("socket.gethostbyname")
    @patch("requests.get")
    @patch("core.scheduler.speak")
    @patch("core.scheduler.send_push_notification")
    def test_execute_url_monitor_flow(self, mock_push, mock_speak, mock_requests, mock_dns):
        mock_dns.return_value = "8.8.8.8"
        # 1. Setup mock response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_content.return_value = [b"Initial Web Content"]
        mock_requests.return_value = mock_resp
        
        # Save a public monitor task to DB
        add_url_monitor("mon_flow", "https://example.com/page", 300)
            
        tasks = get_active_tasks()
        task = tasks[0]
        
        # Run execution for the first time -> computes initial hash
        execute_url_monitor(task)
        
        # DB check: should be success and metadata updated with hash
        tasks_after = get_active_tasks()
        self.assertEqual(len(tasks_after), 1)
        task = tasks_after[0]
        self.assertEqual(task["last_result"], "success")
        metadata = json.loads(task["metadata"])
        initial_hash = metadata["last_hash"]
        self.assertTrue(len(initial_hash) > 0)
        self.assertFalse(metadata["alerted"])
        
        # Run execution again with NO changes
        mock_resp.iter_content.return_value = [b"Initial Web Content"]
        # Reload task to get updated next_run/metadata
        task = tasks_after[0]
        execute_url_monitor(task)
        
        # Verify alerted is still False and no alert speak called
        tasks_after = get_active_tasks()
        task = tasks_after[0]
        metadata = json.loads(task["metadata"])
        self.assertEqual(metadata["last_hash"], initial_hash)
        self.assertFalse(metadata["alerted"])
        mock_speak.assert_not_called()
        
        # Run execution with content CHANGE
        mock_resp.iter_content.return_value = [b"Modified Web Content"]
        execute_url_monitor(task)
        
        # Verify alerted is True, speak and push are called
        tasks_after = get_active_tasks()
        task = tasks_after[0]
        metadata = json.loads(task["metadata"])
        self.assertTrue(metadata["alerted"])
        mock_speak.assert_called_once()
        mock_push.assert_called_once()
        
        # Reset mocks
        mock_speak.reset_mock()
        mock_push.reset_mock()
        mock_requests.reset_mock()
        
        # Run execution again while alerted=True
        execute_url_monitor(task)
        # Should skip download (requests.get not called) and not speak
        mock_requests.assert_not_called()
        mock_speak.assert_not_called()
        
        # Reactivate monitor
        react_res = reactivate_url_monitor("mon_flow")
        self.assertIn("Éxito", react_res)
        
        # Verify alerted became False in DB
        tasks_after = get_active_tasks()
        task = tasks_after[0]
        metadata = json.loads(task["metadata"])
        self.assertFalse(metadata["alerted"])

if __name__ == "__main__":
    unittest.main()
