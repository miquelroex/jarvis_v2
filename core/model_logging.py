import os
import json
from datetime import datetime
from pathlib import Path

def estimate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calcula el coste aproximado de una llamada al LLM en USD.
    Retorna el coste como un float de alta precisión.
    """
    # Precios por millón de tokens (Input, Output) en USD
    PRICES = {
        # DeepSeek
        "deepseek/deepseek-v4-pro": (0.14, 0.28),
        "deepseek-chat": (0.14, 0.28),
        # Gemini
        "gemini-2.5-flash": (0.075, 0.30),
        "gemini-3.5-flash": (0.075, 0.30),
        "gemini-2.5-pro": (1.25, 5.00),
        # Claude
        "anthropic/claude-3.5-sonnet": (3.00, 15.00),
        "anthropic/claude-3.5-sonnet:beta": (3.00, 15.00),
        "claude-sonnet-4.6": (3.00, 15.00),
        # GPT-4o / GPT-5
        "openai/gpt-4o": (2.50, 10.00),
        "openai/gpt-5.5": (5.00, 15.00),
        "openai/gpt-5.5-pro": (15.00, 75.00),
        # Minimax
        "minimax/minimax-m2.7": (0.10, 0.20),
    }

    # Buscar por coincidencia parcial si no está exacta
    matched_price = None
    for key, val in PRICES.items():
        if key in model_name:
            matched_price = val
            break

    if not matched_price:
        # Fallback genérico para modelos desconocidos de coste medio
        matched_price = (0.50, 1.50)

    input_cost = (prompt_tokens / 1_000_000) * matched_price[0]
    output_cost = (completion_tokens / 1_000_000) * matched_price[1]
    return input_cost + output_cost

def get_daily_usage() -> dict:
    """
    Calcula los tokens totales y el coste total acumulado el día de hoy.
    """
    log_path = Path("logs/model_usage.log")
    total_calls = 0
    total_tokens = 0
    total_cost = 0.0
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    if line_str.startswith("{"):
                        try:
                            data = json.loads(line_str)
                            if data.get("timestamp", "").startswith(today_str):
                                total_calls += 1
                                total_tokens += data.get("total_tokens", 0)
                                total_cost += data.get("cost", 0.0)
                        except Exception:
                            pass
                    else:
                        parts = [p.strip() for p in line_str.split(" | ", 3)]
                        if len(parts) >= 3:
                            if parts[0].startswith(today_str):
                                total_calls += 1
        except Exception as e:
            print(f"[Model Logging] Error al calcular uso diario: {e}")
            
    return {
        "calls": total_calls,
        "tokens": total_tokens,
        "cost": total_cost
    }

def log_model_usage(
    tool_name: str,
    model_name: str,
    prompt: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost: float = 0.0,
    provider: str = "openrouter"
) -> None:
    """
    Registra el uso de modelos en el archivo logs/model_usage.log.
    Soporta formato JSON estructurado con conteo de tokens y costes en USD.
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    short_prompt = prompt.replace("\n", " ")[:120]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Si no se pasó coste pero tenemos tokens, lo calculamos
    if cost == 0.0 and (prompt_tokens > 0 or completion_tokens > 0):
        cost = estimate_cost(model_name, prompt_tokens, completion_tokens)

    # Datos estructurados en JSON
    log_data = {
        "timestamp": timestamp,
        "tool_name": tool_name,
        "model_name": model_name,
        "prompt": short_prompt,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost": cost,
        "provider": provider
    }

    # Escribir en formato JSON Line (un JSON por línea)
    with open(logs_dir / "model_usage.log", "a", encoding="utf-8") as file:
        file.write(json.dumps(log_data, ensure_ascii=False) + "\n")

    # Emitir evento de log a la GUI en tiempo real
    try:
        from gui.app import socketio, jarvis_state
        jarvis_state["model"] = model_name
        socketio.emit("new_model_log", log_data)
        socketio.emit("daily_usage_update", get_daily_usage())
        socketio.emit('state_update', jarvis_state)
    except Exception:
        pass
