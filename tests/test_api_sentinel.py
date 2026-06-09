import os
import unittest
from unittest.mock import patch, MagicMock
from core.api_sentinel import check_all_apis_status, _sentinel_loop, LAST_STATUS
from tools.api_sentinel_tool import check_api_status

class TestAPISentinel(unittest.TestCase):
    def setUp(self):
        # Reset LAST_STATUS before each test
        for k in LAST_STATUS:
            LAST_STATUS[k] = "none"

    @patch('requests.get')
    def test_check_all_apis_status_operational(self, mock_get):
        # Configurar mocks
        mock_response_github = MagicMock()
        mock_response_github.status_code = 200
        mock_response_github.json.return_value = {
            "status": {"indicator": "none", "description": "All Systems Operational"}
        }

        mock_response_openai = MagicMock()
        mock_response_openai.status_code = 200
        mock_response_openai.json.return_value = {
            "status": {"indicator": "none", "description": "Operational"}
        }

        mock_response_gemini = MagicMock()
        mock_response_gemini.status_code = 200

        mock_get.side_effect = [mock_response_github, mock_response_openai, mock_response_gemini]

        with patch.dict(os.environ, {"GOOGLE_API_KEY": ""}):
            results = check_all_apis_status()
            self.assertEqual(results["GitHub"]["status"], "none")
            self.assertEqual(results["OpenAI"]["status"], "none")
            self.assertEqual(results["Gemini"]["status"], "none")

    @patch('requests.get')
    @patch('core.api_sentinel.is_internet_available')
    def test_check_all_apis_status_degraded(self, mock_internet, mock_get):
        mock_internet.return_value = True

        mock_response_github = MagicMock()
        mock_response_github.status_code = 200
        mock_response_github.json.return_value = {
            "status": {"indicator": "critical", "description": "Major Outage"}
        }

        mock_response_openai = MagicMock()
        mock_response_openai.status_code = 200
        mock_response_openai.json.return_value = {
            "status": {"indicator": "minor", "description": "Degraded"}
        }

        mock_response_gemini = MagicMock()
        mock_response_gemini.status_code = 500

        mock_get.side_effect = [mock_response_github, mock_response_openai, mock_response_gemini]

        with patch.dict(os.environ, {"GOOGLE_API_KEY": ""}):
            results = check_all_apis_status()
            self.assertEqual(results["GitHub"]["status"], "critical")
            self.assertEqual(results["OpenAI"]["status"], "minor")
            self.assertEqual(results["Gemini"]["status"], "critical")

    @patch('core.api_sentinel.check_all_apis_status')
    @patch('core.api_sentinel.is_internet_available')
    @patch('core.api_sentinel.speak')
    @patch('time.sleep')
    def test_sentinel_alert_on_state_change(self, mock_sleep, mock_speak, mock_internet, mock_check):
        mock_internet.return_value = True
        
        mock_check.side_effect = [
            # Inicial
            {
                "GitHub": {"status": "none", "description": "All Systems Operational"},
                "OpenAI": {"status": "none", "description": "Operational"},
                "Gemini": {"status": "none", "description": "Operational"}
            },
            # Segunda (degradado)
            {
                "GitHub": {"status": "none", "description": "All Systems Operational"},
                "OpenAI": {"status": "minor", "description": "Degraded Performance"},
                "Gemini": {"status": "none", "description": "Operational"}
            },
            # Tercera (sin cambios)
            {
                "GitHub": {"status": "none", "description": "All Systems Operational"},
                "OpenAI": {"status": "minor", "description": "Degraded Performance"},
                "Gemini": {"status": "none", "description": "Operational"}
            },
            # Cuarta (recuperado)
            {
                "GitHub": {"status": "none", "description": "All Systems Operational"},
                "OpenAI": {"status": "none", "description": "Operational"},
                "Gemini": {"status": "none", "description": "Operational"}
            }
        ]

        import core.api_sentinel
        wait_calls = 0
        def mock_wait(timeout=None):
            nonlocal wait_calls
            wait_calls += 1
            if wait_calls >= 4:
                return True
            return False

        original_stop = core.api_sentinel.stop_event
        core.api_sentinel.stop_event = MagicMock()
        core.api_sentinel.stop_event.wait.side_effect = mock_wait
        core.api_sentinel.stop_event.is_set.side_effect = lambda: wait_calls >= 4

        try:
            _sentinel_loop()
        finally:
            core.api_sentinel.stop_event = original_stop

        self.assertEqual(mock_speak.call_count, 2)
        args1 = mock_speak.call_args_list[0][0][0]
        args2 = mock_speak.call_args_list[1][0][0]
        self.assertIn("degradación de servicio", args1)
        self.assertIn("se ha restablecido", args2)

    @patch('core.api_sentinel.check_all_apis_status')
    @patch('core.api_sentinel.is_internet_available')
    @patch('core.api_sentinel.speak')
    @patch('time.sleep')
    def test_sentinel_no_alert_when_no_internet(self, mock_sleep, mock_speak, mock_internet, mock_check):
        mock_internet.return_value = False

        mock_check.side_effect = [
            # Inicial
            {
                "GitHub": {"status": "none", "description": "All Systems Operational"},
                "OpenAI": {"status": "none", "description": "Operational"},
                "Gemini": {"status": "none", "description": "Operational"}
            },
            # Segunda
            {
                "GitHub": {"status": "critical", "description": "Outage"},
                "OpenAI": {"status": "critical", "description": "Outage"},
                "Gemini": {"status": "critical", "description": "Outage"}
            }
        ]

        import core.api_sentinel
        wait_calls = 0
        def mock_wait(timeout=None):
            nonlocal wait_calls
            wait_calls += 1
            if wait_calls >= 2:
                return True
            return False

        original_stop = core.api_sentinel.stop_event
        core.api_sentinel.stop_event = MagicMock()
        core.api_sentinel.stop_event.wait.side_effect = mock_wait
        core.api_sentinel.stop_event.is_set.side_effect = lambda: wait_calls >= 2

        try:
            _sentinel_loop()
        finally:
            core.api_sentinel.stop_event = original_stop

        mock_speak.assert_not_called()

    @patch('tools.api_sentinel_tool.check_all_apis_status')
    def test_api_sentinel_tool(self, mock_check):
        mock_check.return_value = {
            "GitHub": {"status": "none", "description": "All Systems Operational"},
            "OpenAI": {"status": "minor", "description": "Degraded Performance"},
            "Gemini": {"status": "critical", "description": "Service Unavailable"}
        }

        res = check_api_status.invoke("")
        self.assertIn("GitHub", res)
        self.assertIn("OpenAI", res)
        self.assertIn("Gemini", res)
        self.assertIn("🟢", res)
        self.assertIn("🟡", res)
        self.assertIn("🔴", res)
