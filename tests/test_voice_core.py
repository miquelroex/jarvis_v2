"""Tests del núcleo holográfico reactivo a la voz (core/voice_core.py)."""
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

import core.voice_core as vc


class TestComputeEnvelope(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(vc.compute_envelope(np.array([], dtype=np.int16), 1, 44100), [])

    def test_silence_is_zero(self):
        samples = np.zeros(44100, dtype=np.int16)
        env = vc.compute_envelope(samples, 1, 44100, fps=10)
        self.assertTrue(all(v == 0.0 for v in env))
        self.assertEqual(len(env), 10)

    def test_range_0_1_and_peak_normalized(self):
        # Señal con amplitud creciente: la envolvente debe llegar a ~1 en el pico.
        t = np.linspace(0, 1, 44100, endpoint=False)
        ramp = (t * 30000).astype(np.float32)
        sig = (np.sin(2 * np.pi * 220 * t) * ramp).astype(np.int16)
        env = vc.compute_envelope(sig, 1, 44100, fps=20)
        self.assertEqual(len(env), 20)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in env))
        self.assertAlmostEqual(max(env), 1.0, places=3)
        # Creciente: el último fotograma supera al primero.
        self.assertGreater(env[-1], env[0])

    def test_stereo_downmix(self):
        # Estéreo intercalado: canal izq fuerte, der silencio -> no crashea, normaliza.
        mono = (np.sin(np.linspace(0, 50, 4410)) * 10000).astype(np.int16)
        stereo = np.empty(mono.size * 2, dtype=np.int16)
        stereo[0::2] = mono
        stereo[1::2] = 0
        env = vc.compute_envelope(stereo, 2, 44100, fps=10)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in env))


class TestEmit(unittest.TestCase):
    def test_emits_event_with_payload(self):
        captured = []
        fake = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: captured.append((ev, a))))
        with patch.dict(sys.modules, {"gui.app": fake}):
            vc._emit("voice_level", {"level": 0.5})
            vc._emit("voice_core_stop")
        self.assertEqual(captured[0][0], "voice_level")
        self.assertEqual(captured[0][1][0], {"level": 0.5})
        self.assertEqual(captured[1][0], "voice_core_stop")

    def test_no_emit_without_gui(self):
        saved = sys.modules.pop("gui.app", None)
        try:
            vc._emit("voice_level", {"level": 1})  # no debe lanzar
        finally:
            if saved is not None:
                sys.modules["gui.app"] = saved


class TestStartStopGate(unittest.TestCase):
    def tearDown(self):
        vc.stop_voice_core()
        vc._stream_thread = None

    def test_disabled_does_not_emit_start(self):
        captured = []
        fake = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: captured.append(ev)))
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.dict(os.environ, {"JARVIS_VOICE_CORE_ENABLED": "false"}):
            vc.start_voice_core("noexiste.mp3")
        self.assertNotIn("voice_core_start", captured)

    def test_enabled_emits_start_even_if_audio_fails(self):
        captured = []
        fake = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: captured.append(ev)))
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.dict(os.environ, {"JARVIS_VOICE_CORE_ENABLED": "true"}):
            vc.start_voice_core("archivo_inexistente_xyz.mp3")  # falla la carga -> sólo start
        self.assertIn("voice_core_start", captured)


if __name__ == "__main__":
    unittest.main()