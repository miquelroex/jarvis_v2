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

  logs_dir = Path("logs")
  logs_dir.mkdir(exist_ok=True)

  short_prompt = prompt.replace("\n", " ")[:120]

  with open(logs_dir / "model_usage.log", "a", encoding="utf-8") as file:
    file.write(
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    f"ask_gemini | {model} | {short_prompt}\n"
  )

  if not api_key:
    return "No GOOGLE_API_KEY found in .env"

  client = genai.Client(api_key=api_key)

  response = client.models.generate_content(
    model=model,
    contents=prompt,
  )

  return response.text