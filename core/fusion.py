"""
core/fusion.py — Motor de Fusión de Fuentes ("lo sabe todo").

Ante una pregunta, Jarvis consulta VARIAS fuentes a la vez (web, clima, su propio
estado interno…) y un modelo sintetiza UNA respuesta con criterio, cruzando lo
que dicen y señalando acuerdos o tensiones — en vez de devolverte resultados
crudos. Es el equivalente de hive_mind (consenso entre modelos) pero aplicado a
DATOS del mundo en lugar de a modelos.

La selección de fuentes, el prompt de síntesis y el formateo son funciones PURAS
y testeables; la consulta en paralelo a las fuentes y la llamada al modelo se
aíslan. Cada fuente degrada con gracia (si falla o no está configurada, se omite).
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Fuentes (aisladas; cada una devuelve texto o None)
# ----------------------------------------------------------------------------
def _source_web(query: str):
    """Búsqueda web: Tavily y, si no, DuckDuckGo. None si nada disponible."""
    try:
        from tools.tavily_search import tavily_search
        out = tavily_search.invoke(query)
        if out and "No TAVILY_API_KEY" not in out:
            return str(out)[:1500]
    except Exception as e:
        logger.debug(f"[Fusion] Tavily no disponible: {e}")
    try:
        from tools.duckduckgo import _ddg_query
        results = _ddg_query(query)
        if results:
            return "; ".join(str(r) for r in results[:5])[:1500]
    except Exception as e:
        logger.debug(f"[Fusion] DuckDuckGo no disponible: {e}")
    return None


def _source_weather(query: str = None):
    """Clima local (OpenWeatherMap vía morning_briefing). None si no configurado."""
    try:
        from core.morning_briefing import _get_weather
        return _get_weather()
    except Exception as e:
        logger.debug(f"[Fusion] Clima no disponible: {e}")
        return None


def _source_state(query: str = None):
    """Estado interno del sistema (Cerebro de Estado Central)."""
    try:
        from core.world_model import snapshot, build_facts
        facts = build_facts(snapshot())
        return "; ".join(facts) if facts else None
    except Exception as e:
        logger.debug(f"[Fusion] Estado interno no disponible: {e}")
        return None


# Registro por defecto: {nombre legible: función fuente}
DEFAULT_SOURCES = {
    "web": _source_web,
    "clima": _source_weather,
    "estado del sistema": _source_state,
}


# ----------------------------------------------------------------------------
# Lógica pura (selección, prompt, formateo)
# ----------------------------------------------------------------------------
def available_results(results: dict) -> dict:
    """Filtra fuentes vacías/None, conservando sólo las que aportaron algo. Puro."""
    return {k: str(v).strip() for k, v in (results or {}).items()
            if v is not None and str(v).strip()}


def format_sources_block(results: dict) -> str:
    """Bloque de texto con lo aportado por cada fuente (puro)."""
    avail = available_results(results)
    if not avail:
        return ""
    return "\n".join(f"[{name}] {text}" for name, text in avail.items())


def build_fusion_prompt(query: str, results: dict) -> str:
    """Prompt de síntesis para el modelo a partir de las fuentes (puro)."""
    block = format_sources_block(results)
    return (
        "Eres Jarvis. Tienes información de VARIAS fuentes para responder a tu "
        "desarrollador. Sintetiza UNA sola respuesta en español, con criterio y "
        "tono Stark (claro, preciso, algo ingenioso). Cruza las fuentes: si "
        "coinciden, refuérzalo; si se contradicen o falta algo, dilo. No te "
        "limites a listar; da una conclusión útil y accionable.\n\n"
        f"Pregunta del usuario: {query}\n\n"
        f"Información recopilada de las fuentes:\n{block}\n\n"
        "Respuesta sintetizada de Jarvis:"
    )


def build_raw_fallback(query: str, results: dict) -> str:
    """Respuesta de respaldo (sin LLM): las fuentes en bruto pero ordenadas. Puro."""
    block = format_sources_block(results)
    if not block:
        return "No he podido reunir información de ninguna fuente, señor."
    return f"Esto es lo que he reunido, señor:\n{block}"


# ----------------------------------------------------------------------------
# Recolección en paralelo + síntesis (aislado)
# ----------------------------------------------------------------------------
def gather(query: str, sources: dict = None, timeout: float = None) -> dict:
    """Consulta todas las fuentes en paralelo. Devuelve {nombre: texto|None}."""
    sources = sources or DEFAULT_SOURCES
    if timeout is None:
        timeout = float(os.getenv("JARVIS_FUSION_TIMEOUT", "12"))
    results = {name: None for name in sources}
    try:
        with ThreadPoolExecutor(max_workers=max(1, len(sources))) as ex:
            futures = {ex.submit(fn, query): name for name, fn in sources.items()}
            for fut in as_completed(futures, timeout=timeout):
                name = futures[fut]
                try:
                    results[name] = fut.result()
                except Exception as e:
                    logger.debug(f"[Fusion] Fuente '{name}' falló: {e}")
    except Exception as e:
        logger.warning(f"[Fusion] Recolección incompleta (timeout?): {e}")
    return results


def _synthesize(query: str, results: dict) -> str:
    """Pide al modelo la síntesis. Devuelve "" si no se puede (el llamador hace fallback)."""
    try:
        from core.llm_factory import get_llm
        llm = get_llm()
        messages = [
            ("system", "Eres Jarvis, el asistente personal de un desarrollador."),
            ("human", build_fusion_prompt(query, results)),
        ]
        resp = llm.invoke(messages)
        return (resp.content if hasattr(resp, "content") else str(resp)).strip()
    except Exception as e:
        logger.warning(f"[Fusion] Falló la síntesis con el modelo: {e}")
        return ""


def fuse(query: str, sources: dict = None) -> str:
    """Consulta varias fuentes y devuelve una respuesta sintetizada con criterio."""
    if not query or not query.strip():
        return "¿Sobre qué desea que cruce mis fuentes, señor?"
    results = gather(query, sources)
    avail = available_results(results)
    if not avail:
        return "No he podido reunir información de ninguna fuente, señor."
    synthesis = _synthesize(query, avail)
    if synthesis:
        n = len(avail)
        prefijo = f"He cruzado {n} {'fuente' if n == 1 else 'fuentes'}, señor. "
        return prefijo + synthesis
    # Sin modelo: al menos entregamos lo reunido en bruto.
    return build_raw_fallback(query, avail)
