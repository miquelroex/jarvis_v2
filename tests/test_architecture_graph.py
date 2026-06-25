"""Tests del explorador de arquitectura / Sala de Hologramas (core/architecture_graph.py)."""
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.architecture_graph as ag


class TestModuleName(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(ag._module_name_from_path("/r/core/voice.py", "/r"), "core.voice")

    def test_init_collapses_to_package(self):
        self.assertEqual(ag._module_name_from_path("/r/core/__init__.py", "/r"), "core")


class TestCountDefs(unittest.TestCase):
    def test_counts_functions_and_classes(self):
        src = "def a():\n  pass\nclass B:\n  def m(self):\n    pass\nasync def c():\n  pass\n"
        # a, B, m, c => 4
        self.assertEqual(ag._count_defs(src), 4)

    def test_syntax_error_returns_zero(self):
        self.assertEqual(ag._count_defs("def :("), 0)


class TestExtractImports(unittest.TestCase):
    def setUp(self):
        self.locals = {"core.voice", "core.router", "tools.terminal", "core.voice_tone"}

    def test_import_statement(self):
        src = "import core.router\nimport os\n"
        self.assertEqual(ag._extract_imports(src, self.locals), {"core.router"})

    def test_from_import(self):
        src = "from core.voice import speak\nfrom tools.terminal import run\n"
        self.assertEqual(ag._extract_imports(src, self.locals), {"core.voice", "tools.terminal"})

    def test_ignores_external_and_relative(self):
        src = "import requests\nfrom . import x\nfrom os import path\n"
        self.assertEqual(ag._extract_imports(src, self.locals), set())

    def test_longest_prefix_match(self):
        # "core.voice_tone" debe casar con el módulo completo, no con "core.voice".
        src = "from core.voice_tone import TONES\n"
        self.assertEqual(ag._extract_imports(src, self.locals), {"core.voice_tone"})

    def test_syntax_error_safe(self):
        self.assertEqual(ag._extract_imports("def :(", self.locals), set())


class TestBuildGraph(unittest.TestCase):
    def test_nodes_and_edges(self):
        files = {
            "core.a": "import core.b\nclass X:\n  pass\n",
            "core.b": "def f():\n  pass\n",
            "tools.c": "from core.a import X\n",
        }
        g = ag.build_graph(files)
        ids = {n["id"] for n in g["nodes"]}
        self.assertEqual(ids, {"core.a", "core.b", "tools.c"})
        # grupos
        groups = {n["id"]: n["group"] for n in g["nodes"]}
        self.assertEqual(groups["tools.c"], "tools")
        # tamaño por definiciones
        sizes = {n["id"]: n["size"] for n in g["nodes"]}
        self.assertEqual(sizes["core.a"], 1)  # clase X
        self.assertEqual(sizes["core.b"], 1)  # función f
        # aristas
        edge_pairs = {(e["source"], e["target"]) for e in g["edges"]}
        self.assertIn(("core.a", "core.b"), edge_pairs)
        self.assertIn(("tools.c", "core.a"), edge_pairs)

    def test_no_self_edges(self):
        files = {"core.a": "import core.a\n"}
        g = ag.build_graph(files)
        self.assertEqual(g["edges"], [])


class TestEmitters(unittest.TestCase):
    def _fake_gui(self):
        emitted = []
        fake = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: emitted.append((ev, a))))
        return fake, emitted

    def test_open_emits_open_and_graph(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.object(ag, "get_architecture_graph", return_value={"nodes": [], "edges": []}):
            ag.open_holograph()
        events = [e[0] for e in emitted]
        self.assertEqual(events, ["holo_open", "architecture_graph"])

    def test_close_emits(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}):
            ag.close_holograph()
        self.assertEqual(emitted[0][0], "holo_close")

    def test_emit_noop_without_gui(self):
        saved = sys.modules.pop("gui.app", None)
        try:
            ag._emit("holo_open")  # no debe lanzar
        finally:
            if saved is not None:
                sys.modules["gui.app"] = saved


class TestRealScan(unittest.TestCase):
    def test_scans_own_project(self):
        # Smoke test sobre el propio repo: debe encontrar varios módulos y aristas.
        g = ag.get_architecture_graph()
        self.assertGreater(g["module_count"], 10)
        self.assertGreater(g["edge_count"], 0)
        ids = {n["id"] for n in g["nodes"]}
        self.assertIn("core.architecture_graph", ids)


if __name__ == "__main__":
    unittest.main()
