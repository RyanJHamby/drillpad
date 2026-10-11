# ruff: noqa
from collections import defaultdict, deque


class Throttle:
    def __init__(self, limit, window):
        if not isinstance(limit, int) or not isinstance(window, int) or limit < 1 or window < 1:
            raise ValueError("limit and window must be positive ints")
        self.limit = limit
        self.window = window
        self.hits = defaultdict(deque)
        self.last = {}

    def _evict(self, q, ts):
        while q and q[0] <= ts - self.window:
            q.popleft()

    def allow(self, venue, ts):
        if venue in self.last and ts < self.last[venue]:
            raise ValueError("timestamps must be non-decreasing per venue")
        self.last[venue] = ts
        q = self.hits[venue]
        self._evict(q, ts)
        if len(q) < self.limit:
            q.append(ts)
            return True
        return False

    def retry_after(self, venue, ts):
        q = self.hits[venue]
        if len(q) < self.limit:
            return 0
        gate = q[-self.limit]   # the accepted message that must expire to make room
        if gate <= ts - self.window:
            return 0
        return gate + self.window - ts
