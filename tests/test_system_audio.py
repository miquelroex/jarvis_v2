"""Tests del control de volumen/multimedia (core/system_audio.py)."""
import os
import sys
import types
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.system_audio as sa


class _FakeEndpoint:
    """Imita el control de volumen de pycaw."""
    def __init__(self, scalar=0.5, muted=0):
        self._scalar = scalar
        self._muted = muted
        self.set_scalar_calls = []
    def GetMasterVolumeLevelScalar(self):
        return self._scalar
    def SetMasterVolumeLevelScalar(self, value, _ctx):
        self._scalar = value
        self.set_scalar_calls.append(value)
    def GetMute(self):
        return self._muted
    def SetMute(self, state, _ctx):
        self._muted = state


class TestVolume(unittest.TestCase):
    def test_get_volume(self):
        with patch.object(sa, "_get_endpoint", return_value=_FakeEndpoint(scalar=0.42)):
            self.assertEqual(sa.get_volume(), 42)

    def test_get_volume_unavailable(self):
        with patch.object(sa, "_get_endpoint", side_effect=OSError("no audio")):
            self.assertEqual(sa.get_volume(), -1)

    def test_set_volume_clamps(self):
        ep = _FakeEndpoint()
        with patch.object(sa, "_get_endpoint", return_value=ep):
            self.assertEqual(sa.set_volume(150), 100)
            self.assertEqual(sa.set_volume(-20), 0)
        self.assertEqual(ep.set_scalar_calls[0], 1.0)
        self.assertEqual(ep.set_scalar_calls[1], 0.0)

    def test_set_volume_unmutes_when_positive(self):
        ep = _FakeEndpoint(muted=1)
        with patch.object(sa, "_get_endpoint", return_value=ep):
            sa.set_volume(30)
        self.assertEqual(ep._muted, 0)

    def test_change_volume_relative(self):
        ep = _FakeEndpoint(scalar=0.5)
        with patch.object(sa, "_get_endpoint", return_value=ep):
            self.assertEqual(sa.change_volume(10), 60)
            self.assertEqual(sa.change_volume(-25), 35)

    def test_change_volume_unavailable(self):
        with patch.object(sa, "_get_endpoint", side_effect=OSError("no audio")):
            self.assertEqual(sa.change_volume(10), -1)


class TestMute(unittest.TestCase):
    def test_set_mute(self):
        ep = _FakeEndpoint()
        with patch.object(sa, "_get_endpoint", return_value=ep):
            self.assertTrue(sa.set_mute(True))
        self.assertEqual(ep._muted, 1)

    def test_is_muted(self):
        with patch.object(sa, "_get_endpoint", return_value=_FakeEndpoint(muted=1)):
            self.assertTrue(sa.is_muted())
        with patch.object(sa, "_get_endpoint", return_value=_FakeEndpoint(muted=0)):
            self.assertFalse(sa.is_muted())


class TestMediaAction(unittest.TestCase):
    def test_valid_action_sends_key(self):
        presses = []
        fake_win32api = types.SimpleNamespace(keybd_event=lambda *a: presses.append(a))
        fake_win32con = types.SimpleNamespace(KEYEVENTF_KEYUP=2)
        with patch.dict(sys.modules, {"win32api": fake_win32api, "win32con": fake_win32con}):
            ok = sa.media_action("play_pause")
        self.assertTrue(ok)
        self.assertEqual(len(presses), 2)              # keydown + keyup
        self.assertEqual(presses[0][0], 0xB3)          # VK play/pause

    def test_invalid_action(self):
        self.assertFalse(sa.media_action("inventado"))


if __name__ == "__main__":
    unittest.main()
