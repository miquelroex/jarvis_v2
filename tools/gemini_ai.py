import os
from google import genai
from langchain.tools import tool
from datetime import datetime
from pathlib import Path


@tool
def ask_gemini(prompt: str) -> str:
  """
  Use Gemini through Google AI Studio.
  Use this only when the user explicitly asks to use Gemini.
  """
  api_key = os.getenv("GOOGLE_API_KEY")
  model = os.getenv("JARVIS_MODEL_GEMINI", "gemini-3.5-flash")

  from core.model_logging import log_model_usage

  if not api_key:
    return "No GOOGLE_API_KEY found in .env"

  prompt_tokens = 0
  completion_tokens = 0

  try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
      model=model,
      contents=prompt,
    )
    
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
      prompt_tokens = response.usage_metadata.prompt_token_count or 0
      completion_tokens = response.usage_metadata.candidates_token_count or 0
      
    log_model_usage(
      tool_name="ask_gemini",
      model_name=model,
      prompt=prompt,
      prompt_tokens=prompt_tokens,
      completion_tokens=completion_tokens,
      provider="google_ai_studio"
    )
    return response.text
  except Exception as e:
    log_model_usage(
      tool_name="ask_gemini",
      model_name=model,
      prompt=prompt,
      prompt_tokens=0,
      completion_tokens=0,
      provider="google_ai_studio"
    )
    raise