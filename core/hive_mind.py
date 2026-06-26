"""
core/hive_mind.py — Protocolo "Mente Colmena" (consenso multi-modelo).

Para preguntas complejas, consulta a varios modelos en paralelo y sintetiza una
única respuesta de consenso, señalando coincidencias y discrepancias. Reutiliza
core.llm_factory (OpenRouter).

El parseo de la lista de modelos y el armado del prompt de síntesis son puros y
testeables; las llamadas al LLM se aíslan (mockeables).
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def _parse_model_list(spec: str) -> list:
    """Lista de modelos a partir de una cadena separada por comas (puro)."""
    if not spec:
        return []
    seen, out = set(), []
    for m in spec.split(","):
        m = m.strip()
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def get_default_models() -> list:
    """Modelos del enjambre: JARVIS_HIVE_MODELS o los modelos configurados."""
    explicit = _parse_model_list(os.getenv("JARVIS_HIVE_MODELS", ""))
    if explicit:
        return explicit
    defaults = [
        os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v4-pro"),
        os.getenv("JARVIS_MODEL_THINK", "qwen/qwen3.7-plus"),
        os.getenv("JARVIS_MODEL_CODE", "qwen/qwen3-coder"),
    ]
    return _parse_model_list(",".join(defaults))


def _short_name(model: str) -> str:
    """Nombre legible de un id de modelo (parte tras la última '/')."""
    return model.split("/")[-1] if model else model


def build_synthesis_prompt(question: str, responses: list) -> str:
    """Prompt para que un modelo árbitro sintetice el consenso (puro).

    responses: lista de {model, answer}."""
    blocks = []
    for r in responses:
        ans = (r.get("answer") or "").strip()
        if not ans:
            continue
        blocks.append(f"--- Respuesta de «{_short_name(r.get('model', '?'))}» ---\n{ans}")
    joined = "\n\n".join(blocks)
    return (
        "Eres un árbitro experto. A continuación tienes la PREGUNTA original de un "
        "usuario y las RESPUESTAS de varios modelos de IA independientes. Redacta una "
        "ÚNICA respuesta de consenso, clara y útil para el usuario, e indica brevemente "
        "en qué coinciden los modelos y en qué discrepan (si discrepan). No menciones "
        "que eres un árbitro; responde directamente.\n\n"
        f"PREGUNTA:\n{question}\n\nRESPUESTAS:\n{joined}\n\nRESPUESTA DE CONSENSO:"
    )


def _ask_one(model: str, prompt: str) -> dict:
    """Consulta a un modelo. Devuelve {model, answer, error}."""
    try:
        from core.llm_factory import get_llm
        llm = get_llm(model_name=model, temperature=0.3)
        resp = llm.invoke(prompt)
        return {"model": model, "answer": getattr(resp, "content", str(resp)), "error": None}
    except Exception as e:
        logger.warning(f"[HiveMind] Modelo {model} falló: {e}")
        return {"model": model, "answer": "", "error": str(e)}


def _query_all(question: str, models: list) -> list:
    """Consulta a todos los modelos en paralelo. Conserva el orden de `models`."""
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, len(models))) as ex:
        futures = {ex.submit(_ask_one, m, question): m for m in models}
        for fut in as_completed(futures):
            r = fut.result()
            results[r["model"]] = r
    return [results[m] for m in models if m in results]


def consult(question: str, models: list = None, synthesizer: str = None) -> str:
    """Consulta al enjambre y devuelve la síntesis de consenso."""
    if not question or not question.strip():
        return "¿Qué desea que consulte, señor?"
    models = models or get_default_models()
    if not models:
        return "Señor, no hay modelos configurados para la Mente Colmena."

    responses = _query_all(question, models)
    valid = [r for r in responses if not r.get("error") and (r.get("answer") or "").strip()]

    if not valid:
        return "Señor, no he obtenido respuesta de los núcleos de razonamiento."
    if len(valid) == 1:
        return valid[0]["answer"].strip()

    synth_model = synthesizer or os.getenv("JARVIS_HIVE_SYNTHESIZER") or \
        os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v4-pro")
    result = _ask_one(synth_model, build_synthesis_prompt(question, valid))
    if result.get("error") or not (result.get("answer") or "").strip():
        # Si la síntesis falla, devolvemos las respuestas en bruto.
        return "\n\n".join(f"[{_short_name(r['model'])}] {r['answer'].strip()}" for r in valid)
    return result["answer"].strip()
