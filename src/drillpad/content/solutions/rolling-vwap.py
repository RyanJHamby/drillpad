# ruff: noqa
from collections import deque


class RollingVWAP:
    def __init__(self, window):
        if not isinstance(window, int) or window <= 0:
            raise ValueError("window must be a positive int")
        self.window = window
        self.q = deque()
        self.pq = 0
        self.vol = 0
        self.last = None

    def _evict(self, ts):
        cutoff = ts - self.window
        while self.q and self.q[0][0] <= cutoff:
            t, p, v = self.q.popleft()
            self.pq -= p * v
            self.vol -= v

    def _check_ts(self, ts):
        if self.last is not None and ts < self.last:
            raise ValueError("timestamps must be non-decreasing")
        self.last = ts

    def feed(self, ts, price, qty):
        if price <= 0 or qty <= 0:
            raise ValueError("price and qty must be positive")
        self._check_ts(ts)
        self._evict(ts)
        self.q.append((ts, price, qty))
        self.pq += price * qty
        self.vol += qty
        return self.pq / self.vol

    def query(self, ts):
        self._check_ts(ts)
        self._evict(ts)
        return self.pq / self.vol if self.vol else None
