# ruff: noqa
def find_median_sorted_arrays(a, b):
    if len(a) > len(b):
        a, b = b, a
    m, n = len(a), len(b)
    half = (m + n + 1) // 2
    lo, hi = 0, m
    inf = float("inf")
    while lo <= hi:
        i = (lo + hi) // 2
        j = half - i
        al = a[i - 1] if i > 0 else -inf
        ar = a[i] if i < m else inf
        bl = b[j - 1] if j > 0 else -inf
        br = b[j] if j < n else inf
        if al <= br and bl <= ar:
            if (m + n) % 2:
                return float(max(al, bl))
            return (max(al, bl) + min(ar, br)) / 2.0
        if al > br:
            hi = i - 1
        else:
            lo = i + 1
    raise ValueError("inputs must be sorted")
