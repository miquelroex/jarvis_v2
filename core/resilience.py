"""
core/resilience.py — Capa de resiliencia universal para tools y funciones.

Un decorador `@resilient` que dota a cualquier función de:
  - REINTENTOS con backoff exponencial ante fallos transitorios.
  - CACHÉ en memoria con TTL (evita repetir llamadas caras/idénticas).
  - FALLBACK elegante (valor o callable) en vez de propagar la excepción.

Todo en memoria, sin dependencias. Pensado para envolver tools de red (búsquedas,
clima, APIs) y hacerlas indestructibles y rápidas. Pura y testeable.
"""
import time
import logging
import functools
import threading

logger = logging.getLogger(__name__)

_MISS = object()    # centinela: clave ausente en la caché
_UNSET = object()   # centinela: sin fallback configurado


class TTLCache:
    """Caché en memoria con expiración por entrada (thread-safe)."""

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key, now=None):
        now = time.time() if now is None else now
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return _MISS
            value, expiry = entry
            if expiry is not None and now >= expiry:
                del self._data[key]
                return _MISS
            return value

    def set(self, key, value, ttl, now=None):
        now = time.time() if now is None else now
        expiry = (now + ttl) if (ttl and ttl > 0) else None
        with self._lock:
            self._data[key] = (value, expiry)

    def clear(self):
        with self._lock:
            self._data.clear()

    def __len__(self):
        with self._lock:
            return len(self._data)


def _make_key(args, kwargs):
    """Clave de caché estable a partir de los argumentos (best-effort)."""
    try:
        return (args, tuple(sorted(kwargs.items())))
    except Exception:
        return (str(args), str(sorted(kwargs.items())))


def resilient(retries: int = 2, backoff: float = 0.2, cache_ttl: float = 0,
              fallback=_UNSET, exceptions=(Exception,), max_backoff: float = 5.0):
    """Decorador de resiliencia.

    retries: reintentos adicionales tras el primer intento (total = retries+1).
    backoff: segundos base; espera backoff * 2**(intento-1), acotado a max_backoff.
    cache_ttl: si > 0, cachea el resultado por args durante ese tiempo.
    fallback: valor o callable a devolver si se agotan los reintentos. Sin él, relanza.
    exceptions: tipos que disparan reintento; otros se propagan de inmediato.
    """
    def decorator(fn):
        cache = TTLCache()

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = None
            if cache_ttl and cache_ttl > 0:
                key = _make_key(args, kwargs)
                cached = cache.get(key)
                if cached is not _MISS:
                    return cached

            attempt = 0
            last_exc = None
            while attempt <= retries:
                try:
                    result = fn(*args, **kwargs)
                    if key is not None:
                        cache.set(key, result, cache_ttl)
                    return result
                except exceptions as e:
                    last_exc = e
                    attempt += 1
                    if attempt > retries:
                        break
                    delay = min(max_backoff, backoff * (2 ** (attempt - 1)))
                    logger.warning(f"[Resilience] {fn.__name__} falló (intento {attempt}/{retries}): {e}. "
                                   f"Reintentando en {delay:.2f}s.")
                    time.sleep(delay)

            if fallback is not _UNSET:
                logger.warning(f"[Resilience] {fn.__name__} agotó reintentos; usando fallback.")
                return fallback() if callable(fallback) else fallback
            raise last_exc

        wrapper._resilient_cache = cache  # para tests / invalidación manual
        return wrapper

    return decorator
