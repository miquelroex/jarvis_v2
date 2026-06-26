"""Tests del arranque automático con Windows (core/autostart.py)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.autostart as au


class TestBatContent(unittest.TestCase):
    def test_includes_parts(self):
        bat = au.build_bat_content(r"C:\Users\x\jarvis", r"C:\py\pythonw.exe")
        self.assertIn("@echo off", bat)
        self.assertIn(r'cd /d "C:\Users\x\jarvis"', bat)
        self.assertIn("pythonw.exe", bat)
        self.assertIn("main.py", bat)
        self.assertIn("--awake", bat)

    def test_uses_crlf(self):
        bat = au.build_bat_content("r", "p")
        self.assertIn("\r\n", bat)


class TestRegistryLogic(unittest.TestCase):
    def test_enable_writes_bat_and_registers(self):
        tmp_bat = Path(tempfile.mkdtemp()) / "jarvis_autostart.bat"
        calls = {}
        with patch.object(au, "BAT_PATH", tmp_bat), \
             patch.object(au, "_reg_set", side_effect=lambda n, v: calls.update(name=n, value=v) or True):
            ok = au.enable_autostart()
        self.assertTrue(ok)
        self.assertTrue(tmp_bat.exists())               # se escribió el .bat
        self.assertEqual(calls["name"], au.APP_NAME)
        self.assertIn(str(tmp_bat), calls["value"])     # se registró su ruta

    def test_enable_returns_false_if_bat_fails(self):
        with patch.object(au, "BAT_PATH", Path("Z:/no/existe/x.bat")), \
             patch.object(au, "_reg_set") as mock_set:
            ok = au.enable_autostart()
        self.assertFalse(ok)
        mock_set.assert_not_called()  # ni siquiera intenta registrar

    def test_disable_calls_reg_delete(self):
        with patch.object(au, "_reg_delete", return_value=True) as mock_del:
            self.assertTrue(au.disable_autostart())
        mock_del.assert_called_once_with(au.APP_NAME)

    def test_is_enabled_true_when_value_present(self):
        with patch.object(au, "_reg_get", return_value='"C:\\x.bat"'):
            self.assertTrue(au.is_autostart_enabled())

    def test_is_enabled_false_when_absent(self):
        with patch.object(au, "_reg_get", return_value=None):
            self.assertFalse(au.is_autostart_enabled())


class TestRegistryAccess(unittest.TestCase):
    """Verifica _reg_set/_get/_delete sobre un winreg falso."""

    def _fake_winreg(self, store):
        import types as _t

        class _Key:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def OpenKey(root, path, idx, access):
            return _Key()

        def SetValueEx(key, name, r, typ, val):
            store[name] = val

        def QueryValueEx(key, name):
            if name not in store:
                raise FileNotFoundError()
            return store[name], 1

        def DeleteValue(key, name):
            if name not in store:
                raise FileNotFoundError()
            del store[name]

        return _t.SimpleNamespace(
            HKEY_CURRENT_USER=0, KEY_SET_VALUE=1, KEY_READ=2, REG_SZ=1,
            OpenKey=OpenKey, SetValueEx=SetValueEx, QueryValueEx=QueryValueEx,
            DeleteValue=DeleteValue,
        )

    def test_roundtrip(self):
        store = {}
        fake = self._fake_winreg(store)
        with patch.dict(sys.modules, {"winreg": fake}):
            self.assertTrue(au._reg_set("X", "valor"))
            self.assertEqual(au._reg_get("X"), "valor")
            self.assertTrue(au._reg_delete("X"))
            self.assertIsNone(au._reg_get("X"))
            # borrar algo inexistente -> True (objetivo cumplido)
            self.assertTrue(au._reg_delete("X"))

    def test_reg_set_failure_returns_false(self):
        import types as _t

        def boom(*a, **k):
            raise OSError("acceso denegado")
        fake = _t.SimpleNamespace(HKEY_CURRENT_USER=0, KEY_SET_VALUE=1, REG_SZ=1, OpenKey=boom)
        with patch.dict(sys.modules, {"winreg": fake}):
            self.assertFalse(au._reg_set("X", "v"))

    def test_reg_delete_failure_returns_false(self):
        import types as _t

        class _Key:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def DeleteValue(key, name):
            raise PermissionError("sin permiso")
        fake = _t.SimpleNamespace(HKEY_CURRENT_USER=0, KEY_SET_VALUE=1,
                                  OpenKey=lambda *a: _Key(), DeleteValue=DeleteValue)
        with patch.dict(sys.modules, {"winreg": fake}):
            self.assertFalse(au._reg_delete("X"))


if __name__ == "__main__":
    unittest.main()
