"""Tests de core/researcher.py — Investigador Autónomo Profundo."""
import core.researcher as r


# ---------------------------------------------------------------- parse_plan
def test_parse_plan_numbered():
    raw = "1. ¿Qué es X?\n2. ¿Cómo funciona X?\n3. ¿Alternativas a X?"
    out = r.parse_plan(raw)
    assert out == ["¿Qué es X?", "¿Cómo funciona X?", "¿Alternativas a X?"]


def test_parse_plan_bullets_and_parens():
    raw = "- primera pregunta\n* segunda pregunta\n1) tercera pregunta"
    out = r.parse_plan(raw)
    assert out == ["primera pregunta", "segunda pregunta", "tercera pregunta"]


def test_parse_plan_dedupes_and_caps():
    raw = "1. misma pregunta\n2. misma pregunta\n3. otra cosa\n4. tercera\n5. cuarta\n6. quinta"
    out = r.parse_plan(raw, max_q=3)
    assert len(out) == 3
    assert out[0] == "misma pregunta"


def test_parse_plan_skips_short_lines():
    raw = "1. ok\n2. válida pregunta\n\n   \n- x"
    out = r.parse_plan(raw)
    # 'ok' y 'x' son demasiado cortas (< 5 chars tras quitar marcador).
    assert out == ["válida pregunta"]


def test_parse_plan_empty():
    assert r.parse_plan("") == []
    assert r.parse_plan(None) == []


# ---------------------------------------------------------------- build_plan_prompt
def test_build_plan_prompt():
    p = r.build_plan_prompt("¿Conviene migrar a Rust?", max_q=3)
    assert "¿Conviene migrar a Rust?" in p
    assert "3 sub-preguntas" in p


# ---------------------------------------------------------------- format_findings_block
def test_format_findings_block():
    findings = [{"subq": "P1", "info": "dato1"}, {"subq": "P2", "info": ""}]
    block = r.format_findings_block(findings)
    assert "### P1" in block and "dato1" in block
    assert "### P2" in block and "(sin resultados)" in block


def test_format_findings_block_empty():
    assert r.format_findings_block([]) == ""


# ---------------------------------------------------------------- build_report_prompt
def test_build_report_prompt():
    p = r.build_report_prompt("tema", [{"subq": "P1", "info": "hallazgo"}])
    assert "tema" in p
    assert "### P1" in p and "hallazgo" in p
    assert "resumen ejecutivo" in p


# ---------------------------------------------------------------- build_raw_report
def test_build_raw_report_with_data():
    out = r.build_raw_report("tema", [{"subq": "P1", "info": "dato"}])
    assert "Informe de investigación sobre «tema»" in out
    assert "### P1" in out


def test_build_raw_report_no_data():
    out = r.build_raw_report("tema", [{"subq": "P1", "info": ""}])
    assert "No he encontrado información" in out


# ---------------------------------------------------------------- has_findings
def test_has_findings():
    assert r.has_findings([{"subq": "a", "info": "x"}]) is True
    assert r.has_findings([{"subq": "a", "info": ""}, {"subq": "b", "info": "  "}]) is False
    assert r.has_findings([]) is False


# ---------------------------------------------------------------- research (orquestación)
def test_research_empty_question():
    assert "¿Qué desea que investigue" in r.research("")
    assert "¿Qué desea que investigue" in r.research("   ")


def test_research_full_flow(monkeypatch):
    monkeypatch.setattr(r, "_decompose", lambda q, max_q=4: ["sub1", "sub2"])
    monkeypatch.setattr(r, "_investigate", lambda subq: f"info de {subq}")
    monkeypatch.setattr(r, "_synthesize_report", lambda q, f: "INFORME FINAL")
    out = r.research("tema")
    assert "Investigación completada" in out
    assert "2 líneas exploradas" in out
    assert "INFORME FINAL" in out


def test_research_no_findings(monkeypatch):
    monkeypatch.setattr(r, "_decompose", lambda q, max_q=4: ["sub1"])
    monkeypatch.setattr(r, "_investigate", lambda subq: "")
    out = r.research("tema")
    assert "No he encontrado información" in out


def test_research_fallback_without_llm(monkeypatch):
    monkeypatch.setattr(r, "_decompose", lambda q, max_q=4: ["sub1"])
    monkeypatch.setattr(r, "_investigate", lambda subq: "dato crudo")
    monkeypatch.setattr(r, "_synthesize_report", lambda q, f: "")  # modelo no disponible
    out = r.research("tema")
    assert "Informe de investigación sobre «tema»" in out
    assert "dato crudo" in out


def test_decompose_fallback_to_question(monkeypatch):
    # Si la planificación con LLM falla, se investiga la pregunta tal cual.
    def boom(prompt):
        raise RuntimeError("sin modelo")
    monkeypatch.setattr(r, "_ask_llm", boom)
    assert r._decompose("mi pregunta") == ["mi pregunta"]


def test_investigate_safe_without_fusion(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "core.fusion", None)
    assert r._investigate("x") == ""
