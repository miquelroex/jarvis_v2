"""Tests de core/visual_memory.py — Memoria Visual."""
import json

import core.visual_memory as vm


# ---------------------------------------------------------------- _tokens
def test_tokens_filters_stopwords_and_short():
    toks = vm._tokens("¿dónde dejé las llaves del coche?")
    assert "llaves" in toks
    assert "coche" in toks
    assert "donde" not in toks and "deje" not in toks and "las" not in toks


# ---------------------------------------------------------------- parse_scene
def test_parse_scene_object_form():
    raw = json.dumps({"objetos": [{"objeto": "llaves", "lugar": "sobre la mesa"},
                                   {"objeto": "móvil", "lugar": "en el sofá"}]})
    out = vm.parse_scene(raw)
    assert out == [{"object": "llaves", "location": "sobre la mesa"},
                   {"object": "móvil", "location": "en el sofá"}]


def test_parse_scene_strips_fences_and_bare_list():
    raw = '```json\n[{"objeto": "gafas", "lugar": "en la estantería"}]\n```'
    out = vm.parse_scene(raw)
    assert out[0]["object"] == "gafas"


def test_parse_scene_default_location():
    out = vm.parse_scene('{"objetos": [{"objeto": "cartera"}]}')
    assert out[0]["location"] == "en algún lugar"


def test_parse_scene_skips_without_object():
    out = vm.parse_scene('{"objetos": [{"lugar": "x"}, {"objeto": "reloj", "lugar": "y"}]}')
    assert len(out) == 1
    assert out[0]["object"] == "reloj"


def test_parse_scene_garbage():
    assert vm.parse_scene("") == []
    assert vm.parse_scene("no soy json") == []


# ---------------------------------------------------------------- relative_time
def test_relative_time():
    assert vm.relative_time(10) == "hace un momento"
    assert vm.relative_time(60) == "hace 1 minuto"
    assert vm.relative_time(1200) == "hace 20 minutos"
    assert vm.relative_time(3600) == "hace 1 hora"
    assert vm.relative_time(7200) == "hace 2 horas"
    assert vm.relative_time(90000) == "hace 1 día"


# ---------------------------------------------------------------- find_object
def _obs(object_, location, ts):
    return {"object": object_, "location": location, "ts": ts}


def test_find_object_matches_token():
    obs = [_obs("llaves del coche", "sobre la mesa", 100)]
    found = vm.find_object("¿dónde dejé las llaves?", obs)
    assert found["location"] == "sobre la mesa"


def test_find_object_most_recent_wins():
    obs = [_obs("gafas", "en la mesa", 100), _obs("gafas", "en el baño", 200)]
    found = vm.find_object("¿dónde están mis gafas?", obs)
    assert found["location"] == "en el baño"  # la más reciente


def test_find_object_no_match():
    obs = [_obs("llaves", "mesa", 100)]
    assert vm.find_object("¿dónde está el paraguas?", obs) is None


def test_find_object_empty_query():
    assert vm.find_object("¿dónde?", [_obs("llaves", "mesa", 100)]) is None


# ---------------------------------------------------------------- format_answer
def test_format_answer_found():
    obs = [_obs("llaves", "sobre la mesa", 1000)]
    out = vm.format_answer("¿dónde dejé las llaves?", obs, now=1000 + 1200)
    assert "Su llaves, señor: sobre la mesa, hace 20 minutos." == out


def test_format_answer_not_found():
    out = vm.format_answer("¿dónde está el dragón?", [])
    assert "No recuerdo haber visto eso" in out


# ---------------------------------------------------------------- summarize_recent
def test_summarize_recent():
    obs = [_obs("llaves", "mesa", 100), _obs("móvil", "sofá", 200)]
    out = vm.summarize_recent(obs)
    assert "móvil (sofá)" in out and "llaves (mesa)" in out
    # Orden: el más reciente (móvil, ts=200) antes que el antiguo (llaves, ts=100).
    assert out.index("móvil") < out.index("llaves")


def test_summarize_recent_empty():
    assert "Aún no he observado nada" in vm.summarize_recent([])


# ---------------------------------------------------------------- persistencia
def test_record_and_load(monkeypatch, tmp_path):
    monkeypatch.setattr(vm, "LOG_FILE", tmp_path / "vm.jsonl")
    vm.record_observations([{"object": "llaves", "location": "mesa"}], ts=123)
    loaded = vm.load_observations()
    assert len(loaded) == 1
    assert loaded[0]["object"] == "llaves"
    assert loaded[0]["ts"] == 123


def test_record_empty_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(vm, "LOG_FILE", tmp_path / "vm.jsonl")
    vm.record_observations([])
    assert vm.load_observations() == []


def test_load_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(vm, "LOG_FILE", tmp_path / "no_existe.jsonl")
    assert vm.load_observations() == []


# ---------------------------------------------------------------- orquestación
def test_observe_now_no_data(monkeypatch):
    monkeypatch.setattr(vm, "_analyze_scene", lambda: [])
    assert "No he podido observar" in vm.observe_now()


def test_observe_now_records(monkeypatch, tmp_path):
    monkeypatch.setattr(vm, "LOG_FILE", tmp_path / "vm.jsonl")
    monkeypatch.setattr(vm, "_analyze_scene",
                        lambda: [{"object": "llaves", "location": "mesa"}])
    out = vm.observe_now()
    assert "He visto: llaves" in out
    assert len(vm.load_observations()) == 1


def test_where_is_integration(monkeypatch, tmp_path):
    monkeypatch.setattr(vm, "LOG_FILE", tmp_path / "vm.jsonl")
    vm.record_observations([{"object": "llaves", "location": "sobre la mesa"}], ts=__import__("time").time())
    out = vm.where_is("¿dónde dejé las llaves?")
    assert "sobre la mesa" in out


# ---------------------------------------------------------------- daemon
def test_start_daemon_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_VISUAL_MEMORY_ENABLED", "false")
    vm.VISUAL_THREAD = None
    vm.start_visual_memory_daemon()
    assert vm.VISUAL_THREAD is None


def test_stop_daemon_sets_event():
    vm.stop_event.clear()
    vm.stop_visual_memory_daemon()
    assert vm.stop_event.is_set()
    vm.stop_event.clear()
