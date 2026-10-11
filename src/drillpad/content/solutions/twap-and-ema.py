# ruff: noqa
from bisect import bisect_right


class Twap:
    def __init__(self, updates):
        if not updates:
            raise ValueError("need at least one update")
        self.ts = [u[0] for u in updates]
        self.px = [u[1] for u in updates]
        for i in range(1, len(self.ts)):
            if self.ts[i] <= self.ts[i - 1]:
                raise ValueError("timestamps must be strictly increasing")
        self.cum = [0]  # integral of price from ts[0] up to ts[i]
        for i in range(1, len(self.ts)):
            self.cum.append(self.cum[-1] + self.px[i - 1] * (self.ts[i] - self.ts[i - 1]))

    def _integral(self, t):
        i = bisect_right(self.ts, t) - 1
        return self.cum[i] + self.px[i] * (t - self.ts[i])

    def query(self, start, end):
        if end < start or start < self.ts[0]:
            raise ValueError("bad interval")
        if end == start:
            return float(self.px[bisect_right(self.ts, start) - 1])
        return (self._integral(end) - self._integral(start)) / (end - start)


def ema(values, span):
    if not isinstance(span, int) or span < 1:
        raise ValueError("span must be >= 1")
    alpha = 2.0 / (span + 1)
    out = []
    for i, x in enumerate(values):
        out.append(float(x) if i == 0 else alpha * x + (1 - alpha) * out[-1])
    return out
