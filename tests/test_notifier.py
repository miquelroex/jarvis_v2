import unittest
from unittest.mock import patch, MagicMock
import urllib.request
import urllib.parse
import os

# Import core.notifier
import core.notifier as notifier

class TestNotifier(unittest.TestCase):

    @patch("core.notifier.os.getenv")
    @patch("urllib.request.urlopen")
    def test_send_push_notification_ntfy_success(self, mock_urlopen, mock_getenv):
        # Configurar env para ntfy
        mock_getenv.side_effect = lambda k, default=None: {
            "JARVIS_NTFY_TOPIC": "my-topic-123",
            "JARVIS_NTFY_SERVER": "https://ntfy.sh"
        }.get(k, default)
        
        # Simular respuesta HTTP 200 OK
        mock_res = MagicMock()
        mock_res.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_res
        
        # Ejecutar
        res = notifier.send_push_notification(
            title="Test Title",
            message="Test Message Content",
            priority="high",
            tags=["checked", "robot"]
        )
        
        self.assertTrue(res)
        mock_urlopen.assert_called_once()
        
        # Verificar request construida
        req_arg = mock_urlopen.call_args[0][0]
        self.assertIsInstance(req_arg, urllib.request.Request)
        self.assertEqual(req_arg.full_url, "https://ntfy.sh/my-topic-123")
        self.assertEqual(req_arg.headers["Priority"], "4")
        self.assertEqual(req_arg.headers["Tags"], "checked,robot")
        # El título en X-Title es b64, normalizado por urllib a X-title
        self.assertTrue(any(k.lower() == "x-title" for k in req_arg.headers))

    @patch("core.notifier.os.getenv")
    @patch("urllib.request.urlopen")
    def test_send_push_notification_pushover_success(self, mock_urlopen, mock_getenv):
        # Configurar env para Pushover y desactivar ntfy
        mock_getenv.side_effect = lambda k, default=None: {
            "JARVIS_NTFY_TOPIC": "",
            "PUSHOVER_USER_KEY": "user-key-abc",
            "PUSHOVER_APP_TOKEN": "app-token-xyz"
        }.get(k, default)
        
        mock_res = MagicMock()
        mock_res.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_res
        
        res = notifier.send_push_notification(
            title="Pushover Title",
            message="Pushover message content",
            priority="default"
        )
        
        self.assertTrue(res)
        mock_urlopen.assert_called_once()
        
        # Verificar request
        req_arg = mock_urlopen.call_args[0][0]
        self.assertEqual(req_arg.full_url, "https://api.pushover.net/1/messages.json")
        self.assertEqual(req_arg.method, "POST")
        
        # Parsear data post
        post_data = urllib.parse.parse_qs(req_arg.data.decode("utf-8"))
        self.assertEqual(post_data["token"][0], "app-token-xyz")
        self.assertEqual(post_data["user"][0], "user-key-abc")
        self.assertEqual(post_data["title"][0], "Pushover Title")
        self.assertEqual(post_data["message"][0], "Pushover message content")
        self.assertEqual(post_data["priority"][0], "0")

    @patch("core.notifier.os.getenv")
    def test_send_push_notification_missing_config(self, mock_getenv):
        # Sin variables configuradas
        mock_getenv.return_value = None
        
        res = notifier.send_push_notification("Title", "Message")
        self.assertFalse(res)

if __name__ == "__main__":
    unittest.main()
