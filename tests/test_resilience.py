"""Tests de la capa de resiliencia (core/resilience.py)."""
import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.resilience as res


class TestTTLCache(unittest.TestCase):
    def test_set_get(self):
        c = res.TTLCache()
        c.set("k", 42, ttl=0)
        self.assertEqual(c.get("k"), 42)

    def test_missing_is_sentinel(self):
        c = res.TTLCache()
        self.assertIs(c.get("nope"), res._MISS)

    def test_ttl_zero_never_expires(self):
        c = res.TTLCache()
        c.set("k", 1, ttl=0, now=1000)
        self.assertEqual(c.get("k", now=1_000_000), 1)

    def test_expiry(self):
        c = res.TTLCache()
        c.set("k", 1, ttl=10, now=1000)
        self.assertEqual(c.get("k", now=1005), 1)        # dentro de TTL
        self.assertIs(c.get("k", now=1011), res._MISS)   # expirado
        self.assertEqual(len(c), 0)                       # se purga al leer


class TestRetries(unittest.TestCase):
    def test_succeeds_first_try(self):
        calls = []

        @res.resilient(retries=3, backoff=0)
        def f():
            calls.append(1)
            return "ok"

        self.assertEqual(f(), "ok")
        self.assertEqual(len(calls), 1)

    def test_retries_then_succeeds(self):
        state = {"n": 0}

        @res.resilient(retries=3, backoff=0)
        def f():
            state["n"] += 1
            if state["n"] < 3:
                raise ValueError("transitorio")
            return "recuperado"

        self.assertEqual(f(), "recuperado")
        self.assertEqual(state["n"], 3)

    def test_exhausts_and_raises_without_fallback(self):
        @res.resilient(retries=2, backoff=0)
        def f():
            raise RuntimeError("siempre falla")

        with self.assertRaises(RuntimeError):
            f()

    def test_total_attempts_is_retries_plus_one(self):
        calls = []

        @res.resilient(retries=2, backoff=0)
        def f():
            calls.append(1)
            raise ValueError("x")

        with self.assertRaises(ValueError):
            f()
        self.assertEqual(len(calls), 3)  # 1 inicial + 2 reintentos

    def test_only_listed_exceptions_retried(self):
        calls = []

        @res.resilient(retries=3, backoff=0, exceptions=(ValueError,))
        def f():
            calls.append(1)
            raise KeyError("no reintentable")

        with self.assertRaises(KeyError):
            f()
        self.assertEqual(len(calls), 1)  # no se reintenta


class TestFallback(unittest.TestCase):
    def test_value_fallback(self):
        @res.resilient(retries=1, backoff=0, fallback="por defecto")
        def f():
            raise IOError("red caída")

        self.assertEqual(f(), "por defecto")

    def test_callable_fallback(self):
        @res.resilient(retries=0, backoff=0, fallback=lambda: [1, 2, 3])
        def f():
            raise IOError("nope")

        self.assertEqual(f(), [1, 2, 3])

    def test_none_fallback_is_returned(self):
        @res.resilient(retries=0, backoff=0, fallback=None)
        def f():
            raise IOError("nope")

        self.assertIsNone(f())


class TestCache(unittest.TestCase):
    def test_caches_within_ttl(self):
        calls = []

        @res.resilient(cache_ttl=100, backoff=0)
        def f(x):
            calls.append(x)
            return x * 2

        self.assertEqual(f(5), 10)
        self.assertEqual(f(5), 10)        # segunda vez: de caché
        self.assertEqual(len(calls), 1)   # la función solo se ejecutó una vez

    def test_different_args_not_shared(self):
        calls = []

        @res.resilient(cache_ttl=100, backoff=0)
        def f(x):
            calls.append(x)
            return x

        f(1); f(2); f(1)
        self.assertEqual(calls, [1, 2])   # f(1) cacheado, f(2) nuevo

    def test_cache_expires(self):
        calls = []

        @res.resilient(cache_ttl=10, backoff=0)
        def f():
            calls.append(1)
            return "v"

        with patch("time.time", side_effect=[1000, 1000, 1005, 1011, 1011, 1011]):
            f()            # set @1000
            f()            # @1005 -> caché
            f()            # @1011 -> expirado, recalcula
        self.assertEqual(len(calls), 2)

    def test_no_cache_when_ttl_zero(self):
        calls = []

        @res.resilient(cache_ttl=0, backoff=0)
        def f():
            calls.append(1)
            return "v"

        f(); f()
        self.assertEqual(len(calls), 2)


class TestBackoff(unittest.TestCase):
    def test_backoff_is_exponential_and_capped(self):
        sleeps = []

        @res.resilient(retries=4, backoff=1.0, max_backoff=3.0)
        def f():
            raise ValueError("x")

        with patch("time.sleep", side_effect=lambda s: sleeps.append(s)):
            with self.assertRaises(ValueError):
                f()
        # 1, 2, 4->cap 3, 8->cap 3
        self.assertEqual(sleeps, [1.0, 2.0, 3.0, 3.0])


if __name__ == "__main__":
    unittest.main()
