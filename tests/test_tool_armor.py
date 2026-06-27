"""Tests de core/tool_armor.py — coraza universal de herramientas."""
import core.tool_armor as ta


def setup_function(_):
    ta.reset_stats()


# ---------------------------------------------------------------- CircuitBreaker
def test_breaker_starts_closed():
    b = ta.CircuitBreaker(fail_threshold=3)
    assert b.is_open(now=0) is False
    assert b.state == "closed"


def test_breaker_opens_after_threshold():
    b = ta.CircuitBreaker(fail_threshold=3, reset_after=100)
    b.record_failure(now=10)
    b.record_failure(now=11)
    assert b.is_open(now=12) is False  # aún 2 < 3
    assert b.state == "degraded"
    b.record_failure(now=12)
    assert b.is_open(now=13) is True   # 3 fallos -> abierto
    assert b.state == "open"


def test_breaker_success_resets():
    b = ta.CircuitBreaker(fail_threshold=2)
    b.record_failure(now=1)
    b.record_success()
    assert b.failures == 0
    assert b.is_open(now=2) is False


def test_breaker_half_open_after_reset():
    b = ta.CircuitBreaker(fail_threshold=2, reset_after=60)
    b.record_failure(now=0)
    b.record_failure(now=1)
    assert b.is_open(now=2) is True          # abierto
    assert b.is_open(now=100) is False       # pasó el enfriamiento -> deja pasar
    # En half-open, un solo fallo reabre (threshold-1 ya acumulado).
    b.record_failure(now=101)
    assert b.is_open(now=102) is True


def test_breaker_threshold_min_one():
    assert ta.CircuitBreaker(fail_threshold=0).fail_threshold == 1


# ---------------------------------------------------------------- telemetría
def test_record_call_accumulates():
    ta.record_call("t", 100, ok=True)
    ta.record_call("t", 200, ok=False, error="boom")
    stats = ta.get_stats()
    assert stats["t"]["calls"] == 2
    assert stats["t"]["failures"] == 1
    assert stats["t"]["last_error"] == "boom"


def test_summarize_stats_computes_rates():
    ta.record_call("a", 100, ok=True)
    ta.record_call("a", 300, ok=False, error="x")
    rows = ta.summarize_stats(ta.get_stats())
    a = next(r for r in rows if r["name"] == "a")
    assert a["calls"] == 2
    assert a["fail_rate"] == 0.5
    assert a["avg_ms"] == 200.0


def test_summarize_sorts_by_calls():
    ta.record_call("rare", 10, ok=True)
    for _ in range(3):
        ta.record_call("common", 10, ok=True)
    rows = ta.summarize_stats(ta.get_stats())
    assert rows[0]["name"] == "common"


def test_format_tool_report_empty():
    assert "Aún no he usado" in ta.format_tool_report({})


def test_format_tool_report_lists_and_flags_open():
    ta.record_call("buscar", 1200, ok=True)
    ta.record_call("buscar", 1200, ok=True)
    # Forzar circuito abierto en otra tool.
    b = ta.get_breaker("rota")
    for _ in range(b.fail_threshold):
        b.record_failure(now=0)
    ta.record_call("rota", 50, ok=False, error="e")
    report = ta.format_tool_report(ta.get_stats())
    assert "buscar: 2 usos" in report
    # La sección de circuito abierto nombra SÓLO la tool abierta, no la sana.
    assert "abierto en: rota" in report
    assert "abierto en: buscar" not in report


# ---------------------------------------------------------------- armor_callable
def test_armor_callable_success_records():
    b = ta.CircuitBreaker()
    wrapped = ta.armor_callable("ok_tool", lambda x: f"hola {x}", b, retries=0, backoff=0)
    assert wrapped("mundo") == "hola mundo"
    assert ta.get_stats()["ok_tool"]["calls"] == 1
    assert ta.get_stats()["ok_tool"]["failures"] == 0


def test_armor_callable_retries_then_fails():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        raise RuntimeError("siempre falla")

    b = ta.CircuitBreaker(fail_threshold=10)
    wrapped = ta.armor_callable("flaky", flaky, b, retries=2, backoff=0)
    out = wrapped()
    assert "ha fallado" in out          # mensaje gracioso, no excepción
    assert calls["n"] == 3              # 1 intento + 2 reintentos
    assert ta.get_stats()["flaky"]["failures"] == 1  # 1 fallo lógico, no 3


def test_armor_callable_recovers_after_failure():
    state = {"fail": True}

    def sometimes():
        if state["fail"]:
            raise RuntimeError("x")
        return "ok"

    b = ta.CircuitBreaker(fail_threshold=10)
    wrapped = ta.armor_callable("rec", sometimes, b, retries=0, backoff=0)
    assert "ha fallado" in wrapped()
    state["fail"] = False
    assert wrapped() == "ok"
    assert b.failures == 0  # el éxito reseteó el contador


def test_armor_callable_open_circuit_skips():
    called = {"n": 0}

    def fn():
        called["n"] += 1
        return "no debería llamarse"

    import time
    b = ta.CircuitBreaker(fail_threshold=1, reset_after=999)
    b.record_failure(now=time.time())  # circuito recién abierto (dentro del enfriamiento)
    wrapped = ta.armor_callable("skip", fn, b, retries=0, backoff=0)
    out = wrapped()
    assert "deshabilitada temporalmente" in out
    assert called["n"] == 0  # no se invocó la función real
    assert ta.get_stats()["skip"]["failures"] == 1  # la llamada saltada cuenta como fallo


# ---------------------------------------------------------------- armor_tool / armor_all
class _FakeTool:
    def __init__(self, name, func):
        self.name = name
        self.func = func


def test_armor_tool_wraps_func():
    t = _FakeTool("mi_tool", lambda q: f"eco:{q}")
    original = t.func
    ta.armor_tool(t, retries=0, backoff=0)
    assert t.func is not original
    assert t.func("hey") == "eco:hey"
    assert ta.get_stats()["mi_tool"]["calls"] == 1


def test_armor_tool_skips_non_callable():
    t = _FakeTool("sin_func", None)
    # No debe romper ni envolver.
    ta.armor_tool(t)
    assert t.func is None


def test_armor_all_counts_wrapped():
    tools = [_FakeTool("a", lambda: 1), _FakeTool("b", lambda: 2), _FakeTool("c", None)]
    n = ta.armor_all(tools)
    assert n == 2  # 'c' no es envolvible
