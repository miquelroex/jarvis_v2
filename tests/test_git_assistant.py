import os
import unittest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

from core.git_assistant import (
    get_git_branch,
    get_git_status,
    get_git_diff,
    get_git_log,
    generate_commit_message,
    generate_branch_summary,
    generate_branch_changelog,
    apply_git_commit
)
from tools.git_assistant_tool import (
    git_diff_summary,
    git_branch_changelog,
    git_branch_summary,
    git_apply_commit
)
from core.fast_commands import handle_fast_command
from core.pending_actions import PENDING_ACTION_FILE, clear_pending_action


class TestGitAssistant(unittest.TestCase):
    def setUp(self):
        clear_pending_action()

    def tearDown(self):
        clear_pending_action()

    @patch("core.git_assistant._run_git_cmd")
    def test_get_git_branch(self, mock_run):
        mock_run.return_value = (0, "feature/git-assistant\n", "")
        branch = get_git_branch()
        self.assertEqual(branch, "feature/git-assistant")
        mock_run.assert_called_once_with(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    @patch("core.git_assistant._run_git_cmd")
    def test_get_git_status(self, mock_run):
        mock_run.return_value = (0, " M core/git_assistant.py\n?? tests/test_git_assistant.py\n", "")
        status = get_git_status()
        self.assertIn("M core/git_assistant.py", status)
        self.assertIn("?? tests/test_git_assistant.py", status)

    @patch("core.git_assistant._run_git_cmd")
    def test_get_git_diff(self, mock_run):
        mock_run.return_value = (0, "diff --git a/core/git_assistant.py b/core/git_assistant.py\n...", "")
        diff = get_git_diff(staged=True)
        self.assertTrue(diff.startswith("diff --git"))
        mock_run.assert_called_once_with(["git", "diff", "--cached"])

    @patch("core.git_assistant.ask_code_model")
    @patch("core.git_assistant.get_git_diff")
    def test_generate_commit_message_success(self, mock_diff, mock_ask):
        mock_diff.return_value = "diff --git a/tools/voice.py b/tools/voice.py\n+ # add config"
        mock_ask.return_value = "feat(voice): add Edge-TTS configuration"
        
        msg = generate_commit_message(staged=True)
        self.assertEqual(msg, "feat(voice): add Edge-TTS configuration")
        mock_ask.assert_called_once()

    @patch("core.git_assistant.get_git_diff")
    def test_generate_commit_message_empty(self, mock_diff):
        mock_diff.return_value = "   \n"  # diff vacío
        msg = generate_commit_message(staged=True)
        self.assertIn("No he detectado ningún cambio", msg)

    @patch("core.git_assistant.ask_code_model")
    @patch("core.git_assistant.get_git_diff_stat")
    @patch("core.git_assistant.get_git_status")
    @patch("core.git_assistant.get_git_branch")
    def test_generate_branch_summary(self, mock_branch, mock_status, mock_diff_stat, mock_ask):
        mock_branch.return_value = "main"
        mock_status.return_value = " M file.py"
        mock_diff_stat.return_value = "1 file changed, 1 insertion(+)"
        mock_ask.return_value = "Señor, en la rama main hay cambios pendientes."

        summary = generate_branch_summary()
        self.assertEqual(summary, "Señor, en la rama main hay cambios pendientes.")
        mock_ask.assert_called_once()

    @patch("core.git_assistant.ask_code_model")
    @patch("core.git_assistant.get_git_log")
    def test_generate_branch_changelog(self, mock_log, mock_ask):
        mock_log.return_value = "1234567 feat: first commit\n89abcdef fix: critical bug"
        mock_ask.return_value = "### Changelog\n- Nueva funcionalidad..."

        changelog = generate_branch_changelog("main")
        self.assertEqual(changelog, "### Changelog\n- Nueva funcionalidad...")
        mock_ask.assert_called_once()

    @patch("core.git_assistant._run_git_cmd")
    @patch("core.git_assistant.get_git_diff")
    def test_apply_git_commit_success(self, mock_diff, mock_run):
        mock_diff.return_value = "staged changes exist"
        mock_run.return_value = (0, "[main 9908b76] feat: commit\n 1 file changed\n", "")
        
        res = apply_git_commit("feat: commit")
        self.assertIn("He registrado el commit con éxito", res)
        mock_run.assert_called_once_with(["git", "commit", "-m", "feat: commit"])

    @patch("tools.git_assistant_tool.apply_git_commit")
    def test_git_apply_commit_tool_safe_mode(self, mock_apply):
        # Con safe_mode activo, debería guardar acción pendiente y no llamar a apply_git_commit
        with patch.dict(os.environ, {"JARVIS_SAFE_MODE": "True"}):
            res = git_apply_commit.invoke({"message": "feat: test-safe-commit"})
            self.assertIn("requiere confirmación de seguridad", res)
            mock_apply.assert_not_called()
            self.assertTrue(PENDING_ACTION_FILE.exists())
            
            # Verificar acción guardada
            data = json.loads(PENDING_ACTION_FILE.read_text(encoding="utf-8"))
            self.assertEqual(data["action_type"], "git_commit")
            self.assertEqual(data["data"]["message"], "feat: test-safe-commit")

    @patch("core.git_assistant.generate_commit_message")
    def test_fast_commands_git_commit_trigger(self, mock_gen):
        mock_gen.return_value = "feat(fast): trigger commit"
        
        res = handle_fast_command("genera un mensaje de commit")
        self.assertIsNotNone(res)
        self.assertIn("feat(fast): trigger commit", res)
        self.assertTrue(PENDING_ACTION_FILE.exists())
        
        data = json.loads(PENDING_ACTION_FILE.read_text(encoding="utf-8"))
        self.assertEqual(data["action_type"], "git_commit")
        self.assertEqual(data["data"]["message"], "feat(fast): trigger commit")

    @patch("core.git_assistant.generate_branch_summary")
    def test_fast_commands_branch_summary_trigger(self, mock_sum):
        mock_sum.return_value = "Resumen de rama."
        res = handle_fast_command("resumen de rama")
        self.assertEqual(res, "Resumen de rama.")


if __name__ == "__main__":
    unittest.main()
