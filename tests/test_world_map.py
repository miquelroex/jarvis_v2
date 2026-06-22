"""Tests del mapa/globo 3D del mundo (core/world_map.py)."""
import os
import sys
import json
import types
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.world_map as wm


def _fake_urlopen(payload: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = resp
    return cm


class TestGeocode(unittest.TestCase):
    def test_geocodes_place(self):
        payload = {"features": [{"center": [139.69, 35.68], "place_name": "Tokio, Japón"}]}
        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.test"}), \
             patch("core.world_map.urllib.request.urlopen", return_value=_fake_urlopen(payload)):
            loc = wm.geocode("Tokio")
        self.assertEqual(loc["lng"], 139.69)
        self.assertEqual(loc["lat"], 35.68)
        self.assertIn("Tokio", loc["name"])
        self.assertIn("zoom", loc)

    def test_no_token_returns_none(self):
        with patch.dict(os.environ, {"MAPBOX_TOKEN": ""}):
            self.assertIsNone(wm.geocode("Tokio"))

    def test_empty_place_returns_none(self):
        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.test"}):
            self.assertIsNone(wm.geocode("   "))

    def test_no_results_returns_none(self):
        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.test"}), \
             patch("core.world_map.urllib.request.urlopen", return_value=_fake_urlopen({"features": []})):
            self.assertIsNone(wm.geocode("xyzlugarinexistente"))

    def test_network_error_returns_none(self):
        with patch.dict(os.environ, {"MAPBOX_TOKEN": "pk.test"}), \
             patch("core.world_map.urllib.request.urlopen", side_effect=OSError("net")):
            self.assertIsNone(wm.geocode("Tokio"))


class TestEmitters(unittest.TestCase):
    def _fake_gui(self, sink):
        return {"gui.app": types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, data=None: sink.append((ev, data)))
        )}

    def test_open_map_emits(self):
        sink = []
        with patch.dict(sys.modules, self._fake_gui(sink)):
            self.assertTrue(wm.open_map())
        self.assertEqual(sink[0][0], "map_open")

    def test_close_map_emits(self):
        sink = []
        with patch.dict(sys.modules, self._fake_gui(sink)):
            wm.close_map()
        self.assertEqual(sink[0][0], "map_close")

    def test_emit_noop_without_gui(self):
        # Sin gui.app en sys.modules, no emite ni falla.
        with patch.dict(sys.modules, {}, clear=False):
            sys.modules.pop("gui.app", None)
            self.assertFalse(wm.open_map())

    def test_fly_to_emits_flyto(self):
        sink = []
        loc = {"lng": 1.0, "lat": 2.0, "name": "Sitio", "zoom": 9}
        with patch.object(wm, "geocode", return_value=loc), \
             patch.dict(sys.modules, self._fake_gui(sink)):
            result = wm.fly_to("Sitio")
        self.assertEqual(result, loc)
        self.assertEqual(sink[0][0], "map_flyto")
        self.assertEqual(sink[0][1]["name"], "Sitio")

    def test_fly_to_none_when_not_found(self):
        sink = []
        with patch.object(wm, "geocode", return_value=None), \
             patch.dict(sys.modules, self._fake_gui(sink)):
            self.assertIsNone(wm.fly_to("nada"))
        self.assertEqual(sink, [])  # no emite si no geocodifica


if __name__ == "__main__":
    unittest.main()
