# ruff: noqa
from collections import OrderedDict


class _LRU:
    def __init__(self, capacity):
        self.capacity = capacity
        self.d = OrderedDict()

    def get(self, key):
        if key in self.d:
            self.d.move_to_end(key)
            return self.d[key]
        return None

    def put(self, key, value):
        if self.capacity <= 0:
            return
        self.d[key] = value
        self.d.move_to_end(key)
        while len(self.d) > self.capacity:
            self.d.popitem(last=False)

    def pop(self, key):
        self.d.pop(key, None)


class TwoLevelCache:
    def __init__(self, l1_capacity, l2_capacity, loader):
        self.l1 = _LRU(l1_capacity)
        self.l2 = _LRU(l2_capacity)
        self.loader = loader
        self._stats = {"l1_hits": 0, "l2_hits": 0, "misses": 0}

    def get(self, key):
        v = self.l1.get(key)
        if v is not None:
            self._stats["l1_hits"] += 1
            self.l2.get(key)  # keep the hot key warm in L2 too
            return v
        v = self.l2.get(key)
        if v is not None:
            self._stats["l2_hits"] += 1
            self.l1.put(key, v)
            return v
        self._stats["misses"] += 1
        v = self.loader(key)
        if v is None:
            return None
        self.l2.put(key, v)
        self.l1.put(key, v)
        return v

    def put(self, key, value):
        self.l2.put(key, value)
        self.l1.put(key, value)

    def invalidate(self, key):
        self.l1.pop(key)
        self.l2.pop(key)

    def stats(self):
        return dict(self._stats)
