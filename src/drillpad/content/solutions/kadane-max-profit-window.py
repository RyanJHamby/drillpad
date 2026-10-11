# ruff: noqa
def max_subarray(returns):
    if not returns:
        raise ValueError("returns must be non-empty")
    best = returns[0]
    best_l = best_r = 0
    cur = returns[0]
    cur_l = 0
    for i in range(1, len(returns)):
        if cur < 0:
            cur = returns[i]
            cur_l = i
        else:
            cur += returns[i]
        if cur > best:
            best, best_l, best_r = cur, cur_l, i
    return (best, best_l, best_r)
