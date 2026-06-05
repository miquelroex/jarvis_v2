import os
from langchain.tools import tool
from langchain_openai import ChatOpenAI


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def ask_openrouter_model(model_env: str, fallback_model: str, prompt: str) -> str:
  api_key = os.getenv("OPENROUTER_API_KEY")

  if not api_key:
    return "No OPENROUTER_API_KEY found in .env"

  model = os.getenv(model_env, fallback_model)

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
    "JARVIS_MODEL_THINK",
    "qwen/qwen3-30b-a3b-thinking-2507",
    prompt,
  )


@tool
def ask_code_model(prompt: str) -> str:
  """
  Delegate to a coding model.
  Use this for Python, errors, refactoring, project structure, tools, Git, APIs, or programming tasks.
  Do not use this for normal conversation.
  """
  return ask_openrouter_model(
    "JARVIS_MODEL_CODE",
    "qwen/qwen3-coder-next",
    prompt,
  )


@tool
def ask_agent_model(prompt: str) -> str:
  """
  Delegate to an agent/productivity model.
  Use this for multi-step tasks, workflows, tool planning, task organization, or assistant-like execution plans.
  Do not use this for simple questions.
  """
  return ask_openrouter_model(
    "JARVIS_MODEL_AGENT",
    "minimax/minimax-m2.7",
    prompt,
  )


@tool
def ask_pro_model(prompt: str) -> str:
  """
  Delegate to the expensive pro model.
  Use this only if the user explicitly asks for modo pro, Kimi, or maximum quality.
  Never use this automatically for normal tasks.
  """
  return ask_openrouter_model(
    "JARVIS_MODEL_PRO",
    "moonshotai/kimi-k2.6",
    prompt,
  )


@tool
def ask_gpt_model(prompt: str) -> str:
  """
  Delegate to GPT.
  Use this only if the user explicitly asks to use GPT.
  Never use this automatically for normal tasks.
  """
  return ask_openrouter_model(
    "JARVIS_MODEL_GPT",
    "openai/gpt-5.4-mini",
    prompt,
  )