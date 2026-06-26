"""
Tests property-based (Hypothesis): en vez de unos pocos ejemplos, generan miles
de entradas para romper invariantes de las funciones PURAS del sistema.

Cubren funciones que no tocan red/voz/GUI, así que corren también en local.
"""
import os
import re
import sys
import unittest

from hypothesis import given, strategies as st, settings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.error_kb as kb
import core.night_mode as nm
import core.productivity as prod
import core.anticipation as ant
import core.packet_map as pm
import core.babel as babel
import core.personality as pers
import core.hud_overlay as hud
import core.voice_tone as vt
import core.mark_ii as m2
import core.drones as drones


# Texto "razonable" (incluye unicode, vacío, espacios) para fuzzing de strings.
TEXT = st.text(max_size=300)
SAFE_SETTINGS = settings(max_examples=300, deadline=None)


class TestErrorSignature(unittest.TestCase):
    @given(TEXT)
    @SAFE_SETTINGS
    def test_deterministic_and_normalized(self, s):
        a, b = kb.error_signature(s), kb.error_signature(s)
        self.assertEqual(a, b)              # determinista
        self.assertIsInstance(a, str)
        self.assertEqual(a, a.lower())      # siempre minúsculas

    @given(TEXT)
    @SAFE_SETTINGS
    def test_never_raises(self, s):
        kb.error_signature(s)               # no debe lanzar nunca


class TestNightMode(unittest.TestCase):
    @given(st.integers(0, 23), st.integers(0, 23), st.integers(0, 23))
    @SAFE_SETTINGS
    def test_returns_bool(self, h, s, e):
        self.assertIsInstance(nm._is_night(h, s, e), bool)

    @given(st.integers(0, 23), st.integers(0, 23))
    @SAFE_SETTINGS
    def test_equal_start_end_never_night(self, h, x):
        self.assertFalse(nm._is_night(h, x, x))


class TestProductivity(unittest.TestCase):
    @given(TEXT, TEXT)
    @SAFE_SETTINGS
    def test_classify_always_nonempty_str(self, app, title):
        r = prod.classify_activity(app, title)
        self.assertIsInstance(r, str)
        self.assertTrue(r)

    @given(st.lists(st.tuples(st.text(min_size=1, max_size=20),
                              st.floats(min_value=0, max_value=1e6,
                                        allow_nan=False, allow_infinity=False)),
                    max_size=30))
    @SAFE_SETTINGS
    def test_add_time_total_monotonic(self, ops):
        tally = {}
        total = 0.0
        for label, sec in ops:
            prod.add_time(tally, label, sec)
            total += sec
        # La suma del tally nunca supera la suma de lo añadido (redondeos aparte).
        self.assertLessEqual(sum(tally.values()), total + 1.0)
        # Ningún valor negativo.
        self.assertTrue(all(v >= 0 for v in tally.values()))

    @given(st.integers(-10, 10_000_000))
    @SAFE_SETTINGS
    def test_fmt_duration_no_raise(self, s):
        self.assertIsInstance(prod._fmt_duration(s), str)


class TestAnticipation(unittest.TestCase):
    @given(st.integers(0, 23), st.integers(0, 23))
    @SAFE_SETTINGS
    def test_hour_distance_bounded_and_symmetric(self, a, b):
        d = ant._hour_distance(a, b)
        self.assertTrue(0 <= d <= 12)
        self.assertEqual(d, ant._hour_distance(b, a))


class TestPacketMap(unittest.TestCase):
    @given(TEXT)
    @SAFE_SETTINGS
    def test_classify_ip_in_categories(self, ip):
        self.assertIn(pm._classify_ip(ip), {"loopback", "private", "public"})

    @given(st.lists(st.fixed_dictionaries({
        "raddr": st.one_of(st.none(), st.tuples(
            st.from_regex(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", fullmatch=True),
            st.integers(0, 65535))),
        "status": st.text(max_size=12),
        "proc": st.one_of(st.none(), st.text(max_size=20)),
    }), max_size=40))
    @SAFE_SETTINGS
    def test_graph_invariants(self, conns):
        g = pm.build_packet_graph(conns)
        # Más conexiones que endpoints (o iguales); endpoints = nº de nodos.
        self.assertGreaterEqual(g["connection_count"], g["endpoint_count"])
        self.assertEqual(g["endpoint_count"], len(g["nodes"]))
        self.assertEqual(len(g["edges"]), len(g["nodes"]))


class TestBabel(unittest.TestCase):
    @given(TEXT)
    @SAFE_SETTINGS
    def test_normalize_lang_canonical_or_none(self, name):
        r = babel.normalize_lang(name)
        self.assertTrue(r is None or r in set(babel.LANG_ALIASES.values()))

    @given(TEXT)
    @SAFE_SETTINGS
    def test_parse_command_returns_pair(self, cmd):
        target, text = babel.parse_translate_command(cmd)
        self.assertTrue(target is None or isinstance(target, str))
        self.assertIsInstance(text, str)


class TestPersonality(unittest.TestCase):
    @given(st.one_of(st.integers(),
                     st.floats(allow_nan=True, allow_infinity=True),
                     st.text(max_size=10), st.none()))
    @SAFE_SETTINGS
    def test_clamp_always_in_range(self, v):
        n = pers.clamp_level(v)
        self.assertTrue(pers.MIN_LEVEL <= n <= pers.MAX_LEVEL)

    @given(st.integers(-100, 100))
    @SAFE_SETTINGS
    def test_directive_mentions_clamped_level(self, lvl):
        d = pers.get_sarcasm_directive(lvl)
        self.assertIn("/10", d)


class TestHudUptime(unittest.TestCase):
    @given(st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False)))
    @SAFE_SETTINGS
    def test_fmt_uptime_no_raise(self, s):
        self.assertIsInstance(hud._fmt_uptime(s), str)


class TestVoiceTone(unittest.TestCase):
    @given(TEXT)
    @SAFE_SETTINGS
    def test_detect_tone_valid(self, t):
        self.assertIn(vt.detect_tone(t), vt.TONES)

    @given(TEXT, st.one_of(st.none(), TEXT))
    @SAFE_SETTINGS
    def test_resolve_tone_valid(self, text, tone):
        self.assertIn(vt.resolve_tone(text, tone), vt.TONES)


class TestMarkIIPaths(unittest.TestCase):
    @given(TEXT, st.lists(st.text(max_size=15), max_size=5))
    @SAFE_SETTINGS
    def test_allowed_never_permits_traversal(self, target, dirs):
        res = m2.is_path_allowed(target, dirs)
        self.assertIsInstance(res, bool)
        if res:
            norm = target.replace("\\", "/").lstrip("./")
            self.assertNotIn("..", norm.split("/"))

    @given(TEXT)
    @SAFE_SETTINGS
    def test_slug_charset(self, s):
        out = m2._slug(s)
        self.assertRegex(out, r"^[a-z0-9-]*$")


class TestDronesFormat(unittest.TestCase):
    @given(st.lists(st.fixed_dictionaries({
        "short": st.text(min_size=1, max_size=4),
        "name": st.text(max_size=20),
        "status": st.sampled_from(["running", "completed", "failed"]),
    }), max_size=30))
    @SAFE_SETTINGS
    def test_format_drones_no_raise(self, ds):
        out = drones.format_drones(ds)
        self.assertIsInstance(out, str)
        self.assertTrue(out)


if __name__ == "__main__":
    unittest.main()
