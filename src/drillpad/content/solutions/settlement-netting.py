# ruff: noqa
from collections import defaultdict


def _net(debts):
    bal = defaultdict(int)
    for frm, to, amount in debts:
        bal[frm] -= amount
        bal[to] += amount
    return bal


def min_transfers(debts):
    net = [v for v in _net(debts).values() if v != 0]
    n = len(net)
    if n == 0:
        return 0
    full = 1 << n
    total = [0] * full                     # sum of balances per subset
    for mask in range(1, full):
        low = mask & -mask
        total[mask] = total[mask ^ low] + net[low.bit_length() - 1]
    # dp[mask] = max number of disjoint zero-sum groups inside mask
    dp = [0] * full
    for mask in range(1, full):
        best = 0
        for i in range(n):
            if mask >> i & 1 and dp[mask ^ (1 << i)] > best:
                best = dp[mask ^ (1 << i)]
        dp[mask] = best + (1 if total[mask] == 0 else 0)
    return n - dp[full - 1]


def central_bank_transfers(debts):
    out = []
    bal = _net(debts)
    for bank in sorted(bal, key=str):
        v = bal[bank]
        if v < 0:
            out.append((bank, "CENTRAL_BANK", -v))
        elif v > 0:
            out.append(("CENTRAL_BANK", bank, v))
    return out
