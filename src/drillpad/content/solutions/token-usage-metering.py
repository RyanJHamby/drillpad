# ruff: noqa
from collections import deque


class UsageMeter:
    def __init__(self, window, limit):
        if window <= 0 or limit < 0:
            raise ValueError("bad config")
        self.window, self.limit = window, limit
        self.events = {}          # key -> deque of (ts, tokens)
        self.sums = {}
        self.last = None

    def _advance(self, now):
        if self.last is not None and now < self.last:
            raise ValueError("time went backwards")
        self.last = now

    def _expire(self, key, now):
        dq = self.events.get(key)
        if dq is None:
            return None
        s = self.sums[key]
        while dq and dq[0][0] <= now - self.window:
            s -= dq.popleft()[1]
        self.sums[key] = s
        return dq

    def record(self, key, tokens, now):
        if tokens < 0:
            raise ValueError("negative tokens")
        self._advance(now)
        dq = self._expire(key, now)
        if dq is None:
            dq = self.events[key] = deque()
            self.sums[key] = 0
        if tokens:
            dq.append((now, tokens))
            self.sums[key] += tokens

    def usage(self, key, now):
        self._advance(now)
        if self._expire(key, now) is None:
            return 0
        return self.sums[key]

    def allow(self, key, tokens, now):
        if tokens < 0:
            raise ValueError("negative tokens")
        if self.usage(key, now) + tokens > self.limit:
            return False
        self.record(key, tokens, now)
        return True

    def retry_after(self, key, tokens, now):
        if tokens < 0:
            raise ValueError("negative tokens")
        if tokens > self.limit:
            return None
        used = self.usage(key, now)
        need = used + tokens - self.limit
        if need <= 0:
            return 0
        freed = 0
        for ts, n in self.events[key]:
            freed += n
            if freed >= need:
                return ts + self.window - now
