# ruff: noqa
from collections import defaultdict, Counter
class DetectSquares:
    def __init__(self):
        self.cnt = Counter()
        self.cols = defaultdict(Counter)

    def add(self, point):
        x, y = point
        self.cnt[(x, y)] += 1
        self.cols[x][y] += 1

    def count(self, point):
        x, y = point
        total = 0
        for y2, c in self.cols.get(x, {}).items():
            d = y2 - y
            if d == 0:
                continue
            for x2 in (x + d, x - d):
                total += c * self.cnt.get((x2, y), 0) * self.cnt.get((x2, y2), 0)
        return total
