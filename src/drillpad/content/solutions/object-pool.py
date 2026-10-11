# ruff: noqa
import threading
from contextlib import contextmanager


class ObjectPool:
    def __init__(self, factory, reset=None, max_idle=8):
        self.factory = factory
        self.reset = reset
        self.max_idle = max_idle
        self._lock = threading.Lock()
        self._idle = []
        self._in_use = {}
        self._created = 0
        self._reused = 0

    def acquire(self):
        with self._lock:
            if self._idle:
                obj = self._idle.pop()
                self._reused += 1
                self._in_use[id(obj)] = obj
                return obj
        obj = self.factory()     # build outside the lock
        with self._lock:
            self._created += 1
            self._in_use[id(obj)] = obj
        return obj

    def release(self, obj):
        with self._lock:
            if self._in_use.pop(id(obj), None) is None:
                raise ValueError("object not checked out")
        if self.reset:
            self.reset(obj)
        with self._lock:
            if len(self._idle) < self.max_idle:
                self._idle.append(obj)

    @contextmanager
    def lease(self):
        obj = self.acquire()
        try:
            yield obj
        finally:
            self.release(obj)

    def stats(self):
        with self._lock:
            return {"created": self._created, "reused": self._reused,
                    "idle": len(self._idle), "in_use": len(self._in_use)}
