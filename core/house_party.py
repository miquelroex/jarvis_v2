"""
core/house_party.py — Protocolo "Casa Llena" (House Party, multi-agente).

Ante un objetivo complejo, Jarvis despliega varios sub-agentes especializados que
trabajan EN PARALELO con roles distintos (investigación, ingeniería, control de
calidad) y un coordinador integra sus aportaciones en una única respuesta final.

A diferencia de la Mente Colmena (misma pregunta a todos), aquí cada agente tiene
un enfoque distinto. El armado de prompts es puro/testeable; las llamadas al LLM
se aíslan. Reutiliza core.llm_factory (OpenRouter).
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

ROLES = {
    "investigador": {
        "label": "Investigación",
        "model_env": "JARVIS_MODEL_THINK",
        "instruction": ("Eres el agente de INVESTIGACIÓN del equipo. Aporta el contexto "
                        "esencial, los datos relevantes, enfoques posibles y consideraciones "
                        "clave para abordar el objetivo. No implementes; informa."),
    },
    "ingeniero": {
        "label": "Ingeniería",
        "model_env": "JARVIS_MODEL_CODE",
        "instruction": ("Eres el agente de INGENIERÍA del equipo. Propón la solución técnica "
                        "concreta: pasos accionables y, si procede, código. Sé preciso y práctico."),
    },
    "control": {
        "label": "Control de Calidad",
        "model_env": "JARVIS_MODEL_THINK",
        "instruction": ("Eres el agente de CONTROL DE CALIDAD del equipo. Señala riesgos, casos "
                        "límite, errores potenciales y validaciones necesarias. Sé crítico y útil."),
    },
}


def _model_for(role_key: str) -> str:
    role = ROLES.get(role_key, {})
    return os.getenv(role.get("model_env", ""), "") or \
        os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v4-pro")


def build_role_prompt(role_key: str, objective: str) -> str:
    """Prompt para un agente con su rol (puro)."""
    role = ROLES.get(role_key, {"instruction": "Eres un agente del equipo."})
    return (f"{role['instruction']}\n\nOBJETIVO DEL USUARIO:\n{objective}\n\n"
            "Tu aportación (concisa, estructurada y accionable):")


def build_coordinator_prompt(objective: str, contributions: list) -> str:
    """Prompt para que el coordinador unifique las aportaciones (puro).

    contributions: lista de (role_key, texto)."""
    blocks = []
    for role_key, text in contributions:
        label = ROLES.get(role_key, {}).get("label", role_key)
        if (text or "").strip():
            blocks.append(f"--- Aportación de {label} ---\n{text.strip()}")
    joined = "\n\n".join(blocks)
    return (
        "Eres el COORDINADOR de un equipo de agentes especializados. Integra las "
        "aportaciones de tu equipo en una ÚNICA respuesta final para el usuario: clara, "
        "accionable y sin redundancias. Resuelve contradicciones y prioriza lo importante. "
        "No menciones que eres un coordinador; responde directamente.\n\n"
        f"OBJETIVO:\n{objective}\n\nAPORTACIONES DEL EQUIPO:\n{joined}\n\nRESPUESTA FINAL DEL EQUIPO:"
    )


def _ask_model(model: str, prompt: str) -> str:
    try:
        from core.llm_factory import get_llm
        llm = get_llm(model_name=model, temperature=0.3)
        resp = llm.invoke(prompt)
        return getattr(resp, "content", str(resp)) or ""
    except Exception as e:
        logger.warning(f"[HouseParty] Modelo {model} falló: {e}")
        return ""


def _ask_role(role_key: str, objective: str) -> str:
    return _ask_model(_model_for(role_key), build_role_prompt(role_key, objective))


def run_house_party(objective: str, roles: list = None, synthesizer: str = None) -> str:
    """Despliega el equipo en paralelo y devuelve la respuesta unificada."""
    if not objective or not objective.strip():
        return "¿Cuál es el objetivo para el equipo, señor?"
    roles = roles or list(ROLES.keys())

    from core.narration import narrate
    narrate(f"Desplegando un equipo de {len(roles)} agentes especializados, señor…")
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, len(roles))) as ex:
        futures = {ex.submit(_ask_role, r, objective): r for r in roles}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

    contributions = [(r, results.get(r, "")) for r in roles if (results.get(r, "") or "").strip()]
    if not contributions:
        return "Señor, el equipo no ha podido aportar nada en esta ocasión."
    if len(contributions) == 1:
        return contributions[0][1].strip()

    narrate("Coordinando las aportaciones del equipo, señor…")
    coord_model = synthesizer or os.getenv("JARVIS_HOUSEPARTY_COORDINATOR") or \
        os.getenv("JARVIS_MODEL_DEFAULT", "deepseek/deepseek-v4-pro")
    final = _ask_model(coord_model, build_coordinator_prompt(objective, contributions))
    if not final.strip():
        # Si la coordinación falla, devolvemos las aportaciones etiquetadas.
        return "\n\n".join(f"[{ROLES.get(r, {}).get('label', r)}] {t.strip()}" for r, t in contributions)
    return final.strip()
