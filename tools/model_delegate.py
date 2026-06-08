import json
import os
from pathlib import Path
from langchain.tools import tool
from core.llm_factory import get_llm
from core.model_logging import log_model_usage

PENDING_MODEL_REQUEST = Path("logs/pending_model_request.json")


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

  try:
    from core.telegram_bot import send_mfa_request
    send_mfa_request("model", {"model_name": model_name, "prompt": prompt})
  except Exception as e:
    import logging
    logging.error(f"[MFA] Error enviando solicitud MFA para modelo: {e}")


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

  log_model_usage(tool_name, model, prompt)

  try:
    llm = get_llm(model, temperature=0.2)
    response = llm.invoke(prompt)
    return response.content
  except Exception as e:
    return f"Error al invocar OpenRouter ({model}): {str(e)}"

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
    fallback_model="qwen/qwen3.7-plus",
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
    fallback_model="qwen/qwen3-coder",
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
  Confirm and execute the pending expensive model request OR pending terminal command.
  Use this when the user says: confirma, adelante, sí, ejecuta, confirmo modelo.
  """
  pending_command_file = Path("logs/pending_terminal_command.json")
  
  # 1. Comprobar si hay un comando de terminal pendiente
  if pending_command_file.exists():
    try:
      data = json.loads(pending_command_file.read_text(encoding="utf-8"))
      command = data.get("command")
      # Borrar el archivo
      pending_command_file.unlink()
      
      if not command:
        return "No se encontró ningún comando en la solicitud de terminal pendiente."
        
      # Ejecutar el comando
      from tools.terminal import execute_cmd
      return execute_cmd(command)
    except Exception as e:
      if pending_command_file.exists():
        try:
          pending_command_file.unlink()
        except Exception:
          pass
      return f"Error al confirmar el comando de terminal: {str(e)}"

  # 2. Comprobar si hay una solicitud de modelo costoso pendiente
  pending = load_pending_model_request()

  if not pending:
    return "No hay ninguna acción pendiente de confirmar."

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
  Cancel the pending expensive model request or pending terminal command.
  Use this when the user says: cancela, no, no lo hagas, cancela modelo.
  """
  pending_command_file = Path("logs/pending_terminal_command.json")
  cancelled_actions = []

  # 1. Cancelar comando de terminal pendiente
  if pending_command_file.exists():
    try:
      pending_command_file.unlink()
      cancelled_actions.append("comando de terminal")
    except Exception:
      pass

  # 2. Cancelar modelo pendiente
  pending = load_pending_model_request()
  if pending:
    model_name = pending["model_name"]
    clear_pending_model_request()
    cancelled_actions.append(f"uso del modelo {model_name}")

  if not cancelled_actions:
    return "No había ninguna acción pendiente de cancelar."

  return f"Cancelado. Se canceló la ejecución de: {', '.join(cancelled_actions)}."