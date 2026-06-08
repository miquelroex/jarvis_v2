from langchain.tools import tool
from core.api_sentinel import check_all_apis_status

@tool
def check_api_status(query: str = "") -> str:
    """
    Checks the status of external APIs (GitHub, OpenAI, Gemini) and returns a summary.
    Use this tool when the user asks about API health, status page, or if APIs are down.
    """
    status = check_all_apis_status()
    summary = "📊 *Estado de las APIs Externas*:\n\n"
    for api, info in status.items():
        state = info["status"].upper()
        desc = info["description"]
        icon = "🟢"
        if state in ("MINOR", "MAJOR", "CRITICAL"):
            icon = "🔴" if state == "CRITICAL" else "🟡"
        elif state == "UNKNOWN":
            icon = "⚪"
        summary += f"{icon} *{api}*: {state} - {desc}\n"
    return summary
