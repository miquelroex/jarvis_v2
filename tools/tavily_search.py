import os

from langchain.tools import tool
from tavily import TavilyClient


@tool
def tavily_search(query: str) -> str:
  """
  Search the web using Tavily.
  Use this for current information, research, news, prices, documentation,
  comparisons, or anything that needs reliable web sources.
  """
  api_key = os.getenv("TAVILY_API_KEY")

  if not api_key:
    return "No TAVILY_API_KEY found in .env. Use duckduckgo_search as fallback."

  client = TavilyClient(api_key=api_key)

  response = client.search(
    query=query,
    search_depth="advanced",
    max_results=5,
    include_answer=True,
    include_raw_content=False,
  )

  answer = response.get("answer", "")
  results = response.get("results", [])

  output = f"Búsqueda Tavily para: {query}\n\n"

  if answer:
    output += f"Resumen:\n{answer}\n\n"

  output += "Fuentes:\n"

  for index, result in enumerate(results, start=1):
    title = result.get("title", "Sin título")
    url = result.get("url", "Sin URL")
    content = result.get("content", "")

    output += (
      f"\n{index}. {title}\n"
      f"URL: {url}\n"
      f"Extracto: {content[:500]}\n"
    )

  return output