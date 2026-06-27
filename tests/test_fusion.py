"""Tests de core/fusion.py — Motor de Fusión de Fuentes."""
import core.fusion as fusion


# ---------------------------------------------------------------- available_results
def test_available_results_filters_empty():
    res = {"web": "algo", "clima": None, "estado": "   ", "x": "dato"}
    out = fusion.available_results(res)
    assert out == {"web": "algo", "x": "dato"}


def test_available_results_strips():
    assert fusion.available_results({"a": "  hola  "}) == {"a": "hola"}


def test_available_results_empty_input():
    assert fusion.available_results({}) == {}
    assert fusion.available_results(None) == {}


# ---------------------------------------------------------------- format_sources_block
def test_format_sources_block():
    block = fusion.format_sources_block({"web": "resultado", "clima": "soleado"})
    assert "[web] resultado" in block
    assert "[clima] soleado" in block


def test_format_sources_block_empty():
    assert fusion.format_sources_block({"x": None}) == ""


# ---------------------------------------------------------------- build_fusion_prompt
def test_build_fusion_prompt_contains_query_and_sources():
    prompt = fusion.build_fusion_prompt("¿lloverá?", {"clima": "nublado", "web": "lluvia tarde"})
    assert "¿lloverá?" in prompt
    assert "[clima] nublado" in prompt
    assert "[web] lluvia tarde" in prompt
    assert "Sintetiza" in prompt or "sintetiza" in prompt.lower()


# ---------------------------------------------------------------- build_raw_fallback
def test_build_raw_fallback_with_data():
    out = fusion.build_raw_fallback("q", {"web": "dato"})
    assert "he reunido" in out.lower()
    assert "[web] dato" in out


def test_build_raw_fallback_no_data():
    assert "ninguna fuente" in fusion.build_raw_fallback("q", {})


# ---------------------------------------------------------------- gather (paralelo, aislado)
def test_gather_collects_from_sources():
    sources = {
        "a": lambda q: f"resp-a:{q}",
        "b": lambda q: "resp-b",
        "c": lambda q: None,
    }
    out = fusion.gather("hola", sources, timeout=5)
    assert out["a"] == "resp-a:hola"
    assert out["b"] == "resp-b"
    assert out["c"] is None


def test_gather_tolerates_source_exception():
    def boom(q):
        raise RuntimeError("fallo")
    sources = {"ok": lambda q: "bien", "mala": boom}
    out = fusion.gather("x", sources, timeout=5)
    assert out["ok"] == "bien"
    assert out["mala"] is None


# ---------------------------------------------------------------- fuse (orquestación)
def test_fuse_empty_query():
    assert "¿Sobre qué" in fusion.fuse("")
    assert "¿Sobre qué" in fusion.fuse("   ")


def test_fuse_no_sources_available(monkeypatch):
    monkeypatch.setattr(fusion, "gather", lambda q, s=None: {"web": None, "clima": None})
    assert "ninguna fuente" in fusion.fuse("algo")


def test_fuse_with_synthesis(monkeypatch):
    monkeypatch.setattr(fusion, "gather", lambda q, s=None: {"web": "dato", "clima": "sol"})
    monkeypatch.setattr(fusion, "_synthesize", lambda q, r: "Conclusión sintetizada.")
    out = fusion.fuse("¿qué tal?")
    assert "He cruzado 2 fuentes" in out
    assert "Conclusión sintetizada." in out


def test_fuse_singular_source(monkeypatch):
    monkeypatch.setattr(fusion, "gather", lambda q, s=None: {"web": "dato"})
    monkeypatch.setattr(fusion, "_synthesize", lambda q, r: "Resp.")
    out = fusion.fuse("x")
    assert "He cruzado 1 fuente," in out


def test_fuse_fallback_when_no_llm(monkeypatch):
    monkeypatch.setattr(fusion, "gather", lambda q, s=None: {"web": "dato crudo"})
    monkeypatch.setattr(fusion, "_synthesize", lambda q, r: "")  # modelo no disponible
    out = fusion.fuse("x")
    assert "he reunido" in out.lower()
    assert "[web] dato crudo" in out


# ---------------------------------------------------------------- fuentes reales (degradación)
def test_source_state_safe(monkeypatch):
    # Sin world_model utilizable no debe lanzar.
    import sys
    monkeypatch.setitem(sys.modules, "core.world_model", None)
    assert fusion._source_state("x") is None


def test_default_sources_registered():
    assert set(fusion.DEFAULT_SOURCES.keys()) == {"web", "clima", "estado del sistema", "datos en vivo"}
