# ruff: noqa
class SegmentTree:
    def __init__(self, values):
        self.n = len(values)
        self.mn = [0] * (2 * self.n)
        self.mx = [0] * (2 * self.n)
        for i, v in enumerate(values):
            self.mn[self.n + i] = v
            self.mx[self.n + i] = v
        for i in range(self.n - 1, 0, -1):
            self.mn[i] = min(self.mn[2 * i], self.mn[2 * i + 1])
            self.mx[i] = max(self.mx[2 * i], self.mx[2 * i + 1])

    def update(self, i, v):
        if not isinstance(i, int) or i < 0 or i >= self.n:
            raise IndexError("index out of range")
        i += self.n
        self.mn[i] = self.mx[i] = v
        i >>= 1
        while i >= 1:
            self.mn[i] = min(self.mn[2 * i], self.mn[2 * i + 1])
            self.mx[i] = max(self.mx[2 * i], self.mx[2 * i + 1])
            i >>= 1

    def _query(self, l, r, arr, fn, init):
        if not isinstance(l, int) or not isinstance(r, int) or l < 0 or r >= self.n:
            raise IndexError("index out of range")
        if l > r:
            raise ValueError("l must be <= r")
        res = init
        l += self.n
        r += self.n + 1
        while l < r:
            if l & 1:
                res = fn(res, arr[l])
                l += 1
            if r & 1:
                r -= 1
                res = fn(res, arr[r])
            l >>= 1
            r >>= 1
        return res

    def range_min(self, l, r):
        return self._query(l, r, self.mn, min, float("inf"))

    def range_max(self, l, r):
        return self._query(l, r, self.mx, max, float("-inf"))
