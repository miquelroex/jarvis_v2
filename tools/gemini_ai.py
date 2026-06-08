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
  log_model_usage("ask_gemini", model, prompt)

  if not api_key:
    return "No GOOGLE_API_KEY found in .env"

  client = genai.Client(api_key=api_key)

  response = client.models.generate_content(
    model=model,
    contents=prompt,
  )

  return response.text