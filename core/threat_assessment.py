"""
core/threat_assessment.py — Evaluación de Amenaza Narrada.

Ante una decisión o acción, Jarvis verbaliza un análisis probabilístico al estilo
de las películas: *"Analizando… probabilidad de éxito 87%. Riesgo: moderado."*

Heurística simple sobre el contexto: RAM, pruebas fallando, nivel de amenaza
DEFCON, cambios sin confirmar y, si se evalúa un comando, su peligrosidad.

El cálculo es puro y testeable; la recolección del contexto real se aísla.
"""
import logging

logger = logging.getLogger(__name__)

BASE_SCORE = 95


def _risk_from_score(score: int) -> str:
    if score >= 80:
        return "bajo"
    if score >= 55:
        return "moderado"
    if score >= 30:
        return "alto"
    return "crítico"


def assess(context: dict) -> dict:
    """Evalúa el contexto y devuelve {score, risk, reasons} (puro)."""
    score = BASE_SCORE
    reasons = []

    ram = _num(context.get("ram_percent"))
    if ram >= 90:
        score -= 25
        reasons.append("memoria crítica")
    elif ram >= 75:
        score -= 10
        reasons.append("memoria elevada")

    failing = int(_num(context.get("tests_failing")))
    if failing > 0:
        score -= min(25, failing * 8)
        reasons.append(f"{failing} suite(s) de pruebas fallando")

    threat = (context.get("threat_level") or "green").lower()
    if threat in ("red", "violet"):
        score -= 25
        reasons.append("nivel de amenaza elevado")
    elif threat == "amber":
        score -= 10
        reasons.append("nivel de amenaza en ámbar")

    dirty = int(_num(context.get("dirty_count")))
    if dirty >= 50:
        score -= 15
        reasons.append("muchos cambios sin confirmar")
    elif dirty >= 20:
        score -= 8
        reasons.append("cambios sin confirmar")

    cmd_risk = (context.get("command_risk") or "").lower()
    if cmd_risk == "danger":
        score -= 35
        reasons.append("comando peligroso")
    elif cmd_risk == "caution":
        score -= 12
        reasons.append("comando que requiere precaución")

    score = max(5, min(99, score))
    return {"score": score, "risk": _risk_from_score(score), "reasons": reasons}


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def narrate_assessment(context: dict) -> str:
    """Frase narrada estilo Jarvis con el veredicto (puro)."""
    a = assess(context)
    line = f"Analizando, señor… Probabilidad de éxito estimada: {a['score']}%. Riesgo: {a['risk']}."
    if a["reasons"] and a["risk"] != "bajo":
        line += f" Factores: {', '.join(a['reasons'][:2])}."
    return line


def _gather_context(action: str = None) -> dict:
    """Recolecta el contexto real del sistema (best-effort)."""
    ctx = {"ram_percent": 0, "tests_failing": 0, "threat_level": "green", "dirty_count": 0}
    try:
        import psutil
        ctx["ram_percent"] = psutil.virtual_memory().percent
    except Exception:
        pass
    try:
        from core.test_watcher import _test_states
        ctx["tests_failing"] = sum(1 for s in _test_states.values() if s == "fail")
    except Exception:
        pass
    try:
        from core.threat_level import compute_threat_level
        ctx["threat_level"] = compute_threat_level().get("level", "green")
    except Exception:
        pass
    try:
        from core.project_awareness import get_active_project
        s = get_active_project()
        if s.get("is_repo"):
            ctx["dirty_count"] = s.get("dirty_count", 0)
    except Exception:
        pass
    if action:
        try:
            from core.command_safety import analyze_command
            ctx["command_risk"] = analyze_command(action)["level"]
        except Exception:
            pass
    return ctx


def get_assessment(action: str = None) -> str:
    """Evaluación narrada con el contexto real del sistema."""
    return narrate_assessment(_gather_context(action))
