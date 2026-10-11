# ruff: noqa
def max_profit(prices):
    best = 0
    lo = None
    for p in prices:
        if lo is None or p < lo:
            lo = p
        elif p - lo > best:
            best = p - lo
    return best
