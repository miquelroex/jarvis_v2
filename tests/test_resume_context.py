"""Tests de core/resume_context.py — "¿En qué estaba?" (Reanudar Contexto)."""
import core.resume_context as rc


# ---------------------------------------------------------------- changed_files_from_status
def test_changed_files_basic():
    porcelain = " M core/red.py\n?? nuevo.txt\n M tools/voz.py"
    out = rc.changed_files_from_status(porcelain)
    assert out == ["core/red.py", "nuevo.txt", "tools/voz.py"]


def test_changed_files_rename_keeps_destination():
    porcelain = "R  viejo.py -> nuevo.py"
    assert rc.changed_files_from_status(porcelain) == ["nuevo.py"]


def test_changed_files_dedupes_and_limits():
    porcelain = " M a.py\n M a.py\n M b.py\n M c.py\n M d.py"
    out = rc.changed_files_from_status(porcelain, limit=3)
    assert out == ["a.py", "b.py", "c.py"]


def test_changed_files_empty():
    assert rc.changed_files_from_status("") == []
    assert rc.changed_files_from_status(None) == []


def test_changed_files_ignores_short_lines():
    assert rc.changed_files_from_status("XY") == []


def test_changed_files_strips_quotes():
    porcelain = ' M "ruta con espacios.py"'
    assert rc.changed_files_from_status(porcelain) == ["ruta con espacios.py"]


# ---------------------------------------------------------------- _basename
def test_basename_handles_separators():
    assert rc._basename("core/sub/red.py") == "red.py"
    assert rc._basename("core\\sub\\red.py") == "red.py"
    assert rc._basename("red.py") == "red.py"


# ---------------------------------------------------------------- top_activity
def test_top_activity_picks_max():
    tally = {"Proyecto: jarvis": 300, "Navegador": 100, "Otros": 999}
    assert rc.top_activity(tally) == "Proyecto: jarvis"


def test_top_activity_ignores_otros():
    assert rc.top_activity({"Otros": 500}) is None


def test_top_activity_empty():
    assert rc.top_activity({}) is None
    assert rc.top_activity(None) is None


# ---------------------------------------------------------------- build_resume
def test_build_resume_full():
    out = rc.build_resume(
        repo_name="jarvis", branch="main", last_commit="abc123 fix",
        changed_files=["core/red.py", "tools/voz.py"], activity="Proyecto: jarvis")
    assert "Retomamos donde lo dejó, señor" in out
    assert "proyecto jarvis" in out
    assert "rama main" in out
    assert "los archivos red.py, voz.py" in out
    assert "foco principal era Proyecto: jarvis" in out
    assert "abc123 fix" in out


def test_build_resume_single_file_uses_singular():
    out = rc.build_resume(repo_name="x", changed_files=["a.py"])
    assert "el archivo a.py" in out
    assert "los archivos" not in out


def test_build_resume_empty_signals():
    out = rc.build_resume()
    assert "No tengo aún un contexto" in out


def test_build_resume_only_activity():
    out = rc.build_resume(activity="Terminal")
    assert "Retomamos donde lo dejó" in out
    assert "foco principal era Terminal" in out


def test_build_resume_no_commit_no_trailing():
    out = rc.build_resume(repo_name="x", branch="dev")
    assert "último commit" not in out


# ---------------------------------------------------------------- get_resume_context (integración)
def test_get_resume_context_handles_missing_modules(monkeypatch):
    monkeypatch.setattr(rc, "_gather", lambda: (None, None, None, [], None))
    out = rc.get_resume_context()
    assert "No tengo aún un contexto" in out
