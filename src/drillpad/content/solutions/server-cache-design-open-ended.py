# ruff: noqa
import threading
from collections import OrderedDict


class _Flight:
    def __init__(self):
        self.event = threading.Event()
        self.found = False
        self.value = None
        self.error = None
        self.stale = False

    def result(self, key):
        if self.error is not None:
            raise self.error
        if not self.found:
            raise KeyError(key)
        return self.value


class Cache:
    def __init__(self, backend, capacity, ttl, clock):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._b = backend
        self._cap = capacity
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._entries = OrderedDict()  # key -> (found, value, stored_at)
        self._flights = {}
        self._hits = 0
        self._misses = 0

    def _install(self, key, found, value):
        self._entries[key] = (found, value, self._clock())
        self._entries.move_to_end(key)
        while len(self._entries) > self._cap:
            self._entries.popitem(last=False)

    def _detach(self, key):
        fl = self._flights.pop(key, None)
        if fl is not None:
            fl.stale = True

    def get(self, key):
        with self._lock:
            e = self._entries.get(key)
            if e is not None:
                found, value, at = e
                if self._clock() - at < self._ttl:
                    self._entries.move_to_end(key)
                    self._hits += 1
                    if found:
                        return value
                    raise KeyError(key)
                del self._entries[key]
            fl = self._flights.get(key)
            if fl is not None:
                self._hits += 1
                leader = False
            else:
                fl = _Flight()
                self._flights[key] = fl
                self._misses += 1
                leader = True
        if not leader:
            fl.event.wait()
            return fl.result(key)
        try:
            fl.value = self._b.fetch(key)
            fl.found = True
        except KeyError:
            fl.found = False
        except BaseException as exc:
            fl.error = exc
        with self._lock:
            if self._flights.get(key) is fl:
                del self._flights[key]
            if not fl.stale and fl.error is None:
                self._install(key, fl.found, fl.value)
        fl.event.set()
        return fl.result(key)

    def write(self, key, value):
        self._b.store(key, value)
        with self._lock:
            self._detach(key)
            self._install(key, True, value)

    def invalidate(self, key):
        with self._lock:
            self._detach(key)
            self._entries.pop(key, None)

    def stats(self):
        with self._lock:
            return {"hits": self._hits, "misses": self._misses}
