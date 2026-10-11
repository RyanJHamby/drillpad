# ruff: noqa
from fractions import Fraction


def _build(rates):
    explicit = {}
    for a, b, r in rates:
        if isinstance(r, float):
            raise ValueError("float rate")
        f = Fraction(r)
        if f <= 0:
            raise ValueError("rate must be positive")
        explicit[(a, b)] = f
    edges = {}
    for (a, b), f in explicit.items():
        edges.setdefault((b, a), 1 / f)
    edges = {k: v for k, v in edges.items() if k not in explicit}
    edges.update(explicit)
    return edges


def best_rate(rates, src, dst, max_hops=3):
    if max_hops < 1:
        raise ValueError("max_hops must be >= 1")
    edges = _build(rates)
    nodes = {n for e in edges for n in e}
    if src not in nodes or dst not in nodes:
        return None
    best = {src: Fraction(1)}
    for _ in range(max_hops):
        new = dict(best)
        for (a, b), r in edges.items():
            if a in best:
                v = best[a] * r
                if b not in new or v > new[b]:
                    new[b] = v
        best = new
    return best.get(dst)


def convert(rates, src, dst, amount, max_hops=3):
    if amount < 0:
        raise ValueError("amount must be >= 0")
    r = best_rate(rates, src, dst, max_hops)
    if r is None:
        return None
    return (2 * amount * r.numerator + r.denominator) // (2 * r.denominator)
