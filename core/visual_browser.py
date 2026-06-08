import os
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
SCREENSHOT_PATH = LOGS_DIR / "browser_screenshot.png"

class VisualBrowserManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(VisualBrowserManager, cls).__new__(cls, *args, **kwargs)
            cls._instance.playwright = None
            cls._instance.browser = None
            cls._instance.context = None
            cls._instance.page = None
            cls._instance.headless = True
        return cls._instance

    def get_page(self):
        """Lazily initializes Playwright and Chromium browser page."""
        if self.page and not self.page.is_closed():
            return self.page
            
        try:
            LOGS_DIR.mkdir(exist_ok=True)
            if not self.playwright:
                self.playwright = sync_playwright().start()
            if not self.browser:
                self.browser = self.playwright.chromium.launch(headless=self.headless)
            if not self.context:
                self.context = self.browser.new_context(viewport={"width": 1280, "height": 800})
            if not self.page or self.page.is_closed():
                self.page = self.context.new_page()
            return self.page
        except Exception as e:
            logging.error(f"[Visual Browser] Failed to initialize browser page: {e}")
            raise e

    def close(self):
        """Closes the current browser and playwright sessions."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logging.error(f"[Visual Browser] Error closing browser: {e}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None

    def navigate_to(self, url: str) -> str:
        """Navigates to the specified URL, injects overlays, captures page screenshot, and returns status."""
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("data:"):
            url = "https://" + url
            
        page = self.get_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
        except Exception:
            try:
                page.goto(url, wait_until="load", timeout=10000)
            except Exception as e:
                return f"Error al navegar a {url}: {e}"
                
        page.wait_for_timeout(1000)
        num_elements = self.inject_visual_overlays()
        self.capture_page_screenshot()
        
        return f"Navegado a {url} con éxito. Se han identificado {num_elements} elementos interactivos en pantalla."

    def inject_visual_overlays(self) -> int:
        """Injects visual annotation badges (red/pink buttons with numbers) on interactive elements."""
        page = self.get_page()
        script = """
        (() => {
            // Clean old badges
            document.querySelectorAll('.jarvis-nav-badge').forEach(b => b.remove());
            document.querySelectorAll('[data-jarvis-id]').forEach(el => el.removeAttribute('data-jarvis-id'));

            const candidates = document.querySelectorAll('button, a, input:not([type="hidden"]), textarea, select, [role="button"], [role="link"], [contenteditable="true"]');
            let index = 0;
            
            // Sort elements visually: top-to-bottom, left-to-right
            const sorted = Array.from(candidates).sort((a, b) => {
                const rA = a.getBoundingClientRect();
                const rB = b.getBoundingClientRect();
                if (Math.abs(rA.top - rB.top) < 5) {
                    return rA.left - rB.left;
                }
                return rA.top - rB.top;
            });

            sorted.forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 2 && rect.height > 2 && rect.top < window.innerHeight && rect.bottom > 0 && rect.left < window.innerWidth && rect.right > 0) {
                    const style = window.getComputedStyle(el);
                    if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                        el.setAttribute('data-jarvis-id', index);
                        
                        const badge = document.createElement('div');
                        badge.className = 'jarvis-nav-badge';
                        badge.style.position = 'absolute';
                        badge.style.top = (rect.top + window.scrollY) + 'px';
                        badge.style.left = (rect.left + window.scrollX) + 'px';
                        badge.style.background = 'rgba(255, 51, 68, 0.9)';
                        badge.style.color = '#ffffff';
                        badge.style.border = '1px solid #00d4ff';
                        badge.style.fontFamily = 'monospace';
                        badge.style.fontSize = '11px';
                        badge.style.fontWeight = 'bold';
                        badge.style.padding = '2px 5px';
                        badge.style.borderRadius = '3px';
                        badge.style.zIndex = '10000000';
                        badge.style.pointerEvents = 'none';
                        badge.style.boxShadow = '0 0 5px rgba(255, 51, 68, 0.5)';
                        badge.textContent = index;
                        document.body.appendChild(badge);
                        index++;
                    }
                }
            });
            return index;
        })()
        """
        try:
            return page.evaluate(script)
        except Exception as e:
            logging.error(f"[Visual Browser] Failed to inject overlays: {e}")
            return 0

    def click_element(self, index: int) -> str:
        """Clicks the interactive element identified by the index."""
        page = self.get_page()
        try:
            selector = f'[data-jarvis-id="{index}"]'
            target = page.query_selector(selector)
            if not target:
                return f"Error: No se encontró ningún elemento interactivo con el ID {index}."
                
            target.click(timeout=5000)
            page.wait_for_timeout(1500)
            
            num_elements = self.inject_visual_overlays()
            self.capture_page_screenshot()
            
            return f"Clic realizado en el elemento [{index}] con éxito. Nuevos elementos interactivos identificados: {num_elements}."
        except Exception as e:
            return f"Error al hacer clic en el elemento [{index}]: {e}"

    def type_in_element(self, index: int, text: str) -> str:
        """Types text into the interactive input element identified by the index."""
        page = self.get_page()
        try:
            selector = f'[data-jarvis-id="{index}"]'
            target = page.query_selector(selector)
            if not target:
                return f"Error: No se encontró ningún input con el ID {index}."
                
            target.fill(text, timeout=5000)
            num_elements = self.inject_visual_overlays()
            self.capture_page_screenshot()
            
            return f"Texto introducido en el elemento [{index}] con éxito. Nuevos elementos interactivos: {num_elements}."
        except Exception as e:
            return f"Error al escribir en el elemento [{index}]: {e}"

    def scroll_page(self, direction: str) -> str:
        """Scrolls the browser page vertically ('up' or 'down')."""
        page = self.get_page()
        try:
            if direction.lower() == "down":
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.7)")
            elif direction.lower() == "up":
                page.evaluate("window.scrollBy(0, -window.innerHeight * 0.7)")
            else:
                return "Error: Dirección de scroll inválida. Usa 'up' o 'down'."
                
            page.wait_for_timeout(500)
            num_elements = self.inject_visual_overlays()
            self.capture_page_screenshot()
            
            return f"Scroll realizado hacia {direction}. Nuevos elementos identificados: {num_elements}."
        except Exception as e:
            return f"Error al realizar scroll: {e}"

    def go_back(self) -> str:
        """Navigates back to the previous page in history."""
        page = self.get_page()
        try:
            page.go_back(timeout=10000)
            page.wait_for_timeout(1000)
            num_elements = self.inject_visual_overlays()
            self.capture_page_screenshot()
            return f"Regresado a la página anterior. Nuevos elementos identificados: {num_elements}."
        except Exception as e:
            return f"Error al regresar en el historial: {e}"

    def capture_page_screenshot(self) -> str:
        """Captures a screenshot of the current page and saves it to the logs folder."""
        page = self.get_page()
        try:
            LOGS_DIR.mkdir(exist_ok=True)
            page.screenshot(path=str(SCREENSHOT_PATH))
            return str(SCREENSHOT_PATH)
        except Exception as e:
            logging.error(f"[Visual Browser] Failed to capture page screenshot: {e}")
            return ""

browser_manager = VisualBrowserManager()
