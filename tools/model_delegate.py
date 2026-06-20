import json
import os
from pathlib import Path
from langchain.tools import tool
from core.llm_factory import get_llm
from core.model_logging import log_model_usage
from core.pending_actions import (
  save_pending_action,
  load_pending_action,
  clear_pending_action,
  execute_pending_action,
  PENDING_ACTION_FILE
)

PENDING_MODEL_REQUEST = PENDING_ACTION_FILE


def save_pending_model_request(
  tool_name: str,
  model_env: str,
  model_name: str,
  prompt: str,
) -> None:
  data = {
    "tool_name": tool_name,
    "model_env": model_env,
    "model_name": model_name,
    "prompt": prompt,
  }
  save_pending_action("model", data)

  # Para tests o alertas, notificamos por Telegram si está disponible
  try:
    from core.telegram_bot import send_mfa_request
    send_mfa_request("model", {"model_name": model_name, "prompt": prompt})
  except Exception as e:
    import logging
    logging.error(f"[MFA] Error enviando solicitud MFA para modelo: {e}")


def load_pending_model_request():
  return load_pending_action()


def clear_pending_model_request() -> None:
  clear_pending_action()


def ask_delegated_model(
  tool_name: str,
  model_env: str,
  fallback_model: str,
  prompt: str,
  require_confirmation: bool = False,
) -> str:
  # Determinamos el proveedor
  provider = "openrouter"
  
  # Forzar que JARVIS_MODEL_THINK use google_ai_studio (requisito 3)
  if model_env == "JARVIS_MODEL_THINK":
    provider = "google_ai_studio"
  else:
    # Si hay una variable de entorno JARVIS_<SUFFIX>_PROVIDER
    suffix = model_env.replace("JARVIS_MODEL_", "") if model_env else ""
    provider_env = os.getenv(f"JARVIS_{suffix}_PROVIDER") or os.getenv(f"{model_env}_PROVIDER")
    if provider_env:
      provider = provider_env.lower()

  model = os.getenv(model_env, fallback_model)

  if require_confirmation:
    save_pending_model_request(
      tool_name=tool_name,
      model_env=model_env,
      model_name=model,
      prompt=prompt,
    )

    return (
      f"Para esta tarea usaría el modelo {model} ({provider}). "
      "Es un modelo de coste alto. "
      "Si quieres ejecutarlo, di: confirmo modelo. "
      "Si no, di: cancela modelo."
    )

  prompt_tokens = 0
  completion_tokens = 0

  try:
    if provider == "google_ai_studio":
      api_key = os.getenv("GOOGLE_API_KEY")
      if not api_key:
        return "No GOOGLE_API_KEY found in .env"
      from google import genai
      client = genai.Client(api_key=api_key)
      response = client.models.generate_content(
        model=model,
        contents=prompt,
      )
      
      if hasattr(response, 'usage_metadata') and response.usage_metadata:
        prompt_tokens = response.usage_metadata.prompt_token_count or 0
        completion_tokens = response.usage_metadata.candidates_token_count or 0

      log_model_usage(
        tool_name=tool_name,
        model_name=model,
        prompt=prompt,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider=provider
      )
      return response.text
    else:
      api_key = os.getenv("OPENROUTER_API_KEY")
      if not api_key:
        return "No OPENROUTER_API_KEY found in .env"
      
      from langchain_community.callbacks import get_openai_callback
      llm = get_llm(model, temperature=0.2)
      
      with get_openai_callback() as cb:
        response = llm.invoke(prompt)
        prompt_tokens = cb.prompt_tokens
        completion_tokens = cb.completion_tokens
        
      log_model_usage(
        tool_name=tool_name,
        model_name=model,
        prompt=prompt,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider=provider
      )
      return response.content
  except Exception as e:
    log_model_usage(
      tool_name=tool_name,
      model_name=model,
      prompt=prompt,
      prompt_tokens=0,
      completion_tokens=0,
      provider=provider
    )
    return f"Error al invocar {provider} ({model}): {str(e)}"

# Alias compatible por si se sigue llamando ask_openrouter_model en otros archivos
def ask_openrouter_model(
  tool_name: str,
  model_env: str,
  fallback_model: str,
  prompt: str,
  require_confirmation: bool = False,
) -> str:
  return ask_delegated_model(tool_name, model_env, fallback_model, prompt, require_confirmation)

@tool
def ask_reasoning_model(prompt: str) -> str:
  """
  Delegate to a reasoning model.
  Use this for complex reasoning, comparisons, debugging ideas, planning, or when the user asks to think carefully.
  Do not use this for simple commands.
  """
  return ask_delegated_model(
    tool_name="ask_reasoning_model",
    model_env="JARVIS_MODEL_THINK",
    fallback_model="gemini-3.5-flash",
    prompt=prompt,
  )


@tool
def ask_code_model(prompt: str) -> str:
  """
  Delegate to a coding model.
  Use this for Python, errors, refactoring, project structure, tools, Git, APIs, or programming tasks.
  Do not use this for normal conversation.
  """
  return ask_delegated_model(
    tool_name="ask_code_model",
    model_env="JARVIS_MODEL_CODE",
    fallback_model="anthropic/claude-sonnet-4.6",
    prompt=prompt,
  )


@tool
def ask_agent_model(prompt: str) -> str:
  """
  Delegate to an agent/productivity model.
  Use this for multi-step tasks, workflows, tool planning, task organization, or assistant-like execution plans.
  Do not use this for simple questions.
  """
  return ask_delegated_model(
    tool_name="ask_agent_model",
    model_env="JARVIS_MODEL_AGENT",
    fallback_model="minimax/minimax-m2.7",
    prompt=prompt,
  )


@tool
def ask_pro_model(prompt: str) -> str:
  """
  Delegate to the expensive pro model (GPT-5.5).
  Use this only if the user explicitly asks for modo pro, Kimi, or maximum quality.
  This model requires confirmation before execution.
  """
  require_confirm = os.getenv("JARVIS_REQUIRE_CONFIRM_PRO", "True").lower() == "true"
  return ask_delegated_model(
    tool_name="ask_pro_model",
    model_env="JARVIS_MODEL_PRO",
    fallback_model="openai/gpt-5.5",
    prompt=prompt,
    require_confirmation=require_confirm,
  )


@tool
def ask_ultra_model(prompt: str) -> str:
  """
  Delegate to the ultra expensive model (GPT-5.5 Pro).
  Use this only for extreme cases, very hard problems, or complex tasks.
  This model requires confirmation before execution.
  """
  require_confirm = os.getenv("JARVIS_REQUIRE_CONFIRM_ULTRA", "True").lower() == "true"
  return ask_delegated_model(
    tool_name="ask_ultra_model",
    model_env="JARVIS_MODEL_ULTRA",
    fallback_model="openai/gpt-5.5-pro",
    prompt=prompt,
    require_confirmation=require_confirm,
  )


@tool
def ask_gpt_model(prompt: str) -> str:
  """
  Delegate to GPT.
  Use this only if the user explicitly asks to use GPT.
  This model requires confirmation before execution.
  """
  lower_prompt = prompt.lower()
  if "pro" in lower_prompt or "ultra" in lower_prompt or "gpt-5.5-pro" in lower_prompt:
    return ask_ultra_model(prompt)
  else:
    return ask_pro_model(prompt)


@tool
def confirm_pending_action(prompt: str) -> str:
  """
  Confirm and execute any pending action (dangerous commands, critical file writes, model execution, dynamic tools).
  Use this when the user says: confirma, adelante, sí, ejecuta, confirmo acción.
  """
  return execute_pending_action()


@tool
def cancel_pending_action(prompt: str) -> str:
  """
  Cancel any pending action (dangerous commands, file writes, model execution, dynamic tools).
  Use this when the user says: cancela, no, no lo hagas, cancela acción.
  """
  pending = load_pending_action()
  if not pending:
    return "No hay ninguna acción pendiente de cancelar."
    
  action_type = pending.get("action_type")
  clear_pending_action()
  
  desc = f"acción de tipo '{action_type}'"
  if action_type == "model":
    model_name = pending.get("model_name", "modelo")
    desc = f"uso del modelo {model_name}"
  elif action_type == "terminal":
    desc = "comando de terminal"
  elif action_type == "file_write":
    desc = "escritura de archivo"
  elif action_type == "tool_creation":
    desc = "creación de herramienta dinámica"
    
  return f"Cancelado. Se canceló la ejecución de: {desc}."


@tool
def confirm_pending_model(prompt: str) -> str:
  """
  Confirm and execute the pending expensive model request OR pending action.
  Use this when the user says: confirma, adelante, sí, ejecuta, confirmo modelo.
  """
  pending_command_file = Path("logs/pending_terminal_command.json")
  if pending_command_file.exists():
    try:
      data = json.loads(pending_command_file.read_text(encoding="utf-8"))
      command = data.get("command")
      pending_command_file.unlink()
      if command:
        from tools.terminal import execute_cmd
        return execute_cmd(command)
    except Exception:
      pass

  return execute_pending_action()


@tool
def cancel_pending_model(prompt: str) -> str:
  """
  Cancel the pending expensive model request or pending action.
  Use this when the user says: cancela, no, no lo hagas, cancela modelo.
  """
  cancelled_actions = []
  
  pending_command_file = Path("logs/pending_terminal_command.json")
  if pending_command_file.exists():
    try:
      pending_command_file.unlink()
      cancelled_actions.append("comando de terminal")
    except Exception:
      pass

  pending = load_pending_action()
  if pending:
    action_type = pending.get("action_type")
    clear_pending_action()
    if action_type == "model":
      model_name = pending.get("model_name", "modelo")
      cancelled_actions.append(f"uso del modelo {model_name}")
    elif action_type == "terminal":
      cancelled_actions.append("comando de terminal")
    elif action_type == "file_write":
      cancelled_actions.append("escritura de archivo")
    elif action_type == "tool_creation":
      cancelled_actions.append("creación de herramienta dinámica")
    else:
      cancelled_actions.append(f"acción de tipo '{action_type}'")

  if cancelled_actions:
    return f"Cancelado. Se canceló la ejecución de: {', '.join(cancelled_actions)}."
  return "No había ninguna acción pendiente de cancelar."