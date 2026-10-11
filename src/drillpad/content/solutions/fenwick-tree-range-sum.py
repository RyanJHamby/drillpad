# ruff: noqa
class FenwickTree:
    def __init__(self, values):
        self.n = len(values)
        self.t = [0] * (self.n + 1)
        for i, v in enumerate(values, 1):
            self.t[i] += v
            j = i + (i & -i)
            if j <= self.n:
                self.t[j] += self.t[i]

    def _check(self, i):
        if not isinstance(i, int) or i < 0 or i >= self.n:
            raise IndexError("index out of range")

    def add(self, i, delta):
        self._check(i)
        i += 1
        while i <= self.n:
            self.t[i] += delta
            i += i & -i

    def prefix_sum(self, count):
        if not isinstance(count, int) or count < 0 or count > self.n:
            raise IndexError("count out of range")
        s = 0
        while count > 0:
            s += self.t[count]
            count -= count & -count
        return s

    def range_sum(self, l, r):
        self._check(l)
        self._check(r)
        if l > r:
            raise ValueError("l must be <= r")
        return self.prefix_sum(r + 1) - self.prefix_sum(l)
