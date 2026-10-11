# ruff: noqa
import random


def reservoir_sample(stream, k, rng=None):
    if not isinstance(k, int) or k < 0:
        raise ValueError("k must be a non-negative int")
    rng = rng or random.Random()
    res = []
    if k == 0:
        return res
    for i, item in enumerate(stream):
        if i < k:
            res.append(item)
        else:
            j = rng.randrange(i + 1)
            if j < k:
                res[j] = item
    return res
