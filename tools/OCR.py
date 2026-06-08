import os
from PIL import Image
from google import genai
from langchain.tools import tool

@tool("analyze_screenshot", return_direct=True)
def analyze_screenshot_tool(query: str = None) -> str:
    """
    Analiza visualmente la última captura de pantalla tomada del ordenador del usuario.
    Puedes pasar una consulta o pregunta opcional en 'query' para hacer preguntas específicas sobre la pantalla,
    como '¿qué error de código hay?', '¿qué ventanas están abiertas?' o '¿qué dice este texto?'.
    """
    image_path = "logs/latest_screenshot.png"
    
    if not os.path.exists(image_path):
        return "No se ha encontrado ninguna captura en logs/latest_screenshot.png. Por favor, realice una captura de pantalla primero, señor."

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "No se encontró la variable GOOGLE_API_KEY en el archivo .env. No se puede realizar el análisis visual."

    model = os.getenv("JARVIS_MODEL_GEMINI", "gemini-3.5-flash")

    try:
        # Cargar la imagen
        img = Image.open(image_path)
        
        # Inicializar el cliente oficial de Google GenAI
        client = genai.Client(api_key=api_key)
        
        # Estructurar la petición
        if query:
            prompt = f"El usuario pregunta lo siguiente sobre esta captura de pantalla de su PC: {query}. Responde en español de forma concisa y directa."
        else:
            prompt = "Analiza detalladamente esta captura de pantalla de mi PC. Describe qué aplicaciones o ventanas están abiertas, qué código o texto destaca y si hay algún error visible. Responde en español de forma servicial al estilo de Jarvis."

        # Llamar a Gemini enviando la imagen y el prompt en la lista de contenidos
        response = client.models.generate_content(
            model=model,
            contents=[img, prompt],
        )
        
        return response.text
    except Exception as e:
        return f"Error al procesar la imagen con Gemini Vision: {str(e)}"
