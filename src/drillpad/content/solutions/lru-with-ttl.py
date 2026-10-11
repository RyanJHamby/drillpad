# ruff: noqa
import heapq
import itertools
import time
from collections import OrderedDict


class LRUTTLCache:
    def __init__(self, capacity, clock=time.monotonic):
        self.capacity = capacity
        self.clock = clock
        self.data = OrderedDict()  # key -> (value, expiry or None, seq); order = recency
        self.heap = []             # (expiry, seq, key) with lazy deletion of stale entries
        self.seq = itertools.count()

    def _purge(self, now):
        while self.heap and self.heap[0][0] <= now:
            expiry, seq, key = heapq.heappop(self.heap)
            entry = self.data.get(key)
            if entry is not None and entry[2] == seq:  # not overwritten since
                del self.data[key]

    def put(self, key, value, ttl=None):
        if self.capacity <= 0:
            return
        now = self.clock()
        seq = next(self.seq)
        expiry = None if ttl is None else now + ttl
        self.data[key] = (value, expiry, seq)
        self.data.move_to_end(key)
        if expiry is not None:
            heapq.heappush(self.heap, (expiry, seq, key))
        if len(self.data) > self.capacity:
            self._purge(now)
        while len(self.data) > self.capacity:
            self.data.popitem(last=False)

    def get(self, key):
        entry = self.data.get(key)
        if entry is None:
            return None
        value, expiry, _ = entry
        if expiry is not None and self.clock() >= expiry:
            del self.data[key]
            return None
        self.data.move_to_end(key)
        return value

    def __len__(self):
        self._purge(self.clock())
        return len(self.data)
