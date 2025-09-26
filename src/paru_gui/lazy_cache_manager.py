import threading
import time
import weakref
from typing import Any, Dict, Optional, Callable, TypeVar, Generic
from concurrent.futures import ThreadPoolExecutor, Future
from functools import wraps
import asyncio

T = TypeVar('T')

class CacheEntry(Generic[T]):
    def __init__(self, value: T, ttl: float):
        self.value = value
        self.timestamp = time.time()
        self.ttl = ttl
        self.access_count = 0
        self.last_access = time.time()

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl

    def access(self) -> T:
        self.access_count += 1
        self.last_access = time.time()
        return self.value

class LazyCacheManager:
    def __init__(self, max_workers: int = 5, cache_size: int = 1000, default_ttl: float = 3600):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cache: Dict[str, CacheEntry] = {}
        self.futures: Dict[str, Future] = {}
        self.cache_size = cache_size
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
        self.weak_refs: Dict[str, weakref.ref] = {}

    def get(self, key: str, factory: Optional[Callable[[], T]] = None, ttl: Optional[float] = None) -> Optional[T]:
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if not entry.is_expired():
                    return entry.access()
                else:
                    del self.cache[key]

            if key in self.futures:
                future = self.futures[key]
                if not future.done():
                    try:
                        result = future.result(timeout=30.0)
                        self._store(key, result, ttl or self.default_ttl)
                        return result
                    except Exception:
                        del self.futures[key]
                        return None

            if factory:
                return self._lazy_load(key, factory, ttl or self.default_ttl)

            return None

    def _lazy_load(self, key: str, factory: Callable[[], T], ttl: float) -> Optional[T]:
        future = self.executor.submit(factory)
        self.futures[key] = future

        try:
            result = future.result(timeout=30.0)
            self._store(key, result, ttl)
            if key in self.futures:
                del self.futures[key]
            return result
        except Exception as e:
            if key in self.futures:
                del self.futures[key]
            return None

    def _store(self, key: str, value: T, ttl: float):
        with self.lock:
            if len(self.cache) >= self.cache_size:
                self._evict_lru()
            
            self.cache[key] = CacheEntry(value, ttl)

    def _evict_lru(self):
        if not self.cache:
            return
            
        lru_key = min(self.cache.keys(),
                     key=lambda k: self.cache[k].last_access)
        del self.cache[lru_key]

    def set(self, key: str, value: T, ttl: Optional[float] = None):
        self._store(key, value, ttl or self.default_ttl)

    def delete(self, key: str):
        with self.lock:
            if key in self.cache:
                del self.cache[key]
            if key in self.futures:
                future = self.futures[key]
                future.cancel()
                del self.futures[key]
            if key in self.weak_refs:
                del self.weak_refs[key]

    def clear(self):
        with self.lock:
            self.cache.clear()
            for future in self.futures.values():
                future.cancel()
            self.futures.clear()
            self.weak_refs.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total_entries = len(self.cache)
            expired_entries = sum(1 for entry in self.cache.values() if entry.is_expired())
            pending_futures = len(self.futures)

            return {
                'total_entries': total_entries,
                'expired_entries': expired_entries,
                'pending_futures': pending_futures,
                'cache_utilization': total_entries / self.cache_size if self.cache_size > 0 else 0
            }

    def cleanup_expired(self):
        with self.lock:
            expired_keys = [key for key, entry in self.cache.items() if entry.is_expired()]
            for key in expired_keys:
                del self.cache[key]

    def register_weak_ref(self, key: str, obj: Any):
        def cleanup_callback(ref):
            with self.lock:
                if key in self.weak_refs and self.weak_refs[key] is ref:
                    del self.weak_refs[key]
                    self.delete(key)

        self.weak_refs[key] = weakref.ref(obj, cleanup_callback)

    def cached_property(self, ttl: Optional[float] = None):
        def decorator(func):
            @wraps(func)
            def wrapper(instance):
                key = f"{instance.__class__.__name__}_{id(instance)}_{func.__name__}"
                result = self.get(key, lambda: func(instance), ttl)
                if result is None:
                    result = func(instance)
                    self.set(key, result, ttl)
                return result
            return wrapper
        return decorator

    async def async_get(self, key: str, factory: Optional[Callable[[], T]] = None, ttl: Optional[float] = None) -> Optional[T]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.get, key, factory, ttl)

    def __del__(self):
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
