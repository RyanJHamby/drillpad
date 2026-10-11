# ruff: noqa
# gen
def longest_unique(s):
    last, left, best = {}, 0, 0
    for r, ch in enumerate(s):
        if ch in last and last[ch] >= left:
            left = last[ch] + 1
        last[ch] = r
        best = max(best, r - left + 1)
    return best
