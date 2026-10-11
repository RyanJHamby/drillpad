# ruff: noqa
def split_bill(total, people):
    if type(total) is not int or total < 0 or not people or len(set(people)) != len(people):
        raise ValueError("bad split")
    n = len(people)
    base, extra = divmod(total, n)
    out = {}
    for i, name in enumerate(sorted(people)):
        out[name] = base + (1 if i < extra else 0)
    return out


def _settle(group):
    debtors = sorted([[-v, k] for k, v in group if v < 0], reverse=True)
    creditors = sorted([[v, k] for k, v in group if v > 0], reverse=True)
    out = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amt = min(debtors[i][0], creditors[j][0])
        out.append((debtors[i][1], creditors[j][1], amt))
        debtors[i][0] -= amt
        creditors[j][0] -= amt
        if debtors[i][0] == 0:
            i += 1
        if creditors[j][0] == 0:
            j += 1
    return out


def min_cash_flow(net):
    if sum(net.values()) != 0:
        raise ValueError("balances must sum to zero")
    people = sorted((k, v) for k, v in net.items() if v != 0)
    n = len(people)
    if n == 0:
        return []
    size = 1 << n
    total = [0] * size
    for mask in range(1, size):
        low = mask & -mask
        total[mask] = total[mask ^ low] + people[low.bit_length() - 1][1]
    dp = [0] * size
    for mask in range(1, size):
        best = 0
        m = mask
        while m:
            low = m & -m
            if dp[mask ^ low] > best:
                best = dp[mask ^ low]
            m ^= low
        dp[mask] = best + (1 if total[mask] == 0 else 0)
    # walk back from the full mask, collecting zero-sum boundaries
    mask = size - 1
    bounds = []
    while mask:
        if total[mask] == 0:
            bounds.append(mask)
        want = dp[mask] - (1 if total[mask] == 0 else 0)
        m = mask
        nxt = None
        while m:
            low = m & -m
            if dp[mask ^ low] == want:
                nxt = mask ^ low
                break
            m ^= low
        mask = nxt
    bounds.sort()
    out = []
    prev = 0
    for b in bounds:
        grp = b ^ prev
        out.extend(_settle([people[i] for i in range(n) if grp >> i & 1]))
        prev = b
    return out
