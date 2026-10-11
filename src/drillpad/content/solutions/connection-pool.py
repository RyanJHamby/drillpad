# ruff: noqa
import threading
import time
from contextlib import contextmanager


class ConnectionPool:
    def __init__(self, factory, max_size, validate=None, close=None):
        self.factory = factory
        self.max_size = max_size
        self.validate = validate
        self.close = close
        self._cond = threading.Condition(threading.Lock())
        self._idle = []
        self._in_use = {}   # id(conn) -> conn
        self._live = 0
        self._created = 0
        self._closed = False

    def _discard(self, conn):
        if self.close:
            self.close(conn)

    def acquire(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while True:
                if self._closed:
                    raise RuntimeError("pool closed")
                while self._idle:
                    conn = self._idle.pop()
                    if self.validate is None or self.validate(conn):
                        self._in_use[id(conn)] = conn
                        return conn
                    self._live -= 1
                    self._discard(conn)
                if self._live < self.max_size:
                    self._live += 1
                    try:
                        conn = self.factory()
                    except BaseException:
                        self._live -= 1
                        self._cond.notify()
                        raise
                    self._created += 1
                    self._in_use[id(conn)] = conn
                    return conn
                if deadline is None:
                    self._cond.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("no connection available")
                    self._cond.wait(remaining)

    def release(self, conn):
        with self._cond:
            if self._in_use.pop(id(conn), None) is None:
                raise ValueError("connection not checked out")
            if self._closed:
                self._live -= 1
                self._discard(conn)
                return
            self._idle.append(conn)
            self._cond.notify()

    @contextmanager
    def connection(self):
        conn = self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)

    def close_all(self):
        with self._cond:
            self._closed = True
            idle, self._idle = self._idle, []
            self._live -= len(idle)
            for c in idle:
                self._discard(c)
            self._cond.notify_all()

    def stats(self):
        with self._cond:
            return {"created": self._created, "idle": len(self._idle), "in_use": len(self._in_use)}
