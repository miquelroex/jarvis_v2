"""Tests del .env Manager (core/env_manager.py)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.env_manager as em


CODE_SAMPLE = '''
import os
a = os.getenv("REQUIRED_ONE")
b = os.getenv("OPTIONAL_ONE", "default")
c = os.environ["REQUIRED_TWO"]
d = os.environ.get("OPTIONAL_TWO")
e = os.getenv('REQUIRED_THREE')
'''


class TestScan(unittest.TestCase):
    def _make_pkg(self, tmp):
        d = Path(tmp) / "core"
        d.mkdir()
        (d / "mod.py").write_text(CODE_SAMPLE, encoding="utf-8")
        return tmp

    def test_classifies_required_vs_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_pkg(tmp)
            with self._patch_root(tmp):
                refs = em.scan_code_for_env_vars(roots=["core"])
        self.assertEqual(refs["required"], {"REQUIRED_ONE", "REQUIRED_TWO", "REQUIRED_THREE"})
        self.assertEqual(refs["optional"], {"OPTIONAL_ONE", "OPTIONAL_TWO"})

    def _patch_root(self, tmp):
        from unittest.mock import patch
        return patch.object(em, "PROJECT_ROOT", Path(tmp))


class TestParseEnv(unittest.TestCase):
    def test_parses_names_and_emptiness_without_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            envp = Path(tmp) / ".env"
            envp.write_text(
                "# comentario\nFULL=algo_secreto\nEMPTY=\nSPACES=   \nMALA LINEA\n",
                encoding="utf-8",
            )
            defined = em.parse_env_definitions(env_path=envp)
        self.assertEqual(set(defined), {"FULL", "EMPTY", "SPACES"})
        self.assertFalse(defined["FULL"])     # tiene valor
        self.assertTrue(defined["EMPTY"])     # vacío
        self.assertTrue(defined["SPACES"])    # solo espacios -> vacío
        # Seguridad: el valor no debe aparecer en ninguna parte del resultado.
        self.assertNotIn("algo_secreto", str(defined))

    def test_missing_file_returns_empty(self):
        self.assertEqual(em.parse_env_definitions(env_path="/no/existe.env"), {})


class TestAudit(unittest.TestCase):
    def _setup(self, tmp, env_content):
        (Path(tmp) / "core").mkdir()
        (Path(tmp) / "core" / "mod.py").write_text(CODE_SAMPLE, encoding="utf-8")
        envp = Path(tmp) / ".env"
        envp.write_text(env_content, encoding="utf-8")
        return envp

    def _patch_root(self, tmp):
        from unittest.mock import patch
        return patch.object(em, "PROJECT_ROOT", Path(tmp))

    def test_advisory_when_required_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            envp = self._setup(tmp, "REQUIRED_ONE=ok\n")  # faltan REQUIRED_TWO y THREE
            with self._patch_root(tmp):
                report = em.audit_env(roots=["core"], env_path=envp)
        self.assertEqual(report["status"], "advisory")
        self.assertIn("REQUIRED_TWO", report["missing_required"])
        self.assertIn("REQUIRED_THREE", report["missing_required"])
        self.assertNotIn("OPTIONAL_ONE", report["missing_required"])  # opcional no cuenta

    def test_advisory_when_referenced_var_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            envp = self._setup(tmp, "REQUIRED_ONE=\nREQUIRED_TWO=x\nREQUIRED_THREE=y\n")
            with self._patch_root(tmp):
                report = em.audit_env(roots=["core"], env_path=envp)
        self.assertEqual(report["status"], "advisory")
        self.assertIn("REQUIRED_ONE", report["empty"])

    def test_reports_unused(self):
        with tempfile.TemporaryDirectory() as tmp:
            envp = self._setup(
                tmp,
                "REQUIRED_ONE=a\nREQUIRED_TWO=b\nREQUIRED_THREE=c\nVIEJA_VAR=x\n",
            )
            with self._patch_root(tmp):
                report = em.audit_env(roots=["core"], env_path=envp)
        self.assertIn("VIEJA_VAR", report["unused"])

    def test_dynamic_reference_not_flagged_unused(self):
        # Una variable referenciada solo como string literal (uso dinámico) NO
        # debe marcarse como "sin usar".
        with tempfile.TemporaryDirectory() as tmp:
            core = Path(tmp) / "core"
            core.mkdir()
            (core / "mod.py").write_text(CODE_SAMPLE, encoding="utf-8")
            (core / "dyn.py").write_text('MAPA = {"alias": "DYNAMIC_VAR"}\n', encoding="utf-8")
            envp = Path(tmp) / ".env"
            envp.write_text(
                "REQUIRED_ONE=a\nREQUIRED_TWO=b\nREQUIRED_THREE=c\nDYNAMIC_VAR=x\n",
                encoding="utf-8",
            )
            with self._patch_root(tmp):
                report = em.audit_env(roots=["core"], env_path=envp)
        self.assertNotIn("DYNAMIC_VAR", report["unused"])

    def test_healthy_when_all_required_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            envp = self._setup(tmp, "REQUIRED_ONE=a\nREQUIRED_TWO=b\nREQUIRED_THREE=c\n")
            with self._patch_root(tmp):
                report = em.audit_env(roots=["core"], env_path=envp)
        self.assertEqual(report["status"], "healthy")
        self.assertEqual(report["missing_required"], [])
        self.assertEqual(report["empty"], [])


if __name__ == "__main__":
    unittest.main()
