"""Tests de core/module_explainer.py — "Explícame este módulo"."""
import core.module_explainer as me


SAMPLE = '''"""Módulo de ejemplo para pruebas.

Segunda línea de la descripción.
"""
import os
from pathlib import Path


def publica(a, b):
    """Hace algo público."""
    return a + b


def _privada():
    return 1


class Motor:
    """Un motor de ejemplo."""

    def arrancar(self):
        return True

    def _interno(self):
        return False
'''


# ---------------------------------------------------------------- _query_tokens
def test_query_tokens_strips_filler():
    toks = me._query_tokens("explícame el módulo de session_memory")
    assert "session" in toks and "memory" in toks
    assert "modulo" not in toks
    assert "el" not in toks


# ---------------------------------------------------------------- resolve_module
def test_resolve_module_exact_stem():
    cands = ["core/session_memory.py", "core/insights.py", "tools/voice.py"]
    assert me.resolve_module("explica el modulo session_memory", cands) == "core/session_memory.py"


def test_resolve_module_partial_part():
    cands = ["core/network_sentinel.py", "core/insights.py"]
    # "sentinel" coincide con una parte del nombre.
    assert me.resolve_module("que hace el modulo sentinel", cands) == "core/network_sentinel.py"


def test_resolve_module_none_when_no_match():
    cands = ["core/insights.py"]
    assert me.resolve_module("explícame el módulo inexistentexyz", cands) is None


def test_resolve_module_empty_query():
    assert me.resolve_module("explícame el módulo", ["core/x.py"]) is None


# ---------------------------------------------------------------- extract_structure
def test_extract_structure_parses_all():
    s = me.extract_structure(SAMPLE)
    assert s["doc"].startswith("Módulo de ejemplo")
    assert "os" in s["imports"]
    assert "pathlib" in s["imports"]
    names = [f["name"] for f in s["functions"]]
    assert "publica" in names and "_privada" in names
    pub = next(f for f in s["functions"] if f["name"] == "publica")
    assert pub["args"] == ["a", "b"]
    assert pub["doc"] == "Hace algo público."
    assert s["classes"][0]["name"] == "Motor"
    # Métodos públicos sólo (sin _interno).
    assert s["classes"][0]["methods"] == ["arrancar"]


def test_extract_structure_syntax_error():
    s = me.extract_structure("def broken(:\n")
    assert s["error"] is not None
    assert s["functions"] == []


# ---------------------------------------------------------------- build_structural_summary
def test_build_structural_summary_lists_pieces():
    s = me.extract_structure(SAMPLE)
    out = me.build_structural_summary(s, "core/ejemplo.py")
    assert "core/ejemplo.py" in out
    assert "Módulo de ejemplo" in out
    assert "1 clase(s)" in out
    assert "Motor" in out
    assert "publica" in out
    assert out.endswith("señor.")


def test_build_structural_summary_error():
    out = me.build_structural_summary({"error": "fallo X"}, "m.py")
    assert "fallo X" in out


def test_build_structural_summary_empty_module():
    s = me.extract_structure("x = 1\n")
    out = me.build_structural_summary(s, "m.py")
    assert "No expone clases ni funciones públicas" in out


# ---------------------------------------------------------------- build_explain_prompt
def test_build_explain_prompt_contains_source_and_name():
    s = me.extract_structure(SAMPLE)
    prompt = me.build_explain_prompt(s, "core/ejemplo.py", SAMPLE)
    assert "core/ejemplo.py" in prompt
    assert "```python" in prompt
    assert "publica" in prompt


# ---------------------------------------------------------------- explain_module (integración)
def test_explain_module_unresolved(monkeypatch):
    monkeypatch.setattr(me, "_candidate_files", lambda: ["core/insights.py"])
    out = me.explain_module("explícame el módulo zzzznoexiste")
    assert "No identifico" in out


def test_explain_module_structural_without_llm(tmp_path, monkeypatch):
    f = tmp_path / "demo_mod.py"
    f.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr(me, "_candidate_files", lambda: [str(f)])
    out = me.explain_module("explica el modulo demo_mod", use_llm=False)
    assert "Motor" in out
    assert "Módulo de ejemplo" in out


def test_explain_module_uses_llm(tmp_path, monkeypatch):
    f = tmp_path / "demo_mod.py"
    f.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr(me, "_candidate_files", lambda: [str(f)])

    import types
    fake = types.ModuleType("tools.model_delegate")
    fake.ask_code_model = lambda prompt: "Explicación generada por el modelo."
    import sys
    monkeypatch.setitem(sys.modules, "tools.model_delegate", fake)

    out = me.explain_module("explica el modulo demo_mod", use_llm=True)
    assert "Explicación generada por el modelo." in out
    assert "Permítame guiarle" in out
