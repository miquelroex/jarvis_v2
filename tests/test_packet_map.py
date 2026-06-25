"""Tests del Packet Map 3D / telemetría de red (core/packet_map.py)."""
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.packet_map as pm


class TestClassifyIp(unittest.TestCase):
    def test_loopback(self):
        self.assertEqual(pm._classify_ip("127.0.0.1"), "loopback")
        self.assertEqual(pm._classify_ip("::1"), "loopback")

    def test_private(self):
        self.assertEqual(pm._classify_ip("192.168.1.10"), "private")
        self.assertEqual(pm._classify_ip("10.0.0.5"), "private")
        self.assertEqual(pm._classify_ip("172.16.0.1"), "private")
        self.assertEqual(pm._classify_ip("172.20.5.5"), "private")

    def test_public(self):
        self.assertEqual(pm._classify_ip("8.8.8.8"), "public")
        self.assertEqual(pm._classify_ip("172.32.0.1"), "public")  # fuera de 16-31

    def test_empty(self):
        self.assertEqual(pm._classify_ip(""), "public")


class TestBuildGraph(unittest.TestCase):
    def test_aggregates_by_ip(self):
        conns = [
            {"raddr": ("8.8.8.8", 443), "status": "ESTABLISHED", "proc": "chrome.exe"},
            {"raddr": ("8.8.8.8", 443), "status": "ESTABLISHED", "proc": "chrome.exe"},
            {"raddr": ("8.8.8.8", 80), "status": "ESTABLISHED", "proc": "chrome.exe"},
            {"raddr": ("192.168.1.5", 22), "status": "ESTABLISHED", "proc": "ssh.exe"},
        ]
        g = pm.build_packet_graph(conns)
        self.assertEqual(g["connection_count"], 4)
        self.assertEqual(g["endpoint_count"], 2)
        by_id = {n["id"]: n for n in g["nodes"]}
        self.assertEqual(by_id["8.8.8.8"]["count"], 3)
        self.assertEqual(by_id["8.8.8.8"]["group"], "public")
        self.assertEqual(by_id["8.8.8.8"]["ports"], [80, 443])
        self.assertEqual(by_id["192.168.1.5"]["group"], "private")
        # una arista por endpoint
        targets = {e["target"] for e in g["edges"]}
        self.assertEqual(targets, {"8.8.8.8", "192.168.1.5"})
        weight = {e["target"]: e["weight"] for e in g["edges"]}
        self.assertEqual(weight["8.8.8.8"], 3)

    def test_ignores_connections_without_remote(self):
        conns = [
            {"raddr": None, "status": "LISTEN", "proc": "svc"},
            {"raddr": ("1.1.1.1", 53), "status": "ESTABLISHED", "proc": "dns"},
        ]
        g = pm.build_packet_graph(conns)
        self.assertEqual(g["endpoint_count"], 1)
        self.assertEqual(g["connection_count"], 1)

    def test_empty(self):
        g = pm.build_packet_graph([])
        self.assertEqual(g["nodes"], [])
        self.assertEqual(g["edges"], [])
        self.assertEqual(g["connection_count"], 0)


class TestEmitters(unittest.TestCase):
    def _fake_gui(self):
        emitted = []
        fake = types.SimpleNamespace(
            socketio=types.SimpleNamespace(emit=lambda ev, *a, **k: emitted.append((ev, a))))
        return fake, emitted

    def test_open_emits_open_and_snapshot(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}), \
             patch.object(pm, "get_packet_map", return_value={"nodes": [], "edges": []}):
            pm.open_packet_map()
        self.assertEqual([e[0] for e in emitted], ["packet_open", "packet_map_update"])

    def test_close_emits(self):
        fake, emitted = self._fake_gui()
        with patch.dict(sys.modules, {"gui.app": fake}):
            pm.close_packet_map()
        self.assertEqual(emitted[0][0], "packet_close")

    def test_emit_noop_without_gui(self):
        saved = sys.modules.pop("gui.app", None)
        try:
            pm._emit("packet_open")
        finally:
            if saved is not None:
                sys.modules["gui.app"] = saved


class TestDaemon(unittest.TestCase):
    def setUp(self):
        pm.stop_packet_map_daemon()
        if pm.PACKET_THREAD is not None and pm.PACKET_THREAD.is_alive():
            pm.PACKET_THREAD.join(timeout=2)
        pm.PACKET_THREAD = None
        pm.stop_event.clear()

    def tearDown(self):
        pm.stop_packet_map_daemon()
        pm.PACKET_THREAD = None

    def test_disabled_does_not_start(self):
        with patch.dict(os.environ, {"JARVIS_PACKET_MAP_ENABLED": "false"}):
            pm.start_packet_map_daemon()
        self.assertIsNone(pm.PACKET_THREAD)

    def test_enabled_starts(self):
        with patch.dict(os.environ, {"JARVIS_PACKET_MAP_ENABLED": "true"}):
            pm.start_packet_map_daemon()
        self.assertIsNotNone(pm.PACKET_THREAD)
        self.assertTrue(pm.PACKET_THREAD.is_alive())


if __name__ == "__main__":
    unittest.main()
