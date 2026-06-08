import os
from langchain_openai import ChatOpenAI

def get_llm(model_name: str = None, temperature: float = 0.2) -> ChatOpenAI:
    """
    Crea y devuelve una instancia de ChatOpenAI configurada para OpenRouter.
    Si model_name es None, utiliza el modelo configurado por defecto en la variable
    de entorno JARVIS_MODEL_DEFAULT (o deepseek/deepseek-v4-pro como fallback).
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("No se encontro la variable OPENROUTER_API_KEY en el entorno.")

    if not model_name:
        model_name = os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v4-pro")

    return ChatOpenAI(
        model=model_name,
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        temperature=temperature
    )
