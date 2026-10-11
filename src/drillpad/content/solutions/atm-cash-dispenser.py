# ruff: noqa
from math import gcd
from functools import lru_cache


class ATM:
    def __init__(self, inventory):
        self.inv = dict(inventory)

    def inventory(self):
        return dict(self.inv)

    def total_cash(self):
        return sum(d * c for d, c in self.inv.items())

    def refill(self, denomination, count):
        if type(denomination) is not int or type(count) is not int or denomination <= 0 or count <= 0:
            raise ValueError("bad refill")
        self.inv[denomination] = self.inv.get(denomination, 0) + count

    def dispense(self, amount):
        if type(amount) is not int or amount <= 0:
            raise ValueError("amount must be a positive int")
        denoms = sorted((d for d, c in self.inv.items() if c > 0), reverse=True)
        if not denoms:
            return None
        g = 0
        for d in denoms:
            g = gcd(g, d)
        if amount % g:
            return None
        units = [d // g for d in denoms]
        counts = [self.inv[d] for d in denoms]
        n = len(denoms)

        @lru_cache(maxsize=None)
        def f(i, r):
            if r == 0:
                return (0, ())
            if i == n:
                return None
            best = None
            top = min(counts[i], r // units[i])
            for k in range(top, -1, -1):
                sub = f(i + 1, r - k * units[i])
                if sub is None:
                    continue
                cand = (sub[0] + k, (k,) + sub[1])
                if best is None or cand[0] < best[0]:
                    best = cand
            return best

        res = f(0, amount // g)
        if res is None:
            return None
        out = {}
        for d, k in zip(denoms, res[1] + (0,) * (n - len(res[1]))):
            if k:
                out[d] = k
                self.inv[d] -= k
        return out
