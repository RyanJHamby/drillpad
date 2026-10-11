# ruff: noqa
from collections import deque


class OrderIds:
    def __init__(self, prefix, ttl):
        if not prefix or not isinstance(ttl, int) or ttl <= 0:
            raise ValueError("bad prefix or ttl")
        self.prefix = prefix
        self.ttl = ttl
        self.n = 0
        self.seen = {}        # msg_id -> first-accepted ts
        self.order = deque()  # (ts, msg_id) in acceptance order
        self.last = None

    def next_id(self):
        self.n += 1
        return f"{self.prefix}-{self.n:06d}"

    def _purge(self, ts):
        while self.order and self.order[0][0] + self.ttl <= ts:
            _, mid = self.order.popleft()
            del self.seen[mid]

    def accept(self, msg_id, ts):
        if self.last is not None and ts < self.last:
            raise ValueError("timestamps must be non-decreasing")
        self.last = ts
        self._purge(ts)
        if msg_id in self.seen:
            return False
        self.seen[msg_id] = ts
        self.order.append((ts, msg_id))
        return True

    def size(self):
        return len(self.seen)
