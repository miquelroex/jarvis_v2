import os
from langchain.tools import tool
from tavily import TavilyClient
from core.llm_factory import get_llm

@tool
def tavily_research(query: str) -> str:
    """
    Perform a deep research search using Tavily, extracting the full content of the top sources
    and synthesizing a comprehensive, detailed report in Spanish with cited links.
    Use this tool when the user asks for deep research, detailed reports, comprehensive summaries,
    or when they say 'investiga', 'busca a fondo', or request a detailed analysis of a topic.
    """
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        return "No se encontró TAVILY_API_KEY en el archivo .env. No se puede realizar la investigación profunda."

    import socket
    socket.setdefaulttimeout(15)

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    client = TavilyClient(api_key=tavily_api_key)

    # 1. Búsqueda inicial
    try:
        search_response = client.search(
            query=query,
            search_depth="advanced",
            max_results=3,
            include_answer=False,
            include_raw_content=False
        )
        results = search_response.get("results", [])
    except Exception as e:
        return f"Error en la búsqueda inicial de Tavily: {str(e)}"

    if not results:
        return f"No encontré resultados de búsqueda para la consulta: \"{query}\"."

    # Obtener URLs para la extracción
    urls = [r["url"] for r in results if r.get("url")]
    if not urls:
        return f"No se obtuvieron enlaces válidos de la búsqueda para realizar la investigación."

    # 2. Extracción de contenido completo
    extracted_results = []
    try:
        extract_response = client.extract(urls=urls, extract_depth="basic")
        extracted_results = extract_response.get("results", [])
    except Exception as e:
        # Fallback al contenido resumido de la búsqueda si la extracción total falla
        pass

    # 3. Preparación del contexto para el LLM
    pages_text = ""
    if extracted_results:
        for idx, r in enumerate(extracted_results, start=1):
            url = r.get("url", "Sin URL")
            title = next((item.get("title", "Fuente") for item in results if item.get("url") == url), "Fuente")
            raw_content = r.get("raw_content", "")
            # Limitar cada página a unos 12000 caracteres para no desbordar el contexto
            clean_content = raw_content[:12000] if raw_content else "Sin contenido útil."
            pages_text += f"\n--- FUENTE {idx}: {title} ({url}) ---\n{clean_content}\n"
    else:
        # Usar los extractos de la búsqueda como fallback
        pages_text = "Nota: No se pudo extraer el cuerpo completo de las páginas web. Usando extractos de la búsqueda:\n"
        for idx, r in enumerate(results, start=1):
            title = r.get("title", "Sin título")
            url = r.get("url", "Sin URL")
            snippet = r.get("content", "Sin extracto.")
            pages_text += f"\n--- FUENTE {idx}: {title} ({url}) ---\n{snippet}\n"

    # 4. Síntesis mediante LLM si la clave de OpenRouter está disponible
    if not openrouter_api_key:
        # Si no hay API key de LLM, devolvemos las fuentes ordenadas como fallback de investigación
        fallback_report = f"### Informe de Investigación Web (Sin síntesis de IA):\n\n"
        fallback_report += f"No se pudo generar el informe sintetizado porque falta la clave `OPENROUTER_API_KEY` en el archivo `.env`.\n\n"
        fallback_report += f"**Fuentes principales encontradas para: \"{query}\"**\n\n"
        for idx, r in enumerate(results, start=1):
            fallback_report += f"{idx}. **[{r.get('title', 'Fuente')}]({r.get('url')})**\n"
            fallback_report += f"   *Extracto*: {r.get('content')}\n\n"
        return fallback_report

    prompt = f"""Eres un analista de investigación senior y el asistente de inteligencia artificial Jarvis.
Tu tarea es redactar un informe de investigación completo, detallado y excelentemente estructurado en español sobre el siguiente tema: "{query}".

A continuación tienes la información bruta y contenido extraído directamente de las mejores fuentes web sobre este tema:
{pages_text}

Por favor, redacta un informe detallado que cumpla obligatoriamente con los siguientes requisitos:
1. **Idioma**: Escribe tu respuesta en español.
2. **Tono**: Sé servicial, inteligente y profesional, al estilo Jarvis. Dirígete ocasionalmente al usuario como "señor".
3. **Estructura de Informe**: Usa formato Markdown claro. Debe tener:
   - Un título descriptivo.
   - Resumen ejecutivo rápido.
   - Análisis y puntos clave desglosados en secciones temáticas detalladas.
   - Una conclusión o resumen de los próximos pasos/tendencias.
4. **Citas e Hipervínculos**: Cada vez que menciones un dato importante, añade el enlace de la fuente usando formato Markdown clásico, por ejemplo: [Nombre de la Fuente](url). No inventes enlaces, usa solo las URLs provistas en las fuentes anteriores.
5. **Completitud**: No omitas datos técnicos, fechas, nombres propios o cifras importantes. Haz un reporte exhaustivo, digno de un asistente premium.
"""

    try:
        model_name = os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v3.2")
        llm = get_llm(model_name, temperature=0.3)
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        # Si la llamada de síntesis falla, devolvemos un reporte alternativo indicando el error
        err_report = f"### Informe de Búsqueda sobre: \"{query}\"\n\n"
        err_report += f"⚠️ *Error al sintetizar el reporte con el LLM: {str(e)}*\n\n"
        err_report += f"**Fuentes encontradas:**\n\n"
        for idx, r in enumerate(results, start=1):
            err_report += f"{idx}. **[{r.get('title', 'Fuente')}]({r.get('url')})**\n"
            err_report += f"   *Resumen*: {r.get('content')}\n\n"
        return err_report
