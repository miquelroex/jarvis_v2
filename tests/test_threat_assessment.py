"""Tests de la Evaluación de Amenaza Narrada (core/threat_assessment.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.threat_assessment as ta


class TestRiskFromScore(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(ta._risk_from_score(95), "bajo")
        self.assertEqual(ta._risk_from_score(80), "bajo")
        self.assertEqual(ta._risk_from_score(60), "moderado")
        self.assertEqual(ta._risk_from_score(40), "alto")
        self.assertEqual(ta._risk_from_score(10), "crítico")


class TestAssess(unittest.TestCase):
    def test_all_good_high_score(self):
        a = ta.assess({"ram_percent": 20, "tests_failing": 0, "threat_level": "green", "dirty_count": 0})
        self.assertGreaterEqual(a["score"], 90)
        self.assertEqual(a["risk"], "bajo")
        self.assertEqual(a["reasons"], [])

    def test_critical_ram_penalizes(self):
        a = ta.assess({"ram_percent": 95})
        self.assertLess(a["score"], 80)
        self.assertIn("memoria crítica", a["reasons"])

    def test_failing_tests_penalize(self):
        a = ta.assess({"tests_failing": 3})
        self.assertIn("3 suite(s) de pruebas fallando", a["reasons"])
        self.assertLessEqual(a["score"], 95 - 24)

    def test_danger_command_big_penalty(self):
        a = ta.assess({"command_risk": "danger"})
        self.assertEqual(a["score"], 60)  # 95 - 35
        self.assertIn("comando peligroso", a["reasons"])

    def test_threat_red(self):
        a = ta.assess({"threat_level": "red"})
        self.assertIn("nivel de amenaza elevado", a["reasons"])

    def test_score_clamped(self):
        a = ta.assess({"ram_percent": 99, "tests_failing": 9, "threat_level": "violet",
                       "dirty_count": 99, "command_risk": "danger"})
        self.assertGreaterEqual(a["score"], 5)
        self.assertEqual(a["risk"], "crítico")

    def test_dirty_thresholds(self):
        self.assertIn("cambios sin confirmar", ta.assess({"dirty_count": 25})["reasons"])
        self.assertIn("muchos cambios sin confirmar", ta.assess({"dirty_count": 60})["reasons"])


class TestNarrate(unittest.TestCase):
    def test_includes_score_and_risk(self):
        line = ta.narrate_assessment({"ram_percent": 20})
        self.assertIn("Probabilidad de éxito", line)
        self.assertIn("Riesgo: bajo", line)

    def test_low_risk_omits_factors(self):
        line = ta.narrate_assessment({"ram_percent": 20})
        self.assertNotIn("Factores", line)

    def test_high_risk_lists_factors(self):
        line = ta.narrate_assessment({"ram_percent": 95, "threat_level": "red"})
        self.assertIn("Factores", line)


class TestGather(unittest.TestCase):
    def test_get_assessment_uses_context(self):
        with patch.object(ta, "_gather_context", return_value={"ram_percent": 20}):
            r = ta.get_assessment()
        self.assertIn("Riesgo: bajo", r)


if __name__ == "__main__":
    unittest.main()
