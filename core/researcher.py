"""
core/researcher.py — Investigador Autónomo Profundo.

"Investiga X" → Jarvis descompone la pregunta en sub-preguntas, investiga cada
una en la web (en paralelo), contrasta lo encontrado y te entrega un informe
estructurado con conclusión, en vez de un único resultado de búsqueda.

Construye sobre el Motor de Fusión (fuente web) llevándolo a varios pasos:
planificar → investigar cada parte → sintetizar. La planificación (parseo del
plan), el prompt de síntesis y el formateo del informe son funciones PURAS y
testeables; las llamadas al modelo y la búsqueda web se aíslan y degradan con
gracia.
"""
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Planificación / formateo (puro)
# ----------------------------------------------------------------------------
def parse_plan(raw: str, max_q: int = 4):
    """Extrae sub-preguntas de la respuesta del modelo (numerada/viñetas). Puro.

    Quita el marcador inicial (1., -, *, 1)) de cada línea, descarta vacías o
    demasiado cortas, elimina duplicados y limita a `max_q`."""
    if not raw or not raw.strip():
        return []
    subqs = []
    seen = set()
    for line in raw.splitlines():
        line = line.strip()
        # Quitar viñetas/numeración inicial: "1.", "1)", "-", "*", "•".
        line = re.sub(r"^\s*(\d+[.)]|[-*•])\s*", "", line).strip()
        if len(line) < 5:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        subqs.append(line)
        if len(subqs) >= max_q:
            break
    return subqs


def build_plan_prompt(question: str, max_q: int = 4) -> str:
    """Prompt para que el modelo descomponga la pregunta en sub-preguntas. Puro."""
    return (
        "Eres el planificador de investigación de Jarvis. Descompón la siguiente "
        f"pregunta en un máximo de {max_q} sub-preguntas concretas e independientes "
        "que, investigadas por separado, permitan responderla a fondo. Devuelve "
        "SÓLO la lista, una sub-pregunta por línea, sin explicaciones.\n\n"
        f"Pregunta: {question}"
    )


def format_findings_block(findings) -> str:
    """Bloque de texto con lo hallado por cada sub-pregunta (puro)."""
    parts = []
    for f in findings or []:
        info = (f.get("info") or "").strip() or "(sin resultados)"
        parts.append(f"### {f.get('subq', '')}\n{info}")
    return "\n\n".join(parts)


def build_report_prompt(question: str, findings) -> str:
    """Prompt de síntesis del informe final a partir de los hallazgos. Puro."""
    return (
        "Eres Jarvis redactando un informe de investigación para tu desarrollador, "
        "en español y con tono Stark (claro, preciso, algo ingenioso). A partir de "
        "los hallazgos por sub-pregunta, redacta un informe estructurado: un breve "
        "resumen ejecutivo, los puntos clave (contrastando y señalando acuerdos o "
        "contradicciones entre fuentes) y una conclusión accionable. No inventes lo "
        "que no esté en los hallazgos.\n\n"
        f"Pregunta original: {question}\n\n"
        f"Hallazgos:\n{format_findings_block(findings)}\n\n"
        "Informe de Jarvis:"
    )


def build_raw_report(question: str, findings) -> str:
    """Informe de respaldo (sin LLM): los hallazgos ordenados. Puro."""
    if not has_findings(findings):
        return f"No he encontrado información sobre «{question}», señor."
    return f"Informe de investigación sobre «{question}», señor:\n\n{format_findings_block(findings)}"


def has_findings(findings) -> bool:
    """True si al menos una sub-pregunta obtuvo resultados (puro)."""
    return any((f.get("info") or "").strip() for f in (findings or []))


# ----------------------------------------------------------------------------
# Orquestación (aislado: modelo + web)
# ----------------------------------------------------------------------------
def _ask_llm(prompt: str) -> str:
    from core.llm_factory import get_llm
    llm = get_llm()
    resp = llm.invoke([("system", "Eres Jarvis, asistente de un desarrollador."),
                       ("human", prompt)])
    return (resp.content if hasattr(resp, "content") else str(resp)).strip()


def _decompose(question: str, max_q: int = 4):
    """Descompone la pregunta en sub-preguntas (con fallback a la pregunta sola)."""
    try:
        plan = parse_plan(_ask_llm(build_plan_prompt(question, max_q)), max_q)
        if plan:
            return plan
    except Exception as e:
        logger.warning(f"[Researcher] Falló la planificación: {e}")
    return [question]


def _investigate(subq: str) -> str:
    """Investiga una sub-pregunta en la web (reusa la fuente del motor de fusión)."""
    try:
        from core.fusion import _source_web
        return _source_web(subq) or ""
    except Exception as e:
        logger.debug(f"[Researcher] Búsqueda fallida para '{subq}': {e}")
        return ""


def _synthesize_report(question: str, findings) -> str:
    try:
        return _ask_llm(build_report_prompt(question, findings))
    except Exception as e:
        logger.warning(f"[Researcher] Falló la síntesis del informe: {e}")
        return ""


def research(question: str, max_q: int = 4) -> str:
    """Investiga una pregunta a fondo y devuelve un informe estructurado."""
    if not question or not question.strip():
        return "¿Qué desea que investigue, señor?"
    subqs = _decompose(question, max_q)

    findings = [{"subq": q, "info": ""} for q in subqs]
    with ThreadPoolExecutor(max_workers=max(1, len(subqs))) as ex:
        futures = {ex.submit(_investigate, f["subq"]): f for f in findings}
        for fut in as_completed(futures):
            entry = futures[fut]
            try:
                entry["info"] = fut.result()
            except Exception:
                entry["info"] = ""

    if not has_findings(findings):
        return f"No he encontrado información sobre «{question}», señor."

    report = _synthesize_report(question, findings)
    if report:
        return f"Investigación completada, señor ({len(subqs)} líneas exploradas).\n\n{report}"
    return build_raw_report(question, findings)
