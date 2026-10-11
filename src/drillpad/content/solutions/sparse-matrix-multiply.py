# ruff: noqa
def multiply(a, b):
    if not a:
        return []
    k = len(b)
    for row in a:
        if len(row) != k:
            raise ValueError("inner dimensions disagree")
    n = len(b[0]) if b else 0
    brows = [[(j, v) for j, v in enumerate(row) if v] for row in b]
    out = [[0] * n for _ in a]
    for i, row in enumerate(a):
        oi = out[i]
        for t, av in enumerate(row):
            if av:
                for j, bv in brows[t]:
                    oi[j] += av * bv
    return out
