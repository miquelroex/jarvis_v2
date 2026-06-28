"""Tests de core/evolution.py — Motor de Evolución (aprendizaje continuo)."""
import core.evolution as ev


# ---------------------------------------------------------------- assess_evolution
def test_assess_open_circuit_tool():
    rows = [{"name": "tavily_search", "calls": 10, "fail_rate": 0.5, "state": "open"}]
    lessons = ev.assess_evolution(rows, [])
    assert lessons[0]["kind"] == "tool"
    assert lessons[0]["priority"] == 3
    assert "tavily_search" in lessons[0]["text"]
    assert "fallback" in lessons[0]["text"]


def test_assess_unreliable_tool():
    rows = [{"name": "ddg", "calls": 5, "fail_rate": 0.4, "state": "degraded"}]
    lessons = ev.assess_evolution(rows, [])
    assert lessons[0]["priority"] == 2
    assert "40%" in lessons[0]["text"]


def test_assess_strength_tool():
    rows = [{"name": "memoria", "calls": 8, "fail_rate": 0.0, "state": "closed"}]
    lessons = ev.assess_evolution(rows, [])
    assert lessons[0]["kind"] == "strength"
    assert "8 usos sin un solo fallo" in lessons[0]["text"]


def test_assess_tool_below_thresholds_ignored():
    rows = [{"name": "x", "calls": 2, "fail_rate": 0.0, "state": "closed"}]
    assert ev.assess_evolution(rows, []) == []


def test_assess_recurring_error_no_solution():
    errors = [{"error": "ZeroDivisionError: division by zero", "count": 6, "solution": None}]
    lessons = ev.assess_evolution([], errors)
    assert lessons[0]["priority"] == 3
    assert "Mark II" in lessons[0]["text"]


def test_assess_recurring_error_with_solution():
    errors = [{"error": "KeyError: x", "count": 5, "solution": "usar .get()"}]
    lessons = ev.assess_evolution([], errors)
    assert lessons[0]["kind"] == "error"
    assert "ya sé resolverlo" in lessons[0]["text"]


def test_assess_error_below_threshold_ignored():
    errors = [{"error": "x", "count": 2}]
    assert ev.assess_evolution([], errors, error_threshold=4) == []


def test_assess_sorted_by_priority():
    rows = [{"name": "good", "calls": 8, "fail_rate": 0.0, "state": "closed"},  # prio 1
            {"name": "bad", "calls": 4, "fail_rate": 0.5, "state": "open"}]      # prio 3
    lessons = ev.assess_evolution(rows, [])
    assert lessons[0]["name"] if False else lessons[0]["priority"] == 3  # el peor primero


# ---------------------------------------------------------------- new_lessons
def test_new_lessons_filters_known():
    lessons = [{"text": "A", "kind": "tool"}, {"text": "B", "kind": "error"}]
    fresh = ev.new_lessons({"A"}, lessons)
    assert [l["text"] for l in fresh] == ["B"]


def test_new_lessons_all_new():
    lessons = [{"text": "A"}, {"text": "B"}]
    assert len(ev.new_lessons(set(), lessons)) == 2


def test_new_lessons_empty():
    assert ev.new_lessons({"A"}, []) == []


# ---------------------------------------------------------------- format
def test_format_report_empty():
    assert "No he extraído lecciones nuevas" in ev.format_evolution_report([])


def test_format_report_lists():
    out = ev.format_evolution_report([{"text": "Lección uno."}, {"text": "Lección dos."}])
    assert "Lección uno." in out and "Lección dos." in out


def test_format_learnings_empty():
    assert "Aún no he acumulado" in ev.format_learnings([])


def test_format_learnings_counts_and_recent():
    journal = [{"text": "vieja", "ts": 100}, {"text": "nueva", "ts": 200}]
    out = ev.format_learnings(journal)
    assert "2 lecciones" in out
    assert out.index("nueva") < out.index("vieja")  # más reciente primero


# ---------------------------------------------------------------- learn_now / persistencia
def test_learn_now_records_new(monkeypatch, tmp_path):
    monkeypatch.setattr(ev, "JOURNAL_FILE", tmp_path / "j.jsonl")
    monkeypatch.setattr(ev, "_tool_rows",
                        lambda: [{"name": "x", "calls": 5, "fail_rate": 0.0, "state": "closed"}])
    monkeypatch.setattr(ev, "_error_items", lambda: [])
    out = ev.learn_now()
    assert "Domino bien x" in out
    assert len(ev._load_journal()) == 1


def test_learn_now_dedupes_across_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(ev, "JOURNAL_FILE", tmp_path / "j.jsonl")
    monkeypatch.setattr(ev, "_tool_rows",
                        lambda: [{"name": "x", "calls": 5, "fail_rate": 0.0, "state": "closed"}])
    monkeypatch.setattr(ev, "_error_items", lambda: [])
    ev.learn_now()
    out2 = ev.learn_now()  # misma lección -> nada nuevo
    assert "No he extraído lecciones nuevas" in out2
    assert len(ev._load_journal()) == 1  # no se duplica


def test_get_learnings_integration(monkeypatch, tmp_path):
    monkeypatch.setattr(ev, "JOURNAL_FILE", tmp_path / "j.jsonl")
    ev._append_journal([{"text": "lección A", "kind": "tool"}], ts=100)
    assert "1 lecciones" in ev.get_learnings()


# ---------------------------------------------------------------- daemon
def test_start_daemon_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_EVOLUTION_ENABLED", "false")
    ev.EVOLUTION_THREAD = None
    ev.start_evolution_daemon()
    assert ev.EVOLUTION_THREAD is None


def test_stop_daemon_sets_event():
    ev.stop_event.clear()
    ev.stop_evolution_daemon()
    assert ev.stop_event.is_set()
    ev.stop_event.clear()
