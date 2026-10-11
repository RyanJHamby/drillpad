# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
import threading
from collections import deque


class BoundedQueue:
    def __init__(self, capacity):
        self._capacity = capacity
        self._buf = deque()
        self._lock = threading.Lock()
        self._not_full = threading.Condition(self._lock)
        self._not_empty = threading.Condition(self._lock)

    def put(self, item):
        with self._not_full:
            while len(self._buf) >= self._capacity:   # loop, not `if` — re-check after wakeup
                self._not_full.wait()
            self._buf.append(item)
            self._not_empty.notify()   # wake one waiting consumer

    def get(self):
        with self._not_empty:
            while not self._buf:
                self._not_empty.wait()
            item = self._buf.popleft()
            self._not_full.notify()    # wake one waiting producer
            return item
