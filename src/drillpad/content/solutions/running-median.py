# ruff: noqa
import heapq


class RunningMedian:
    def __init__(self):
        self.lo = []  # max-heap (negated): lower half, len(lo) >= len(hi)
        self.hi = []  # min-heap: upper half

    def add(self, x):
        if not isinstance(x, int):
            raise ValueError("prices must be ints")
        if not self.lo or x <= -self.lo[0]:
            heapq.heappush(self.lo, -x)
        else:
            heapq.heappush(self.hi, x)
        if len(self.lo) > len(self.hi) + 1:
            heapq.heappush(self.hi, -heapq.heappop(self.lo))
        elif len(self.hi) > len(self.lo):
            heapq.heappush(self.lo, -heapq.heappop(self.hi))

    def median(self):
        if not self.lo:
            raise ValueError("empty")
        if len(self.lo) > len(self.hi):
            return float(-self.lo[0])
        return (-self.lo[0] + self.hi[0]) / 2

    def __len__(self):
        return len(self.lo) + len(self.hi)
