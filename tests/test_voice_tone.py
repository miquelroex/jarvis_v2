"""Tests de la voz adaptativa / tone shifting (core/voice_tone.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.voice_tone as vt


class TestDetectTone(unittest.TestCase):
    def test_alert(self):
        self.assertEqual(vt.detect_tone("ALERTA, señor. Consumo crítico de memoria."), "alert")
        self.assertEqual(vt.detect_tone("Detectada una amenaza en la red"), "alert")

    def test_calm(self):
        self.assertEqual(vt.detect_tone("Señor, es bastante tarde. Le sugiero descansar."), "calm")

    def test_humor(self):
        self.assertEqual(vt.detect_tone("Con el debido respeto, señor, es poco ortodoxa."), "humor")

    def test_success(self):
        self.assertEqual(vt.detect_tone("Tarea completada, señor. Todo operativo."), "success")

    def test_neutral_default(self):
        self.assertEqual(vt.detect_tone("Son las tres de la tarde, señor."), vt.NEUTRAL)

    def test_alert_takes_precedence_over_success(self):
        # Contiene "completado" pero también "crítico": gana la alerta.
        self.assertEqual(vt.detect_tone("Backup completado pero hay un fallo crítico"), "alert")

    def test_accents_and_case_insensitive(self):
        self.assertEqual(vt.detect_tone("EMERGENCIA"), "alert")
        self.assertEqual(vt.detect_tone("Operación finalizada con éxito"), "success")

    def test_empty(self):
        self.assertEqual(vt.detect_tone(""), vt.NEUTRAL)
        self.assertEqual(vt.detect_tone(None), vt.NEUTRAL)


class TestResolveTone(unittest.TestCase):
    def test_explicit_valid_tone_wins(self):
        self.assertEqual(vt.resolve_tone("texto cualquiera", "calm"), "calm")

    def test_invalid_explicit_falls_back_to_detection(self):
        self.assertEqual(vt.resolve_tone("ALERTA crítica", "inexistente"), "alert")

    def test_none_uses_detection(self):
        self.assertEqual(vt.resolve_tone("Tarea completada"), "success")


class TestParams(unittest.TestCase):
    def test_edge_params_shape(self):
        p = vt.get_edge_params("alert")
        self.assertIn("rate", p)
        self.assertIn("pitch", p)
        self.assertTrue(p["rate"].endswith("%"))
        self.assertTrue(p["pitch"].endswith("Hz"))

    def test_edge_params_unknown_tone_neutral(self):
        self.assertEqual(vt.get_edge_params("xxx"), vt.get_edge_params("neutral"))

    def test_eleven_settings_ranges(self):
        s = vt.get_eleven_settings("humor")
        self.assertTrue(0.0 <= s["stability"] <= 1.0)
        self.assertTrue(0.0 <= s["style"] <= 1.0)

    def test_all_tones_have_complete_config(self):
        for tone, cfg in vt.TONES.items():
            for key in ("rate", "pitch", "stability", "style"):
                self.assertIn(key, cfg, f"{tone} falta {key}")


if __name__ == "__main__":
    unittest.main()
