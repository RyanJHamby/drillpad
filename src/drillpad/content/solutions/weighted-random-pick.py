# ruff: noqa
import random
from bisect import bisect_right
from itertools import accumulate


class WeightedPicker:
    def __init__(self, weights, rng=None):
        if not weights:
            raise ValueError("weights must be non-empty")
        for w in weights:
            if not isinstance(w, int) or w < 0:
                raise ValueError("weights must be non-negative ints")
        self.prefix = list(accumulate(weights))
        if self.prefix[-1] == 0:
            raise ValueError("total weight must be positive")
        self.rng = rng or random.Random()

    def pick(self):
        r = self.rng.randrange(self.prefix[-1])
        return bisect_right(self.prefix, r)
