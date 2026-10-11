# ruff: noqa
def asof_join(left, right, tolerance=None, allow_exact=True):
    out = []
    j = 0
    n = len(right)
    prev = None
    for ts, payload in left:
        if prev is not None and ts < prev:
            raise ValueError("left must be sorted")
        prev = ts
        # advance j to the first right row that is NOT eligible (too new)
        while j < n and (right[j][0] <= ts if allow_exact else right[j][0] < ts):
            j += 1
        match = None
        if j > 0:
            r_ts, r_payload = right[j - 1]
            if tolerance is None or ts - r_ts <= tolerance:
                match = r_payload
        out.append((ts, payload, match))
    return out
