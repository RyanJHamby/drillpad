# ruff: noqa
from collections import deque


class HitCounter:
    WINDOW = 300

    def __init__(self):
        self.q = deque()   # [timestamp, count] buckets, one per distinct second
        self.total = 0

    def _evict(self, timestamp):
        while self.q and self.q[0][0] <= timestamp - self.WINDOW:
            self.total -= self.q.popleft()[1]

    def hit(self, timestamp):
        if self.q and self.q[-1][0] == timestamp:
            self.q[-1][1] += 1
        else:
            self.q.append([timestamp, 1])
        self.total += 1

    def get_hits(self, timestamp):
        self._evict(timestamp)
        return self.total
