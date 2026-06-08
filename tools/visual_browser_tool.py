import os
from langchain.tools import tool
from core.visual_browser import browser_manager, SCREENSHOT_PATH

def get_screenshot_markdown() -> str:
    """Returns markdown string embedding the absolute path of the browser screenshot."""
    abs_path = os.path.abspath(SCREENSHOT_PATH).replace("\\", "/")
    return f"\n\n![Vista del Navegador](file:///{abs_path}?t={os.path.getmtime(SCREENSHOT_PATH) if os.path.exists(SCREENSHOT_PATH) else 0})"

@tool
def web_browser_navigate(url: str) -> str:
    """
    Opens a Chromium browser session in the background and navigates to the specified URL.
    It injects visual numbered overlays on all clickable elements.
    Use this tool when the user asks to browse a website, search something on Google, or open a webpage.
    """
    try:
        status = browser_manager.navigate_to(url)
        return f"{status}{get_screenshot_markdown()}"
    except Exception as e:
        return f"Error al iniciar/navegar en el navegador: {e}"

@tool
def web_browser_click(element_id: int) -> str:
    """
    Clicks the interactive element identified by the numerical ID/index overlay (e.g. 0, 1, 2).
    Use this tool to click links, submit buttons, check checkboxes, etc. visible on the screenshot.
    """
    try:
        try:
            idx = int(element_id)
        except ValueError:
            return "Error: El ID del elemento debe ser un número entero."
            
        status = browser_manager.click_element(idx)
        return f"{status}{get_screenshot_markdown()}"
    except Exception as e:
        return f"Error al hacer clic en el elemento [{element_id}]: {e}"

@tool
def web_browser_type(element_id: int, text: str) -> str:
    """
    Types text into the interactive input field identified by the numerical ID/index overlay (e.g. 0, 1, 2).
    Use this tool to fill forms, write search queries, enter credentials, etc. visible on the screenshot.
    """
    try:
        try:
            idx = int(element_id)
        except ValueError:
            return "Error: El ID del elemento debe ser un número entero."
            
        status = browser_manager.type_in_element(idx, text)
        return f"{status}{get_screenshot_markdown()}"
    except Exception as e:
        return f"Error al escribir en el elemento [{element_id}]: {e}"

@tool
def web_browser_scroll(direction: str) -> str:
    """
    Scrolls the page vertically.
    - direction: Must be 'up' or 'down'.
    """
    try:
        status = browser_manager.scroll_page(direction)
        return f"{status}{get_screenshot_markdown()}"
    except Exception as e:
        return f"Error al desplazar la página: {e}"

@tool
def web_browser_back() -> str:
    """
    Navigates back to the previous webpage in browser history.
    """
    try:
        status = browser_manager.go_back()
        return f"{status}{get_screenshot_markdown()}"
    except Exception as e:
        return f"Error al retroceder en el navegador: {e}"
