"""Tests del fallback de búsqueda DuckDuckGo con resiliencia (tools/duckduckgo.py)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tools.duckduckgo as ddg


def _call(query="prueba"):
    # Llamar a la función subyacente del @tool directamente.
    return ddg.duckduckgo_search_tool.func(query)


class TestDuckDuckGo(unittest.TestCase):
    def test_failed_after_retries(self):
        with patch.object(ddg, "_ddg_query", return_value=ddg._FAILED):
            out = _call()
        self.assertIn("tras varios intentos", out)

    def test_no_results(self):
        with patch.object(ddg, "_ddg_query", return_value=[]):
            out = _call("algo raro")
        self.assertIn("no he podido encontrar", out)

    def test_formats_results(self):
        fake = [
            {"title": "T1", "href": "http://a", "body": "cuerpo uno"},
            {"title": "T2", "href": "http://b", "body": "cuerpo dos"},
        ]
        with patch.object(ddg, "_ddg_query", return_value=fake):
            out = _call("noticias")
        self.assertIn("T1", out)
        self.assertIn("http://b", out)
        self.assertIn("cuerpo uno", out)

    def test_query_with_retries_recovers(self):
        # _ddg_query usa @resilient: falla una vez y luego devuelve resultados.
        state = {"n": 0}

        def flaky(*a, **k):
            state["n"] += 1
            if state["n"] == 1:
                raise ConnectionError("red transitoria")
            return [{"title": "OK", "href": "u", "body": "b"}]

        # Parcheamos la consulta interna a DDGS (dentro de _ddg_query) vía DDGS.
        with patch.object(ddg, "DDGS") as mock_ddgs:
            inst = mock_ddgs.return_value.__enter__.return_value
            inst.text.side_effect = flaky
            out = _call("hola")
        self.assertIn("OK", out)
        self.assertEqual(state["n"], 2)  # reintentó una vez


if __name__ == "__main__":
    unittest.main()
