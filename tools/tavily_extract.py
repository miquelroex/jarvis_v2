import os
from langchain.tools import tool
from tavily import TavilyClient


@tool
def tavily_extract_url(url: str) -> str:
  """
  Extract readable content from a specific URL using Tavily.
  Use this when the user gives a link and asks to read, summarize, analyze,
  compare, explain, or extract information from that page.
  """
  api_key = os.getenv("TAVILY_API_KEY")

  if not api_key:
    return "No TAVILY_API_KEY found in .env."

  client = TavilyClient(api_key=api_key)

  try:
    response = client.extract(
      urls=url,
      extract_depth="basic",
      include_images=False,
      format="markdown",
      timeout=20,
    )
  except Exception as error:
    return f"No he podido extraer el contenido de la URL: {error}"

  results = response.get("results", [])
  failed_results = response.get("failed_results", [])

  if not results:
    return (
      "No he podido extraer contenido útil de esa URL.\n"
      f"Fallos: {failed_results}"
    )

  result = results[0]
  raw_content = result.get("raw_content", "")

  if not raw_content:
    return "La URL se ha leído, pero no ha devuelto contenido útil."

  clean_content = raw_content[:6000]

  return (
    f"Contenido extraído de:\n{url}\n\n"
    f"{clean_content}\n\n"
    "Nota: contenido recortado a 6000 caracteres para no saturar el contexto."
  )