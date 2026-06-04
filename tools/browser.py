from langchain.tools import tool
import webbrowser

@tool
def open_website(url: str) -> str:
    """Opens a website in the default browser. Use when the user asks to open a webpage like YouTube, Gmail, Google, etc."""
    webbrowser.open(url)
    return f"Abriendo {url}"