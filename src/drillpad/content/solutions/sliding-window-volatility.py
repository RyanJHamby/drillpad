# ruff: noqa
import math
from collections import deque


class RollingStd:
    def __init__(self, window):
        if not isinstance(window, int) or window < 2:
            raise ValueError("window must be an int >= 2")
        self.window = window
        self.q = deque()
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0

    def _push(self, x):
        self.n += 1
        d = x - self.mean
        self.mean += d / self.n
        self.m2 += d * (x - self.mean)

    def _pop(self, x):
        if self.n == 1:
            self.n, self.mean, self.m2 = 0, 0.0, 0.0
            return
        old_mean = self.mean
        self.n -= 1
        self.mean = (old_mean * (self.n + 1) - x) / self.n
        self.m2 -= (x - old_mean) * (x - self.mean)
        if self.m2 < 0:
            self.m2 = 0.0

    def std(self):
        if self.n < 2:
            return None
        return math.sqrt(self.m2 / (self.n - 1))

    def add(self, x):
        self.q.append(x)
        self._push(x)
        if len(self.q) > self.window:
            self._pop(self.q.popleft())
        return self.std()
