from langchain.tools import tool
from ddgs import DDGS

@tool("duckduckgo_search", return_direct=True)
def duckduckgo_search_tool(query: str) -> str:
    """
    Perform a web search using DuckDuckGo and return the top 5 results.
    Use this tool when the user asks a question that requires up-to-date information from the internet.
    
    Examples of queries:
    - "Please look up what's the weather like in Paris today?"
    - "Look up the latest tech news"
    - "yes, please search for current AI news"

    Input:
    - A natural language query string.
    """
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, region='wt-wt', safesearch='Moderate', max_results=5)
            results_list = list(results)
    except Exception as e:
        return f"Error al realizar la búsqueda en DuckDuckGo: {str(e)}"

    if not results_list:
        return f"Disculpe señor, no he podido encontrar ningún resultado para: \"{query}\"."

    output = f"Resultados de búsqueda en DuckDuckGo para: \"{query}\"\n\n"
    output += "Fuentes encontradas:\n"
    for index, result in enumerate(results_list, start=1):
        title = result.get("title", "Sin título")
        url = result.get("href", "Sin URL")
        body = result.get("body", "")
        output += (
            f"\n{index}. {title}\n"
            f"   🔗 URL: {url}\n"
            f"   📝 Extracto: {body[:300]}\n"
        )
    return output

