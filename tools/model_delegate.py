import json
import os
from datetime import datetime
from pathlib import Path
from langchain.tools import tool
from langchain_openai import ChatOpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PENDING_MODEL_REQUEST = Path("logs/pending_model_request.json")


def log_model_use(tool_name: str, model_name: str, prompt: str) -> None:
  logs_dir = Path("logs")
  logs_dir.mkdir(exist_ok=True)

  short_prompt = prompt.replace("\n", " ")[:120]

  with open(logs_dir / "model_usage.log", "a", encoding="utf-8") as file:
    file.write(
      f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
      f"{tool_name} | {model_name} | {short_prompt}\n"
    )


def save_pending_model_request(
  tool_name: str,
  model_env: str,
  model_name: str,
  prompt: str,
) -> None:
  logs_dir = Path("logs")
  logs_dir.mkdir(exist_ok=True)

  data = {
    "tool_name": tool_name,
    "model_env": model_env,
    "model_name": model_name,
    "prompt": prompt,
  }

  PENDING_MODEL_REQUEST.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8",
  )


def load_pending_model_request():
  if not PENDING_MODEL_REQUEST.exists():
    return None

  return json.loads(PENDING_MODEL_REQUEST.read_text(encoding="utf-8"))


def clear_pending_model_request() -> None:
  if PENDING_MODEL_REQUEST.exists():
    PENDING_MODEL_REQUEST.unlink()


def ask_openrouter_model(
  tool_name: str,
  model_env: str,
  fallback_model: str,
  prompt: str,
  require_confirmation: bool = False,
) -> str:
  api_key = os.getenv("OPENROUTER_API_KEY")

  if not api_key:
    return "No OPENROUTER_API_KEY found in .env"

  model = os.getenv(model_env, fallback_model)

  if require_confirmation:
    save_pending_model_request(
      tool_name=tool_name,
      model_env=model_env,
      model_name=model,
      prompt=prompt,
    )

    return (
      f"Para esta tarea usaría el modelo {model}. "
      "Es un modelo de coste alto. "
      "Si quieres ejecutarlo, di: confirmo modelo. "
      "Si no, di: cancela modelo."
    )

  log_model_use(tool_name, model, prompt)

  llm = ChatOpenAI(
    model=model,
    base_url=OPENROUTER_BASE_URL,
    api_key=api_key,
    temperature=0.2,
  )

  response = llm.invoke(prompt)
  return response.content

@tool
def ask_reasoning_model(prompt: str) -> str:
  """
  Delegate to a reasoning model.
  Use this for complex reasoning, comparisons, debugging ideas, planning, or when the user asks to think carefully.
  Do not use this for simple commands.
  """
  return ask_openrouter_model(
    tool_name="ask_reasoning_model",
    model_env="JARVIS_MODEL_THINK",
    fallback_model="qwen/qwen3-30b-a3b-thinking-2507",
    prompt=prompt,
  )


@tool
def ask_code_model(prompt: str) -> str:
  """
  Delegate to a coding model.
  Use this for Python, errors, refactoring, project structure, tools, Git, APIs, or programming tasks.
  Do not use this for normal conversation.
  """
  return ask_openrouter_model(
    tool_name="ask_code_model",
    model_env="JARVIS_MODEL_CODE",
    fallback_model="qwen/qwen3-coder-next",
    prompt=prompt,
  )


@tool
def ask_agent_model(prompt: str) -> str:
  """
  Delegate to an agent/productivity model.
  Use this for multi-step tasks, workflows, tool planning, task organization, or assistant-like execution plans.
  Do not use this for simple questions.
  """
  return ask_openrouter_model(
    tool_name="ask_agent_model",
    model_env="JARVIS_MODEL_AGENT",
    fallback_model="minimax/minimax-m2.7",
    prompt=prompt,
  )


@tool
def ask_pro_model(prompt: str) -> str:
  """
  Delegate to the expensive pro model.
  Use this only if the user explicitly asks for modo pro, Kimi, or maximum quality.
  This model requires confirmation before execution.
  """
  return ask_openrouter_model(
    tool_name="ask_pro_model",
    model_env="JARVIS_MODEL_PRO",
    fallback_model="moonshotai/kimi-k2.6",
    prompt=prompt,
    require_confirmation=True,
  )


@tool
def ask_gpt_model(prompt: str) -> str:
  """
  Delegate to GPT.
  Use this only if the user explicitly asks to use GPT.
  This model requires confirmation before execution.
  """
  return ask_openrouter_model(
    tool_name="ask_gpt_model",
    model_env="JARVIS_MODEL_GPT",
    fallback_model="openai/gpt-5.4-mini",
    prompt=prompt,
    require_confirmation=True,
  )


@tool
def confirm_pending_model(prompt: str) -> str:
  """
  Confirm and execute the pending expensive model request.
  Use this when the user says: confirmo modelo, confirma, adelante, sí, ejecuta.
  """
  pending = load_pending_model_request()

  if not pending:
    return "No hay ninguna delegación pendiente de confirmar."

  clear_pending_model_request()

  return ask_openrouter_model(
    tool_name=pending["tool_name"],
    model_env=pending["model_env"],
    fallback_model=pending["model_name"],
    prompt=pending["prompt"],
    require_confirmation=False,
  )


@tool
def cancel_pending_model(prompt: str) -> str:
  """
  Cancel the pending expensive model request.
  Use this when the user says: cancela modelo, no, cancela, no lo uses.
  """
  pending = load_pending_model_request()

  if not pending:
    return "No había ningún modelo pendiente de cancelar."

  model_name = pending["model_name"]
  clear_pending_model_request()

  return f"Cancelado. No se ha usado {model_name}."