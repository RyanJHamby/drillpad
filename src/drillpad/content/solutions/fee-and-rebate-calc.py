# ruff: noqa
from bisect import bisect_right
from collections import defaultdict


def fees(fills, schedule):
    vol = defaultdict(int)
    by_venue = defaultdict(int)
    total = 0
    prepared = {}
    for venue, sides in schedule.items():
        for liq, tiers in sides.items():
            tiers = sorted(tiers)
            prepared[(venue, liq)] = ([t[0] for t in tiers], [t[1] for t in tiers])
    for venue, liq, price, qty in fills:
        key = (venue, liq)
        if key not in prepared:
            raise ValueError("unknown venue or liquidity flag")
        if not isinstance(qty, int) or qty <= 0:
            raise ValueError("qty must be a positive int")
        mins, rates = prepared[key]
        i = bisect_right(mins, vol[key]) - 1
        if i < 0:
            raise ValueError("no tier covers volume")
        fee = qty * rates[i]
        vol[key] += qty
        by_venue[venue] += fee
        total += fee
    return {"total": total, "by_venue": dict(by_venue)}
