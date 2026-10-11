# ruff: noqa
import bisect
import math
from collections import deque


def percentile(samples, p):
    if not samples or not (0 < p <= 100):
        raise ValueError("bad input")
    s = sorted(samples)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)]


def hedged_request(latencies, hedge_delay, max_hedges=1):
    inf = float("inf")
    best_t, best_i = inf, None
    launched = 0
    for k, lat in enumerate(latencies[: max_hedges + 1]):
        start = k * hedge_delay
        if k > 0 and start >= best_t:
            break
        launched += 1
        t = start + lat
        if t < best_t:
            best_t, best_i = t, k
    return best_i, best_t, launched


class LatencyTracker:
    def __init__(self, window):
        if window < 1:
            raise ValueError("window")
        self.window = window
        self.fifo = deque()
        self.sorted = []

    def record(self, x):
        self.fifo.append(x)
        bisect.insort(self.sorted, x)
        if len(self.fifo) > self.window:
            old = self.fifo.popleft()
            del self.sorted[bisect.bisect_left(self.sorted, old)]

    def hedge_delay(self, p):
        if not self.sorted:
            return None
        if not (0 < p <= 100):
            raise ValueError("bad percentile")
        return self.sorted[max(0, math.ceil(p / 100 * len(self.sorted)) - 1)]
