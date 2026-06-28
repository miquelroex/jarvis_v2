"""Tests de core/face_id.py — reconocimiento facial local (lógica pura + degradación)."""
import core.face_id as fid


# ---------------------------------------------------------------- resolve_identity
def test_resolve_identity_known():
    labels = {"0": "señor", "1": "Ana"}
    assert fid.resolve_identity(0, 40.0, labels, threshold=70) == "señor"
    assert fid.resolve_identity(1, 65.0, labels, threshold=70) == "Ana"


def test_resolve_identity_above_threshold_is_unknown():
    labels = {"0": "señor"}
    # confidence (distancia) por encima del umbral -> no se acepta.
    assert fid.resolve_identity(0, 90.0, labels, threshold=70) == "desconocido"


def test_resolve_identity_unknown_label():
    assert fid.resolve_identity(5, 10.0, {"0": "señor"}, threshold=70) == "desconocido"


def test_resolve_identity_none_inputs():
    assert fid.resolve_identity(None, 10.0, {"0": "x"}, 70) == "desconocido"
    assert fid.resolve_identity(0, None, {"0": "x"}, 70) == "desconocido"


def test_resolve_identity_exact_threshold_accepted():
    # <= umbral se acepta (límite inclusivo).
    assert fid.resolve_identity(0, 70.0, {"0": "señor"}, threshold=70) == "señor"


# ---------------------------------------------------------------- next_label_id / add_label
def test_next_label_id_empty():
    assert fid.next_label_id({}) == 0


def test_next_label_id_after_existing():
    assert fid.next_label_id({"0": "a", "1": "b"}) == 2


def test_add_label_new():
    labels, lid = fid.add_label({}, "señor")
    assert labels == {"0": "señor"}
    assert lid == 0


def test_add_label_reuses_existing_case_insensitive():
    labels, lid = fid.add_label({"0": "señor"}, "SEÑOR")
    assert lid == 0
    assert labels == {"0": "señor"}  # no duplica


def test_add_label_second_person():
    labels, lid = fid.add_label({"0": "señor"}, "Ana")
    assert lid == 1
    assert labels["1"] == "Ana"


def test_add_label_does_not_mutate_input():
    original = {"0": "señor"}
    fid.add_label(original, "Ana")
    assert original == {"0": "señor"}  # copia, no muta


# ---------------------------------------------------------------- greeting_for / is_known
def test_greeting_for_known():
    assert fid.greeting_for("Ana") == "Bienvenido, Ana."


def test_greeting_for_unknown():
    assert "no reconozco" in fid.greeting_for("desconocido")
    assert "no reconozco" in fid.greeting_for("")


def test_is_known():
    assert fid.is_known("señor") is True
    assert fid.is_known("desconocido") is False
    assert fid.is_known("") is False


# ---------------------------------------------------------------- degradación sin OpenCV
def test_enroll_without_opencv(monkeypatch):
    monkeypatch.setattr(fid, "is_available", lambda: False)
    out = fid.enroll("señor")
    assert "opencv-contrib-python" in out


def test_enroll_empty_name():
    assert "¿Con qué nombre" in fid.enroll("")


def test_who_is_there_without_opencv(monkeypatch):
    monkeypatch.setattr(fid, "is_available", lambda: False)
    assert "opencv-contrib-python" in fid.who_is_there()


def test_who_is_there_not_enrolled(monkeypatch, tmp_path):
    monkeypatch.setattr(fid, "is_available", lambda: True)
    monkeypatch.setattr(fid, "MODEL_PATH", tmp_path / "no_existe.yml")
    assert "Aún no he memorizado" in fid.who_is_there()


def test_identify_without_model(monkeypatch, tmp_path):
    monkeypatch.setattr(fid, "is_available", lambda: True)
    monkeypatch.setattr(fid, "MODEL_PATH", tmp_path / "no_existe.yml")
    assert fid.identify() == "desconocido"


def test_identify_unavailable(monkeypatch):
    monkeypatch.setattr(fid, "is_available", lambda: False)
    assert fid.identify() == "desconocido"


def test_identify_greeting_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(fid, "is_available", lambda: False)
    assert fid.identify_greeting() is None


def test_identify_greeting_no_model(monkeypatch, tmp_path):
    monkeypatch.setattr(fid, "is_available", lambda: True)
    monkeypatch.setattr(fid, "MODEL_PATH", tmp_path / "no.yml")
    assert fid.identify_greeting() is None


# ---------------------------------------------------------------- who_is_there (con modelo)
def _model(tmp_path):
    p = tmp_path / "lbph.yml"
    p.write_text("modelo", encoding="utf-8")
    return p


def test_who_is_there_recognizes_senor(monkeypatch, tmp_path):
    monkeypatch.setattr(fid, "is_available", lambda: True)
    monkeypatch.setattr(fid, "MODEL_PATH", _model(tmp_path))
    monkeypatch.setattr(fid, "identify", lambda: "señor")
    assert "Es usted, señor" in fid.who_is_there()


def test_who_is_there_recognizes_other(monkeypatch, tmp_path):
    monkeypatch.setattr(fid, "is_available", lambda: True)
    monkeypatch.setattr(fid, "MODEL_PATH", _model(tmp_path))
    monkeypatch.setattr(fid, "identify", lambda: "Ana")
    assert "Le reconozco: Ana" in fid.who_is_there()


def test_who_is_there_unknown(monkeypatch, tmp_path):
    monkeypatch.setattr(fid, "is_available", lambda: True)
    monkeypatch.setattr(fid, "MODEL_PATH", _model(tmp_path))
    monkeypatch.setattr(fid, "identify", lambda: "desconocido")
    assert "No reconozco" in fid.who_is_there()


def test_identify_greeting_with_model(monkeypatch, tmp_path):
    monkeypatch.setattr(fid, "is_available", lambda: True)
    monkeypatch.setattr(fid, "MODEL_PATH", _model(tmp_path))
    monkeypatch.setattr(fid, "identify", lambda: "Ana")
    assert fid.identify_greeting() == "Bienvenido, Ana."
