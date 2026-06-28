"""
core/simulation.py — Simulaciones y Cálculos al Vuelo.

Ante una acción ("simula el despliegue", "¿qué probabilidad de éxito?"), Jarvis
ejecuta comprobaciones rápidas (dry-runs/checks reales) y calcula una
PROBABILIDAD de éxito ponderada: *"Ejecutando simulación… probabilidad de éxito
del 91%, señor."*. Decisión cuantitativa antes de actuar.

El cálculo de la probabilidad a partir de unos factores ponderados y el fraseo
son funciones PURAS y testeables; la ejecución de las comprobaciones (tests,
git, sistema) se aísla. A diferencia de threat_assessment (riesgo del contexto),
esto CORRE comprobaciones concretas para la acción pedida.
"""
import logging

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Núcleo puro (probabilidad ponderada + fraseo)
# ----------------------------------------------------------------------------
def success_probability(factors) -> int:
    """Probabilidad de éxito 0-100 a partir de factores ponderados. Puro.

    factors: lista de {name, ok: bool, weight}. La probabilidad es la fracción
    de peso satisfecho, sobre 100. Sin factores -> 50 (incierto)."""
    factors = factors or []
    total = sum(abs(f.get("weight", 1)) for f in factors)
    if total == 0:
        return 50
    got = sum(abs(f.get("weight", 1)) for f in factors if f.get("ok"))
    return int(round(got / total * 100))


def verdict(prob: int) -> str:
    """Veredicto cualitativo de una probabilidad (puro)."""
    if prob >= 85:
        return "muy favorable"
    if prob >= 65:
        return "favorable"
    if prob >= 45:
        return "incierto"
    if prob >= 25:
        return "desfavorable"
    return "muy desfavorable"


def format_simulation(action: str, prob: int, factors) -> str:
    """Informe de la simulación: probabilidad, veredicto y factores en contra (puro)."""
    contras = [f["name"] for f in (factors or []) if not f.get("ok")]
    accion = f" para {action}" if action else ""
    base = (f"Simulación completada{accion}, señor. Probabilidad de éxito: {prob}%. "
            f"Pronóstico {verdict(prob)}.")
    if contras:
        base += " En contra: " + ", ".join(contras[:4]) + "."
    return base


# ----------------------------------------------------------------------------
# Comprobaciones (aisladas) y orquestación
# ----------------------------------------------------------------------------
def _check_smoke_tests() -> bool:
    """Corre el subconjunto smoke de tests; True si pasan."""
    try:
        from core.jarvis_integrity import run_unit_tests
        return bool(run_unit_tests().get("passed"))
    except Exception as e:
        logger.debug(f"[Simulation] Tests no evaluables: {e}")
        return False


def _gather_factors() -> list:
    """Factores reales del estado para la simulación (cada uno con su peso)."""
    factors = []
    # Estado del mundo (RAM, amenaza, repo).
    try:
        from core.world_model import snapshot
        s = snapshot()
        ram = float((s.get("system", {}) or {}).get("ram") or 0)
        factors.append({"name": "memoria holgada", "ok": ram < 85, "weight": 2})
        threat = str((s.get("threat", {}) or {}).get("level", "green")).lower()
        factors.append({"name": "amenaza controlada", "ok": threat in ("green", "amber"), "weight": 2})
        dirty = (s.get("project", {}) or {}).get("dirty_count") or 0
        factors.append({"name": "árbol git limpio", "ok": dirty == 0, "weight": 1})
    except Exception as e:
        logger.debug(f"[Simulation] Sin estado del mundo: {e}")
    # Tests (el más pesado).
    factors.append({"name": "tests en verde", "ok": _check_smoke_tests(), "weight": 4})
    return factors


def simulate(action: str = "") -> str:
    """Ejecuta la simulación para una acción y devuelve el informe."""
    factors = _gather_factors()
    prob = success_probability(factors)
    return format_simulation(action, prob, factors)
