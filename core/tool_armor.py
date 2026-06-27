"""
core/tool_armor.py — Capa de endurecimiento universal de herramientas.

En lugar de tocar las 37 tools una a una, este módulo ENVUELVE cada herramienta
de LangChain al cargarse (core.agent_manager.load_all_tools) y le añade, de un
golpe y retroactivamente:

  - 🛡️ Resiliencia: reintentos con backoff ante fallos transitorios.
  - 📊 Telemetría: cada llamada registra latencia, éxito/fallo y último error.
  - ⚡ Circuit breaker: si una tool falla repetidamente, "abre el circuito" y se
       salta (devolviendo un aviso) hasta que pase un tiempo de enfriamiento,
       evitando martillear un servicio caído.

El circuit breaker y la agregación de telemetría son PUROS y testeables; el
envoltorio de la herramienta (que muta el callable) se aísla y degrada con
gracia: si no se puede envolver una tool concreta, se deja tal cual.
"""
import os
import time
import logging
import functools
import threading

logger = logging.getLogger(__name__)

_STATS = {}
_lock = threading.Lock()


# ----------------------------------------------------------------------------
# Circuit breaker (puro)
# ----------------------------------------------------------------------------
class CircuitBreaker:
    """Cortacircuitos por herramienta: se abre tras N fallos y se cierra al enfriar."""

    def __init__(self, fail_threshold: int = 4, reset_after: float = 120.0):
        self.fail_threshold = max(1, fail_threshold)
        self.reset_after = reset_after
        self.failures = 0
        self.opened_at = None

    def record_success(self):
        self.failures = 0
        self.opened_at = None

    def record_failure(self, now: float):
        self.failures += 1
        if self.failures >= self.fail_threshold:
            self.opened_at = now

    def is_open(self, now: float) -> bool:
        """¿Está abierto (hay que saltar la tool)? Tras el enfriamiento, deja pasar
        un intento (half-open): si vuelve a fallar, se reabre."""
        if self.opened_at is None:
            return False
        if now - self.opened_at >= self.reset_after:
            self.opened_at = None
            self.failures = self.fail_threshold - 1  # un fallo más y reabre
            return False
        return True

    @property
    def state(self) -> str:
        if self.opened_at is not None:
            return "open"
        return "degraded" if self.failures else "closed"


# ----------------------------------------------------------------------------
# Telemetría (registro vivo + agregación pura)
# ----------------------------------------------------------------------------
def _entry(name: str) -> dict:
    return _STATS.setdefault(name, {
        "calls": 0, "failures": 0, "total_ms": 0.0, "last_error": "",
        "breaker": CircuitBreaker(
            fail_threshold=int(os.getenv("JARVIS_TOOL_ARMOR_FAIL_THRESHOLD", "4")),
            reset_after=float(os.getenv("JARVIS_TOOL_ARMOR_RESET", "120")),
        ),
    })


def record_call(name: str, ms: float, ok: bool, error: str = ""):
    """Registra una llamada a una herramienta (thread-safe)."""
    with _lock:
        e = _entry(name)
        e["calls"] += 1
        e["total_ms"] += ms
        if not ok:
            e["failures"] += 1
            e["last_error"] = error[:200]


def get_breaker(name: str) -> CircuitBreaker:
    with _lock:
        return _entry(name)["breaker"]


def get_stats() -> dict:
    with _lock:
        return {name: dict(e) for name, e in _STATS.items()}


def reset_stats():
    with _lock:
        _STATS.clear()


def summarize_stats(stats: dict):
    """Resumen por herramienta (puro): calls, fail_rate, avg_ms, estado, último error."""
    out = []
    for name, e in (stats or {}).items():
        calls = e.get("calls", 0)
        failures = e.get("failures", 0)
        breaker = e.get("breaker")
        out.append({
            "name": name,
            "calls": calls,
            "failures": failures,
            "fail_rate": (failures / calls) if calls else 0.0,
            "avg_ms": (e.get("total_ms", 0.0) / calls) if calls else 0.0,
            "state": breaker.state if breaker is not None else "closed",
            "last_error": e.get("last_error", ""),
        })
    out.sort(key=lambda s: s["calls"], reverse=True)
    return out


def format_tool_report(stats: dict, top: int = 6) -> str:
    """Informe hablado de la telemetría de herramientas (puro)."""
    rows = summarize_stats(stats)
    if not rows:
        return "Aún no he usado ninguna herramienta en esta sesión, señor."
    total_calls = sum(r["calls"] for r in rows)
    partes = []
    for r in rows[:top]:
        txt = f"{r['name']}: {r['calls']} usos"
        if r["fail_rate"]:
            txt += f", {r['fail_rate']*100:.0f}% fallo"
        txt += f", {r['avg_ms']:.0f}ms"
        partes.append(txt)
    report = (f"Telemetría de herramientas, señor: {total_calls} llamadas en "
              f"{len(rows)} herramientas. Más usadas: " + "; ".join(partes) + ".")
    abiertas = [r["name"] for r in rows if r["state"] == "open"]
    if abiertas:
        report += " ⚠ Circuito abierto en: " + ", ".join(abiertas) + "."
    return report


def get_tool_report() -> str:
    return format_tool_report(get_stats())


# ----------------------------------------------------------------------------
# Envoltorio de herramientas (aislado)
# ----------------------------------------------------------------------------
def armor_callable(name, fn, breaker, retries: int, backoff: float):
    """Envuelve un callable con circuit breaker + reintentos + telemetría."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if breaker.is_open(time.time()):
            record_call(name, 0.0, ok=False, error="circuito abierto")
            return (f"⚠ La herramienta «{name}» está deshabilitada temporalmente por "
                    "fallos repetidos, señor. La reintentaré más tarde.")
        t0 = time.perf_counter()
        last_err = None
        for attempt in range(retries + 1):
            try:
                result = fn(*args, **kwargs)
                record_call(name, (time.perf_counter() - t0) * 1000, ok=True)
                breaker.record_success()
                return result
            except Exception as e:
                last_err = e
                if attempt < retries:
                    time.sleep(backoff * (2 ** attempt))
        # Agotados los reintentos: registrar fallo, abrir circuito si procede.
        record_call(name, (time.perf_counter() - t0) * 1000, ok=False, error=str(last_err))
        breaker.record_failure(time.time())
        return f"⚠ La herramienta «{name}» ha fallado, señor: {last_err}"

    return wrapper


def armor_tool(tool, retries: int = None, backoff: float = None):
    """Aplica la coraza a una herramienta de LangChain (in-place). Devuelve la tool."""
    if retries is None:
        retries = int(os.getenv("JARVIS_TOOL_ARMOR_RETRIES", "1"))
    if backoff is None:
        backoff = float(os.getenv("JARVIS_TOOL_ARMOR_BACKOFF", "0.4"))
    name = getattr(tool, "name", None) or getattr(tool, "__name__", "?")
    fn = getattr(tool, "func", None)
    if not callable(fn):
        return tool  # no es envolvible (p.ej. tool basada en _run); se deja igual
    breaker = get_breaker(name)
    wrapped = armor_callable(name, fn, breaker, retries, backoff)
    try:
        tool.func = wrapped
    except Exception:
        try:
            object.__setattr__(tool, "func", wrapped)
        except Exception as e:
            logger.debug(f"[ToolArmor] No se pudo blindar «{name}»: {e}")
    return tool


def armor_all(tools):
    """Aplica la coraza a una lista de herramientas. Devuelve cuántas blindó."""
    n = 0
    for tool in tools or []:
        try:
            before = getattr(tool, "func", None)
            armor_tool(tool)
            if getattr(tool, "func", None) is not before:
                n += 1
        except Exception as e:
            logger.debug(f"[ToolArmor] Error blindando una herramienta: {e}")
    logger.info(f"[ToolArmor] Coraza aplicada a {n} herramientas.")
    return n
