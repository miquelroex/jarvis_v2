import sys
import os
import unittest
import json
from pathlib import Path
from datetime import datetime

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.model_logging import (
    log_model_usage,
    estimate_cost,
    get_daily_usage
)

class TestModelUsageLogging(unittest.TestCase):
    def setUp(self):
        self.log_path = Path("logs/model_usage.log")
        self.log_backup = None
        
        # Copia de seguridad del log real si existe
        if self.log_path.exists():
            try:
                self.log_backup = self.log_path.read_text(encoding="utf-8")
                self.log_path.unlink()
            except Exception:
                pass
        else:
            Path("logs").mkdir(exist_ok=True)

    def tearDown(self):
        # Eliminar log temporal del test
        if self.log_path.exists():
            try:
                self.log_path.unlink()
            except Exception:
                pass
                
        # Restaurar log real
        if self.log_backup is not None:
            try:
                self.log_path.write_text(self.log_backup, encoding="utf-8")
            except Exception:
                pass

    def test_estimate_cost(self):
        # Deepseek chat
        cost_ds = estimate_cost("deepseek/deepseek-v4-pro", 1000, 2000)
        # prompt cost: (1000/1M) * 0.14 = 0.00014
        # completion cost: (2000/1M) * 0.28 = 0.00056
        # total: 0.0007
        self.assertAlmostEqual(cost_ds, 0.0007, places=6)

        # Gemini
        cost_gemini = estimate_cost("google/gemini-3.5-flash", 10000, 5000)
        # prompt: (10k/1M) * 0.075 = 0.00075
        # completion: (5k/1M) * 0.30 = 0.0015
        # total: 0.00225
        self.assertAlmostEqual(cost_gemini, 0.00225, places=6)

        # Fallback
        cost_unknown = estimate_cost("unknown-model", 1000, 1000)
        # prompt: (1k/1M) * 0.50 = 0.0005
        # completion: (1k/1M) * 1.50 = 0.0015
        # total: 0.002
        self.assertAlmostEqual(cost_unknown, 0.002, places=6)

    def test_log_model_usage_json_writing(self):
        log_model_usage(
            tool_name="test_tool",
            model_name="deepseek/deepseek-v4-pro",
            prompt="Hola mundo",
            prompt_tokens=100,
            completion_tokens=200,
            provider="openrouter"
        )

        self.assertTrue(self.log_path.exists())
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)

        # Validar JSON
        data = json.loads(lines[0])
        self.assertEqual(data["tool_name"], "test_tool")
        self.assertEqual(data["model_name"], "deepseek/deepseek-v4-pro")
        self.assertEqual(data["prompt_tokens"], 100)
        self.assertEqual(data["completion_tokens"], 200)
        self.assertEqual(data["total_tokens"], 300)
        self.assertEqual(data["provider"], "openrouter")
        self.assertTrue(data["cost"] > 0)

    def test_get_daily_usage(self):
        # 1. Registrar logs del día de hoy
        log_model_usage(
            tool_name="tool_1",
            model_name="deepseek/deepseek-v4-pro",
            prompt="P1",
            prompt_tokens=1000,
            completion_tokens=1000
        )
        log_model_usage(
            tool_name="tool_2",
            model_name="openai/gpt-5.5",
            prompt="P2",
            prompt_tokens=2000,
            completion_tokens=4000
        )

        # 2. Registrar un log simulado de ayer (modificamos la fecha en el archivo)
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        log_data_yesterday = {
            "timestamp": "2025-01-01 12:00:00",
            "tool_name": "old_tool",
            "model_name": "deepseek-chat",
            "prompt": "Old prompt",
            "prompt_tokens": 50000,
            "completion_tokens": 50000,
            "total_tokens": 100000,
            "cost": 1.0,
            "provider": "openrouter"
        }
        
        # Reescribir agregando la de ayer
        with open(self.log_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
            f.write(json.dumps(log_data_yesterday) + "\n")

        usage = get_daily_usage()
        
        # Deben sumarse sólo las de hoy (2 llamadas)
        self.assertEqual(usage["calls"], 2)
        # Tokens hoy: 2000 (1000+1000) + 6000 (2000+4000) = 8000
        self.assertEqual(usage["tokens"], 8000)
        
        # Coste hoy:
        # deepseek cost: 1000/1M * 0.14 + 1000/1M * 0.28 = 0.00014 + 0.00028 = 0.00042
        # gpt5 cost: 2000/1M * 5.00 + 4000/1M * 15.00 = 0.0100 + 0.0600 = 0.0700
        # total: 0.07042
        self.assertAlmostEqual(usage["cost"], 0.07042, places=6)

    def test_get_daily_usage_computes_avg_latency(self):
        # Escribimos el log directamente (sin log_model_usage) para evitar el
        # import de gui.app durante los tests.
        today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entries = [
            {"timestamp": today, "total_tokens": 20, "cost": 0.0, "latency_ms": 200},
            {"timestamp": today, "total_tokens": 20, "cost": 0.0, "latency_ms": 400},
            {"timestamp": today, "total_tokens": 20, "cost": 0.0, "latency_ms": None},
        ]
        with open(self.log_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        usage = get_daily_usage()
        self.assertEqual(usage["calls"], 3)
        # Media solo de las que tienen latencia: (200 + 400) / 2 = 300
        self.assertEqual(usage["avg_latency_ms"], 300)

    def test_get_daily_usage_avg_latency_none_when_absent(self):
        today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": today, "total_tokens": 10, "cost": 0.0}) + "\n")
        usage = get_daily_usage()
        self.assertIsNone(usage["avg_latency_ms"])


if __name__ == "__main__":
    unittest.main()
