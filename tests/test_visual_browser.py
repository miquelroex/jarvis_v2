import sys
import os
import unittest
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.visual_browser import browser_manager, SCREENSHOT_PATH
from tools.visual_browser_tool import (
    web_browser_navigate,
    web_browser_click,
    web_browser_type,
    web_browser_scroll,
    web_browser_back
)

class TestVisualBrowser(unittest.TestCase):
    def setUp(self):
        # Asegurarnos de que el manager arranca limpio
        browser_manager.close()
        browser_manager.headless = True
        
    def tearDown(self):
        browser_manager.close()
        if SCREENSHOT_PATH.exists():
            try:
                SCREENSHOT_PATH.unlink()
            except Exception:
                pass

    def test_browser_lifecycle_and_overlays(self):
        # Crear un HTML simple con data URL
        html_content = (
            "data:text/html,<html><body>"
            "<h1>Test Page</h1>"
            "<a href='about:blank' style='display:inline-block; width:100px; height:30px;'>Enlace de Prueba</a>"
            "<button id='btn' style='display:inline-block; width:100px; height:30px;'>Boton de Prueba</button>"
            "<input id='txt' style='display:inline-block; width:100px; height:30px;' />"
            "</body></html>"
        )
        
        # 1. Navegar
        res = web_browser_navigate.invoke({"url": html_content})
        
        self.assertIn("Navegado a data:text/html", res)
        # Debe haber inyectado overlays y creado el screenshot
        self.assertTrue(SCREENSHOT_PATH.exists())
        self.assertIn("![Vista del Navegador]", res)
        
        # Debemos tener identificados al menos 3 elementos interactivos (a, button, input)
        page = browser_manager.get_page()
        badges = page.query_selector_all(".jarvis-nav-badge")
        self.assertEqual(len(badges), 3)

        # 2. Escribir texto en el input (debe ser ID 2 si se ordenan por top-to-bottom)
        # Vamos a escribir "Hola Jarvis" en el elemento que tenga data-jarvis-id="2"
        type_res = web_browser_type.invoke({"element_id": 2, "text": "Hola Jarvis"})
        self.assertIn("Texto introducido en el elemento [2] con éxito", type_res)
        
        # Comprobar que el valor se escribió en el input real
        input_val = page.eval_on_selector("#txt", "el => el.value")
        self.assertEqual(input_val, "Hola Jarvis")

        # 3. Hacer clic en el botón (debe ser ID 1)
        # Vamos a añadir un event listener para verificar el click
        page.evaluate("document.getElementById('btn').addEventListener('click', () => { document.body.innerHTML += '<p id=\"clicked\">Boton clickeado</p>'; })")
        
        click_res = web_browser_click.invoke({"element_id": 1})
        self.assertIn("Clic realizado en el elemento [1] con éxito", click_res)
        
        # Verificar que el párrafo apareció en el DOM
        clicked_el = page.query_selector("#clicked")
        self.assertIsNotNone(clicked_el)

    def test_scroll_and_back(self):
        # HTML alto para probar scroll
        html_content = "data:text/html,<html><body style='height: 2000px;'><h1>Scroll Test</h1></body></html>"
        web_browser_navigate.invoke({"url": html_content})
        
        scroll_res = web_browser_scroll.invoke({"direction": "down"})
        self.assertIn("Scroll realizado hacia down", scroll_res)
        
        back_res = web_browser_back.invoke({})
        self.assertIn("Regresado a la página anterior", back_res)

if __name__ == "__main__":
    unittest.main()
